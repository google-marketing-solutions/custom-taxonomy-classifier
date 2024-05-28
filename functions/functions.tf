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

data "google_project" "project" {}

resource "google_storage_bucket" "classify_cron_code" {
  name     = format("%s-classify-cron-code", data.google_project.project.number)
  location = "US"
}

data "archive_file" "default" {
  type        = "zip"
  output_path = "/tmp/classify-cron.zip"
  source_dir  = "./classify_cron/"
}

resource "google_storage_bucket_object" "archive" {
  name   = "classify-cron.zip"
  bucket = google_storage_bucket.classify_cron_code.name
  source = data.archive_file.default.output_path
}

resource "google_cloudfunctions2_function" "classify_cron" {
  name        = "classify-cron"
  location    = var.region
  description = "A function to classify keywords on a cron job."

  build_config {
    runtime     = "python312"
    entry_point = "main"
    source {
      storage_source {
        bucket = google_storage_bucket.classify_cron_code.name
        object = google_storage_bucket_object.archive.name
      }
    }
  }

  service_config {
    max_instance_count    = 1
    available_memory      = "8Gi"
    timeout_seconds       = 3600
    service_account_email = google_service_account.classify_cron_sa.email
    environment_variables = {
      ADS_TRANSFER_DATASET        = var.ads_transfer_dataset
      CLASSIFICATIONS_DATASET     = var.classifications_dataset
      CLASSIFY_API_URL            = var.classify_api_url
      ADS_TRANSFER_ACCOUNT_ID     = var.ads_transfer_account_id
      DAILY_COST_THRESHOLD_MICROS = var.daily_cost_micros_threshold
    }
  }
}

output "function_uri" {
  value = google_cloudfunctions2_function.classify_cron.service_config[0].uri
}

# IAM entry for all users to invoke the function
resource "google_cloudfunctions2_function_iam_member" "invoker" {
  project        = google_cloudfunctions2_function.classify_cron.project
  location       = google_cloudfunctions2_function.classify_cron.location
  cloud_function = google_cloudfunctions2_function.classify_cron.name
  role           = "roles/cloudfunctions.invoker"
  member         = "serviceAccount:${google_service_account.classify_cron_sa.email}"
}

resource "google_cloud_run_service_iam_member" "cloud_run_invoker" {
  project  = google_cloudfunctions2_function.classify_cron.project
  location = google_cloudfunctions2_function.classify_cron.location
  service  = google_cloudfunctions2_function.classify_cron.name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.classify_cron_sa.email}"
}

resource "google_cloud_scheduler_job" "invoke_cloud_function" {
  name             = "invoke-classify-cron"
  description      = "Schedule the HTTPS trigger for the classify cron job."
  schedule         = "0 0 * * *" # every day at midnight UTC.
  project          = google_cloudfunctions2_function.classify_cron.project
  region           = google_cloudfunctions2_function.classify_cron.location
  attempt_deadline = "1800s"

  http_target {
    uri         = google_cloudfunctions2_function.classify_cron.service_config[0].uri
    http_method = "POST"
    oidc_token {
      audience              = "${google_cloudfunctions2_function.classify_cron.service_config[0].uri}/"
      service_account_email = google_service_account.classify_cron_sa.email
    }
  }
}