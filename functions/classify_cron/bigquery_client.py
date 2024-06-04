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

"""A client to read and write from/to BigQuery."""

import datetime
import os

from absl import logging
from google.cloud import bigquery

import constants


_BQ_STREAMING_INSERT_BATCH_SIZE = 1000


class BigQueryClient:
  """A class to read and write to BigQuery."""

  def __init__(self) -> None:
    """Instantiates the BigQuery Client."""
    self._client = bigquery.Client()
    self._ads_transfer_dataset = os.environ["ADS_TRANSFER_DATASET"]
    self._ads_transfer_account_id = os.environ["ADS_TRANSFER_ACCOUNT_ID"]
    self._classifications_dataset = os.environ["CLASSIFICATIONS_DATASET"]
    self._daily_cost_threshold_micros = os.environ[
        "DAILY_COST_THRESHOLD_MICROS"
    ]
    logging.info("BigQueryClient: Initialized.")

  def get_spending_keywords(self) -> list[str]:
    """Reads spending keywords for Google Ads Datatransfer tables.

    Returns:
      A list of keywords.
    """
    query = constants.SPENDING_KEYWORDS_QUERY.format(
        ads_transfer_dataset=self._ads_transfer_dataset,
        ads_transfer_account_id=self._ads_transfer_account_id,
        daily_cost_threshold_micros=self._daily_cost_threshold_micros,
    )
    query_job = self._client.query(query)
    rows = query_job.result()
    keyword_list = [row.keyword_text for row in rows]
    logging.info("BigQueryClient: Found %s keywords.", len(keyword_list))
    return keyword_list

  def get_current_keyword_mappings(self) -> dict[str, str]:
    """Reads the current mappings from the single dimension keyword table."""
    query = constants.CURRENT_KEYWORD_MAPPINGS_QUERY.format(
        classifications_dataset=self._classifications_dataset
    )
    query_job = self._client.query(query)
    rows = query_job.result()
    keyword_category_map = dict()
    for row in rows:
      keyword_category_map[row.keyword_text] = row.category_name
    return keyword_category_map

  def _write_classified_keywords_to_staging(
      self, classified_keywords: dict[str, str]
  ) -> None:
    """Writes newly classified keywords to the staging table.

    Args:
      classified_keywords: The list of keywords with classification metadata.
    """
    # Truncates the staging table.
    truncate_job = self._client.query(
        constants.TRUNCATE_STAGING_TABLE_QUERY.format(
            classifications_dataset=self._classifications_dataset
        )
    )
    truncate_job.result()  # Waits for the query to finish.
    logging.info("BigQueryClient: Staging table truncated.")
    rows = []
    for keyword in classified_keywords.keys():
      rows.append({
          "keyword_text": keyword,
          "category_name": classified_keywords[keyword],
          "datetime": datetime.datetime.now(tz=datetime.timezone.utc).strftime(
              "%Y-%m-%d %H:%M:%S.%f"
          ),
      })
    rows_to_process = rows
    while rows_to_process:
      chunk, rows_to_process = (
          rows_to_process[:_BQ_STREAMING_INSERT_BATCH_SIZE],
          rows_to_process[_BQ_STREAMING_INSERT_BATCH_SIZE:],
      )
      pct_complete = (
          f"{int(round((len(rows) - len(rows_to_process)) / len(rows) * 100, 1))}%"
      )
      logging.info(
          "BigQueryClient: Streaming data to staging table %s complete.",
          pct_complete,
      )
      errors = self._client.insert_rows_json(
          constants.KEYWORD_DIM_STAGING_TABLE_NAME.format(
              classifications_dataset=self._classifications_dataset
          ),
          chunk,
      )
      if not errors:
        logging.info("BigQueryClient: New rows have been added.")
      else:
        logging.error(
            "BigQueryClient: Encountered errors while inserting rows: %s",
            errors,
        )

  def write_classified_keywords(
      self, classified_keywords: dict[str, str]
  ) -> None:
    """Populates the keyword tables with classified keywords if applicable.

    Args:
      classified_keywords: The list of keywords with classification metadata.
    """
    # Populates staging table.
    if not classified_keywords:
      logging.info("BigQueryClient: No new rows to add.")
      return
    self._write_classified_keywords_to_staging(classified_keywords)
    logging.info("BigQueryClient: Wrote classified keywords to staging table.")
    # Merges the staging table with the dimension table.
    query = constants.MERGE_STAGING_TO_PROD_QUERY.format(
        classifications_dataset=self._classifications_dataset
    )
    merge_staging_to_dim_job = self._client.query(query)
    merge_staging_to_dim_job.result()  # Wait for the query to finish.
    logging.info("BigQueryClient: Merged staging with dim table.")
    # Updates the slowly changing dimensions (SDC) table.
    update_scd_job = self._client.query(
        constants.MERGE_PROD_TO_SCD_QUERY.format(
            classifications_dataset=self._classifications_dataset
        )
    )
    update_scd_job.result()  # Wait for the query to finish.
    logging.info("BigQueryClient: SDC table updated.")
