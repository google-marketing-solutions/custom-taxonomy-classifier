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

variable "project_id" {
  description = "The GCP Project to deploy the classify-cron function."
}

variable "region" {
  description = "The GCP Region to deploy the classify-cron function."
}

variable "ads_transfer_dataset" {
  description = "The dataset that contains the Google Ads Data Transfer tables."
}

variable "classifications_dataset" {
  description = "The BigQuery dataset that will contain the classifications tables."
}

variable "classify_api_url" {
  description = "The customer classification API URL."
}

variable "ads_transfer_account_id" {
  description = "The customer ID for which the Google Ads Data Transfer service was configured."
}

variable "daily_cost_micros_threshold" {
  description = "The cost threshold in micros for keywords to be considered for classification."
}

##
# Test utilities

variable "test_google_access_token" {
  type    = string
  default = null
}