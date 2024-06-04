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

"""Google Cloud Function entry point."""

from absl import logging
import flask
import functions_framework
import bigquery_client as bigquery_client_lib
import classify_client as classify_client_lib
import google.cloud.logging

logging_client = google.cloud.logging.Client()
logging_client.setup_logging()


@functions_framework.http
def main(request: ...) -> flask.Response:
  del request  # unused.
  try:
    bigquery_client = bigquery_client_lib.BigQueryClient()
    classify_client = classify_client_lib.ClassifyClient()
    keywords = bigquery_client.get_spending_keywords()
    logging.info('Main: Found %s keywords with current spend.', len(keywords))
    classified_keywords = classify_client.classify_keywords(keywords)
    logging.info('Main: Classification of keywords complete.')
    keyword_map = bigquery_client.get_current_keyword_mappings()
    logging.info(
        'Main: %s existing keywords with a classification', len(keyword_map)
    )
    new_classified_keywords = {
        k: classified_keywords[k]
        for k in set(classified_keywords) - set(keyword_map)
    }
    logging.info(
        'Main: %s keywords with classification to add or update.',
        len(new_classified_keywords),
    )
    bigquery_client.write_classified_keywords(new_classified_keywords)
  except Exception as err:
    logging.exception(err)
    return flask.Response(
        status=500, response='An exception occurred. Checks logs for details.'
    )
  return flask.Response(
      status=200,
      response=(
          f'Successfully modified {len(new_classified_keywords)} keywords.'
      ),
  )
