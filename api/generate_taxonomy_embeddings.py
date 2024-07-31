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

"""Generates taxonomy embeddings for a task."""

import datetime
import os
import sys
from typing import Optional
import uuid

from absl import logging
from googleapiclient import discovery

from common import ai_platform_client as ai_platform_client_lib
from common import storage_client as storage_client_lib
from common import vertex_client as vertex_client_lib
import google.cloud.logging
from database import base_postgres_client as base_postgres_client_lib
from database import errors as errors_lib
from database import postgres_client as postgres_client_lib
from datamodel import task as task_lib
from services import taxonomy_service as taxonomy_service_lib


logging_client = google.cloud.logging.Client()
logging_client.setup_logging()

# Retrieve Job-defined env vars
SPREADSHEET_ID: Optional[str] = os.getenv('SPREADSHEET_ID')
WORKSHEET_NAME: Optional[str] = os.getenv('WORKSHEET_NAME')
WORKSHEET_COL_INDEX: Optional[str] = os.getenv('WORKSHEET_COL_INDEX')
HEADER: bool = os.getenv('HEADER', 'False') == 'True'
TASK_ID: Optional[str] = os.getenv('TASK_ID', str(uuid.uuid4()))
GCP_PROJECT_ID: Optional[str] = os.getenv('GCP_PROJECT_ID')
GCP_REGION: Optional[str] = os.getenv('GCP_REGION')
SERVICE_NAME: Optional[str] = 'classify-service'


def restart_cloud_run_service(
    project_id: str, region: str, service_name: str
) -> None:
  """Restarts a Cloud Run service using the googleapiclient.discovery library.

  Args:
      project_id: Your Google Cloud project ID.
      region: The region where the Cloud Run service is deployed.
      service_name: The name of the Cloud Run service.
  """
  service = discovery.build('run', 'v2')
  parent = f'projects/{project_id}/locations/{region}'
  name = f'{parent}/services/{service_name}'

  # Get the current configuration of the service.
  logging.info('Retrieving current configuration for service %s.', service_name)
  service_config = (
      service.projects().locations().services().get(name=name).execute()
  )
  # Update the service configuration to trigger a restart
  # We don't technically make any configuration changes for a restart,
  # but we need to send an update request to trigger the restart, so we add
  # a new env var with the current timestamp to force a change.
  env_vars = service_config['template']['containers'][0]['env']
  env_vars.append(
      {'name': 'RESTART_TIME', 'value': str(datetime.datetime.now())}
  )
  service_config['template']['containers'][0]['env'] = env_vars

  logging.info(
      'Restart initiated for service %s. Waiting for operation to complete...',
      service_name,
  )
  operation = (
      service.projects()
      .locations()
      .services()
      .patch(
          name=name,
          body=service_config,
      )
      .execute()
  )
  # Poll the operation to wait for completion.
  while True:
    operation_result = (
        service.projects()
        .locations()
        .operations()
        .get(name=operation['name'])
        .execute()
    )
    if operation_result.get('done'):
      break

  # Check if the restart operation was successful.
  if 'error' in operation_result:
    logging.error(
        'Error restarting service %s: {operation_result["error"]}', service_name
    )
  else:
    logging.info('Service %s restarted successfully.', service_name)


def setup_vector_search_endpoint_from_spreadsheet_data(
    spreadsheet_id: str,
    worksheet_name: str,
    worksheet_col_index: int | str,
    header: bool,
    task_id: str,
):
  """Sets up the vector search endpoint.

  Args:
    spreadsheet_id: The ID of the spreadsheet containing the taxonomy.
    worksheet_name: The name of the worksheet containing the taxonomy.
    worksheet_col_index: The 1-based column index that contains the taxonomy.
    header: Whether or not the column has a header row.
    task_id: The name of the task from the request.
  """
  base_postgres_client = base_postgres_client_lib.BasePostgresClient()
  base_postgres_client.create_tables_if_not_exist()
  postgres_client = postgres_client_lib.PostgresClient(
      base_postgres_client.engine
  )
  vertex_client = vertex_client_lib.VertexClient()
  storage_client = storage_client_lib.StorageClient()
  ai_platform_client = ai_platform_client_lib.AiPlatformClient()

  taxonomy_service = taxonomy_service_lib.TaxonomyService(
      postgres_client,
      vertex_client,
      storage_client,
      ai_platform_client,
      task_id,
  )
  try:
    taxonomy_service.create_taxonomy_embeddings_index_endpoint(
        spreadsheet_id,
        worksheet_name,
        int(worksheet_col_index),
        header,
    )
  # Isolation block to update DB status to failed in event of exception.
  except Exception as e:
    logging.exception(
        'Failed to create taxonomy embeddings index endpoint: %s.', e
    )
    postgres_client.update_task(task_id, task_lib.TaskStatus.FAILED)


if __name__ == '__main__':
  try:
    setup_vector_search_endpoint_from_spreadsheet_data(
        SPREADSHEET_ID, WORKSHEET_NAME, WORKSHEET_COL_INDEX, HEADER, TASK_ID
    )
    restart_cloud_run_service(GCP_PROJECT_ID, GCP_REGION, SERVICE_NAME)
  except taxonomy_service_lib.GetTaxonomyError:
    logging.exception(
        'Generating taxonomy embeddings for task: %s failed.',
        TASK_ID,
    )
    sys.exit(1)
  except errors_lib.PostgresClientError:
    logging.exception(
        'Generating taxonomy embeddings for task: %s failed.',
        TASK_ID,
    )
    sys.exit(1)
