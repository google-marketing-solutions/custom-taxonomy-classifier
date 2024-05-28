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

# Images

variable "classify_service_image" {
  description = "The Docker Image for the classify service."
}

variable "taxonomy_job_image" {
  description = "The Docker Image for the taxonomy job."
}

##
# Google Cloud Project

variable "project_id" {
  description = "GCP Project ID"
}

variable "region" {
  description = "GCP Region"
}

variable "postgres_db_user" {
  description = "The Cloud SQL Postgres user name"
}

variable "postgres_db_password" {
  description = "The Cloud SQL Postgres user password"
}

variable "postgres_db_name" {
  description = "The Cloud SQL Postgres Database name"
}

##
# Test utilities

variable "test_google_access_token" {
  type    = string
  default = null
}