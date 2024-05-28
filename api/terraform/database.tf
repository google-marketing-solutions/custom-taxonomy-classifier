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

## Creates a Cloud SQL database instance.

resource "google_sql_database_instance" "classify_api_instance" {
  name             = "classify-api-instance"
  region           = var.region
  database_version = "POSTGRES_15"

  depends_on = [google_service_networking_connection.vpc_connection]

  deletion_protection = true
  settings {
    tier = "db-custom-1-3840"
    ip_configuration {
      ipv4_enabled                                  = "false"
      private_network                               = google_compute_network.classify_api_network.id
      enable_private_path_for_google_cloud_services = true
    }
  }
}
resource "google_sql_database" "database" {
  name     = var.postgres_db_name
  instance = google_sql_database_instance.classify_api_instance.name
}
resource "google_sql_user" "database_user" {
  name     = var.postgres_db_user
  instance = google_sql_database_instance.classify_api_instance.name
  password = var.postgres_db_password
}