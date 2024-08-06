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
# Service Accounts
#

resource "google_service_account" "classify_api_sa" {
  account_id   = "classify-api-sa"
  display_name = "Classify API Service Account"
  project      = var.project_id
}

resource "google_service_account" "pubsub_sa" {
  account_id   = "classify-api-pubsub-invoker"
  display_name = "Classify API Pub/Sub Service Account"
  project      = var.project_id
}

resource "google_project_service_identity" "cloudbuild_managed_sa" {
  provider = google-beta
  project  = var.project_id
  service  = "cloudbuild.googleapis.com"
}

resource "google_project_service_identity" "pubsub_agent" {
  provider = google-beta
  project  = var.project_id
  service  = "pubsub.googleapis.com"
}

##
# Service Account Permissions
#

resource "google_project_iam_member" "classify_api_sa_logging_writer" {
  member  = "serviceAccount:${google_service_account.classify_api_sa.email}"
  project = var.project_id
  role    = "roles/logging.logWriter"
}

resource "google_project_iam_member" "classify_api_sa_logging_viewer" {
  member  = "serviceAccount:${google_service_account.classify_api_sa.email}"
  project = var.project_id
  role    = "roles/logging.viewer"
}

resource "google_project_iam_member" "classify_api_sa_token_creator" {
  member  = "serviceAccount:${google_service_account.classify_api_sa.email}"
  project = var.project_id
  role    = "roles/iam.serviceAccountTokenCreator"
}

resource "google_project_iam_member" "classify_api_sa_service_account_user" {
  member  = "serviceAccount:${google_service_account.classify_api_sa.email}"
  project = var.project_id
  role    = "roles/iam.serviceAccountUser"
}

resource "google_project_iam_member" "classify_api_sa_storage_object_admin" {
  member  = "serviceAccount:${google_service_account.classify_api_sa.email}"
  project = var.project_id
  role    = "roles/storage.objectAdmin"
}

resource "google_project_iam_member" "classify_api_sa_vertexai_user" {
  member  = "serviceAccount:${google_service_account.classify_api_sa.email}"
  project = var.project_id
  role    = "roles/aiplatform.user"
}

resource "google_project_iam_member" "classify_api_sa_sql_admin" {
  member  = "serviceAccount:${google_service_account.classify_api_sa.email}"
  project = var.project_id
  role    = "roles/cloudsql.admin"
}

resource "google_project_iam_member" "classify_api_sa_cloudbuild_builder" {
  member  = "serviceAccount:${google_service_account.classify_api_sa.email}"
  project = var.project_id
  role    = "roles/cloudbuild.builds.builder"
}

# Needed to execute a cloud run job with overrides and restart a cloud run service.
resource "google_project_iam_member" "classify_api_sa_run_admin" {
  member  = "serviceAccount:${google_service_account.classify_api_sa.email}"
  project = var.project_id
  role    = "roles/run.admin"
}

# Needed to access the classify service image during migrations from Cloud Build.
resource "google_project_iam_member" "cloudbuild_managed_sa_object_viewer" {
  member  = "serviceAccount:${google_project_service_identity.cloudbuild_managed_sa.email}"
  project = var.project_id
  role    = "roles/storage.objectViewer"
}

##
# Cloud Run permissions
#

data "google_iam_policy" "classify_service_run_users" {
  binding {
    role = "roles/run.invoker"
    members = [
      "serviceAccount:${google_service_account.classify_api_sa.email}",
      "serviceAccount:${google_service_account.pubsub_sa.email}",
    ]
  }
}

resource "google_cloud_run_v2_service_iam_policy" "backend_run_invoker" {
  location    = google_cloud_run_v2_service.classify_service_run.location
  project     = google_cloud_run_v2_service.classify_service_run.project
  name        = google_cloud_run_v2_service.classify_service_run.name
  policy_data = data.google_iam_policy.classify_service_run_users.policy_data
}

resource "google_cloud_run_v2_job_iam_policy" "taxonomy_job_run_invoker" {
  location    = google_cloud_run_v2_job.taxonomy_job_run.location
  project     = google_cloud_run_v2_job.taxonomy_job_run.project
  name        = google_cloud_run_v2_job.taxonomy_job_run.name
  policy_data = data.google_iam_policy.classify_service_run_users.policy_data
}

resource "google_project_iam_binding" "project_token_creator" {
  project = var.project_id
  role    = "roles/iam.serviceAccountTokenCreator"
  members = ["serviceAccount:${google_project_service_identity.pubsub_agent.email}"]
}
