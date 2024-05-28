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

resource "google_bigquery_table" "keywords" {
  dataset_id          = google_bigquery_dataset.classifications.dataset_id
  table_id            = "keywords"
  deletion_protection = true

  time_partitioning {
    type = "DAY"
  }

  schema = <<EOF
[
    {
        "name": "keyword_text",
        "type": "STRING",
        "mode": "REQUIRED",
        "description": "The keyword text."
    },
    {
        "name": "category_name",
        "type": "STRING",
        "mode": "NULLABLE",
        "description": "The category of the keyword from the classification API."
    },
    {
        "name": "updated_at",
        "type": "DATETIME",
        "mode": "NULLABLE",
        "description": "The datetime when the classification was written."
    }
]
EOF

}

resource "google_bigquery_table" "keywords_staging" {
  dataset_id = google_bigquery_dataset.classifications.dataset_id
  table_id   = "keywords_staging"

  schema = <<EOF
[
    {
        "name": "keyword_text",
        "type": "STRING",
        "mode": "REQUIRED",
        "description": "The keyword text."
    },
    {
        "name": "category_name",
        "type": "STRING",
        "mode": "NULLABLE",
        "description": "The category of the keyword from the classification API."
    },
    {
        "name": "datetime",
        "type": "DATETIME",
        "mode": "NULLABLE",
        "description": "The datetime when the classification was written."
    }
]
EOF

}

resource "google_bigquery_table" "keywords_scd" {
  dataset_id          = google_bigquery_dataset.classifications.dataset_id
  table_id            = "keywords_scd"
  deletion_protection = true

  time_partitioning {
    type = "DAY"
  }

  schema = <<EOF
[
    {
        "name": "id",
        "type": "STRING",
        "mode": "REQUIRED",
        "description": "The id of the table row."
    },
    {
        "name": "keyword_text",
        "type": "STRING",
        "mode": "REQUIRED",
        "description": "The keyword text."
    },
    {
        "name": "category_name",
        "type": "STRING",
        "mode": "NULLABLE",
        "description": "The category of the keyword from the classification API."
    },
    {
        "name": "start_datetime",
        "type": "DATETIME",
        "mode": "NULLABLE",
        "description": "The datetime when the keyword had this category."
    },
    {
        "name": "end_datetime",
        "type": "DATETIME",
        "mode": "NULLABLE",
        "description": "The datetime when a new category for the keyword text became available."
    }
]
EOF

}

resource "google_bigquery_dataset" "classifications" {
  dataset_id    = var.classifications_dataset
  friendly_name = var.classifications_dataset
  description   = "A dataset to host the keyword classifications."
  location      = var.region

  access {
    role          = "OWNER"
    user_by_email = google_service_account.classify_cron_sa.email
  }
}

resource "google_bigquery_dataset_iam_member" "admin" {
  dataset_id = google_bigquery_dataset.classifications.dataset_id
  role       = "roles/bigquery.admin"

  member = "serviceAccount:${google_service_account.classify_cron_sa.email}"
}

resource "google_project_iam_member" "admin" {
  project = var.project_id
  role    = "roles/bigquery.admin"
  member  = "serviceAccount:${google_service_account.classify_cron_sa.email}"
}
