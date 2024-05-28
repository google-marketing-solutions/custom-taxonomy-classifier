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

resource "google_service_account" "classify_cron_sa" {
  account_id   = "classify-cron-sa"
  display_name = "The Service Account to run the classify-cron function."
}

resource "google_project_iam_member" "classify_cron_sa_bq_data_editor" {
  member  = "serviceAccount:${google_service_account.classify_cron_sa.email}"
  project = var.project_id
  role    = "roles/bigquery.admin"
}

resource "google_project_iam_member" "classify_cron_sa_bq_job_user" {
  member  = "serviceAccount:${google_service_account.classify_cron_sa.email}"
  project = var.project_id
  role    = "roles/bigquery.jobUser"
}

resource "google_project_iam_member" "classify_cron_sa_run_invoker" {
  member  = "serviceAccount:${google_service_account.classify_cron_sa.email}"
  project = var.project_id
  role    = "roles/run.invoker"
}