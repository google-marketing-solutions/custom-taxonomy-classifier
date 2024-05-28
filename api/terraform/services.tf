# Copyright 2024 Google LLC.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

##
# Cloud Storage Bucket
#
# Creates a Google Cloud Storage bucket store category embedding vectors.

data "google_project" "project" {}

resource "google_storage_bucket" "vector_search_bucket" {
  name                        = format("%s-vector-search-embeddings", var.project_id)
  storage_class               = "REGIONAL"
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true
  force_destroy               = false
}

##
# Cloud Run Services
#
resource "google_cloud_run_v2_service" "classify_service_run" {
  name     = "classify-service"
  location = var.region
  project  = var.project_id
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.classify_api_sa.email
    timeout         = "3600s"
    containers {
      image = data.google_container_registry_image.classify_service_latest.image_url
      resources {
        limits = {
          cpu    = "2000m"
          memory = "4Gi"
        }
        cpu_idle          = true
        startup_cpu_boost = true
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "POSTGRES_DB_USER"
        value = var.postgres_db_user
      }
      env {
        name  = "POSTGRES_DB_PASSWORD"
        value = var.postgres_db_password
      }
      env {
        name  = "POSTGRES_INSTANCE_HOST"
        value = google_sql_database_instance.classify_api_instance.ip_address.0.ip_address
      }
      env {
        name  = "POSTGRES_INSTANCE_PORT"
        value = 5432
      }
      env {
        name  = "POSTGRES_DB_NAME"
        value = var.postgres_db_name
      }
      env {
        name  = "TAXONOMY_JOB_URL"
        value = format("https://%s-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/%s/jobs/write-taxonomy-embeddings:run", var.region, var.project_id)
      }
      env {
        name  = "BUCKET_NAME"
        value = google_storage_bucket.vector_search_bucket.name
      }
      env {
        name  = "VPC_NETWORK_ID"
        value = format("projects/%s/global/networks/%s", data.google_project.project.number, google_compute_network.classify_api_network.name)
      }
    }

    vpc_access {
      connector = google_vpc_access_connector.connector.id
      egress    = "ALL_TRAFFIC"
    }

    scaling { # Replaces autoscaling annotations
      min_instance_count = 1
      max_instance_count = 80
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.apis,
    google_project_iam_member.classify_api_sa_token_creator,
    google_cloud_run_v2_job.taxonomy_job_run,
    google_storage_bucket.vector_search_bucket,
    google_sql_database_instance.classify_api_instance,
  ]
}

locals {
  classify_service_url = google_cloud_run_v2_service.classify_service_run.uri
}

resource "google_cloud_run_v2_job" "taxonomy_job_run" {
  name     = "write-taxonomy-embeddings"
  location = var.region
  project  = var.project_id

  template {
    template {
      service_account = google_service_account.classify_api_sa.email
      timeout         = "18000s" # 5 hours
      containers {
        image = data.google_container_registry_image.taxonomy_job_latest.image_url
        resources {
          limits = {
            cpu    = "4"
            memory = "2048Mi"
          }
        }
        env {
          name  = "GCP_PROJECT_ID"
          value = var.project_id
        }
        env {
          name  = "GCP_REGION"
          value = var.region
        }
        env {
          name  = "POSTGRES_DB_USER"
          value = var.postgres_db_user
        }
        env {
          name  = "POSTGRES_DB_PASSWORD"
          value = var.postgres_db_password
        }
        env {
          name  = "POSTGRES_INSTANCE_HOST"
          value = google_sql_database_instance.classify_api_instance.ip_address.0.ip_address
        }
        env {
          name  = "POSTGRES_INSTANCE_PORT"
          value = 5432
        }
        env {
          name  = "POSTGRES_DB_NAME"
          value = var.postgres_db_name
        }
        env {
          name  = "SPREADSHEET_ID"
          value = ""
        }
        env {
          name  = "WORKSHEET_NAME"
          value = ""
        }
        env {
          name  = "WORKSHEET_COL_INDEX"
          value = ""
        }
        env {
          name  = "HEADER"
          value = "True"
        }
        env {
          name  = "TASK_ID"
          value = null
        }
        env {
          name  = "BUCKET_NAME"
          value = google_storage_bucket.vector_search_bucket.name
        }
        env {
          name  = "VPC_NETWORK_ID"
          value = format("projects/%s/global/networks/%s", data.google_project.project.number, google_compute_network.classify_api_network.name)
        }
      }

      vpc_access {
        connector = google_vpc_access_connector.connector.id
        egress    = "ALL_TRAFFIC"
      }

    }
  }
  depends_on = [
    google_project_service.apis,
    google_project_iam_member.classify_api_sa_token_creator,
    google_storage_bucket.vector_search_bucket,
    google_compute_network.classify_api_network,
    google_sql_database_instance.classify_api_instance,
  ]
}

## In order to update the Cloud Run deployment when the underlying :latest
## image changes, we will retrieve the sha256_digest of the image through
## the docker provider, since the google container registry does not seem
## to have an API.
data "google_client_config" "default" {}

provider "docker" {
  registry_auth {
    address  = "gcr.io"
    username = "oauth2accesstoken"
    password = data.google_client_config.default.access_token
  }
}

data "docker_registry_image" "classify_service_image" {
  name = format("%s:%s", var.classify_service_image, "latest")
}

data "docker_registry_image" "taxonomy_job_image" {
  name = format("%s:%s", var.taxonomy_job_image, "latest")
}

data "google_container_registry_image" "classify_service_latest" {
  name    = "classify-service"
  project = var.project_id
  digest  = data.docker_registry_image.classify_service_image.sha256_digest
}

data "google_container_registry_image" "taxonomy_job_latest" {
  name    = "taxonomy-job"
  project = var.project_id
  digest  = data.docker_registry_image.taxonomy_job_image.sha256_digest
}
