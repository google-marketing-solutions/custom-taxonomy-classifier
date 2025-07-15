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

"""API entry point."""

import datetime
import os
from typing import Optional, Union
import uuid
from absl import logging
import fastapi
import pydantic
from common import ai_platform_client as ai_platform_client_lib
from common import api_utils
from common import vertex_client as vertex_client_lib
import google.cloud.logging
from database import base_postgres_client as base_postgres_client_lib
from database import errors
from database import postgres_client as postgres_client_lib
from services import classify_service as classify_service_lib

clients = {}
services = {}

app = fastapi.FastAPI()


class ClassifyRequest(pydantic.BaseModel):
  """Request to classify a text string or media."""

  text: str | list[str] | None = None
  media_uri: str | list[str] | None = None
  embeddings: bool = False


class ClassifyResponse(pydantic.BaseModel):
  """Response to classify a text string or media."""

  text: str | None = None
  media_uri: str | None = None
  media_description: str | None = None
  categories: list[dict[str, Union[str, float]]] = pydantic.Field(
      default_factory=list
  )
  embedding: list[float] | None = None


class GenerateTaxonomyEmbeddingsRequest(pydantic.BaseModel):
  """Request to generate taxonomy embeddings."""

  spreadsheet_id: str
  worksheet_name: str
  worksheet_col_index: str
  header: str = 'True'


class TaskStatusResponse(pydantic.BaseModel):
  """Task status."""

  task_id: str
  status: str
  time_created: Optional[datetime.datetime] = None
  time_updated: Optional[datetime.datetime] = None

  @pydantic.field_serializer('time_created', 'time_updated')
  def serialize_dt(self, dt: Optional[datetime.datetime]) -> str | None:
    """Custom serializer for datetime fields.

    Args:
      dt: The datetime object to serialize.

    Formats the datetime object to ISO 8601 with timezone.
    """
    if dt is None:
      return None
    # Ensure the datetime object has timezone information (using UTC if naive)
    if dt.tzinfo is None:
      dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.isoformat()


@app.on_event('startup')
async def startup_event():
  """Runs on server startup."""
  logging_client = google.cloud.logging.Client()
  logging_client.setup_logging()
  base_postgres_client = base_postgres_client_lib.BasePostgresClient()
  base_postgres_client.create_tables_if_not_exist()
  clients['postgres_client'] = postgres_client_lib.PostgresClient(
      base_postgres_client.engine
  )
  clients['vertex_client'] = vertex_client_lib.VertexClient()
  clients['ai_platform_client'] = ai_platform_client_lib.AiPlatformClient()
  logging.info('Instantiated clients.')

  services['classify_service'] = classify_service_lib.ClassifyService(
      clients['postgres_client'],
      clients['vertex_client'],
      clients['ai_platform_client'],
  )
  logging.info('Instantiated services.')


@app.get('/')
def root() -> dict[str, str]:
  """Root route for the web server. Exists only for debugging purpose.

  Returns:
    Dummy message.
  """
  return {'message': 'Welcome to Classify API!!!'}


@app.post('/classify')
def classify(
    request: ClassifyRequest,
) -> list[ClassifyResponse]:
  """Classifies a text.

  Args:
    request: The text to classify.

  Returns:
    A classify service classify response object.
  """
  try:
    classify_results = services['classify_service'].classify(
        request.text,
        request.media_uri,
        request.embeddings,
    )
    return classify_results
  except Exception as e:
    logging.exception('The server could not process the request.')
    raise fastapi.HTTPException(
        status_code=500, detail='The server could not process the request.'
    ) from e


@app.post(
    '/generate_taxonomy_embeddings', status_code=fastapi.status.HTTP_201_CREATED
)
async def generate_taxonomy_embeddings(
    request: GenerateTaxonomyEmbeddingsRequest,
) -> dict[str, str]:
  """Generates taxonomy embeddings.

  Args:
    request: The spreadsheet info that contains the taxonomy.

  Returns:
    A message that the task was generated.
  """
  task_id = str(uuid.uuid4())
  override_spec = {
      'overrides': {
          'container_overrides': [
              {
                  'env': [
                      {
                          'name': 'SPREADSHEET_ID',
                          'value': request.spreadsheet_id,
                      },
                      {
                          'name': 'WORKSHEET_NAME',
                          'value': request.worksheet_name,
                      },
                      {
                          'name': 'WORKSHEET_COL_INDEX',
                          'value': request.worksheet_col_index,
                      },
                      {'name': 'HEADER', 'value': request.header},
                      {'name': 'TASK_ID', 'value': task_id},
                  ]
              },
          ]
      }
  }

  url = os.environ['TAXONOMY_JOB_URL']
  api_utils.send_api_request(url, override_spec)

  return {
      'task_id': task_id,
      'message': 'Generate Taxonomy Embeddings task sent in the background.',
  }


@app.get('/task_status/{task_id}')
def get_task_status(task_id: str) -> TaskStatusResponse:
  """Gets taxonomy status."""
  try:
    return clients['postgres_client'].get_task_status(task_id)
  except errors.PostgresClientError as e:
    logging.exception('Failed to get task status for task: %s.', task_id)
    raise fastapi.HTTPException(
        status_code=500, detail='Failed to get task status.'
    ) from e
