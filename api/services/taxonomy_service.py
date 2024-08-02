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

"""Module to manage and write a taxonomy to postgres."""

from absl import logging
import google.auth
import gspread
from common import ai_platform_client as ai_platform_client_lib
from common import storage_client as storage_client_lib
from common import vertex_client as vertex_client_lib
from database import postgres_client as postgres_client_lib
from datamodel import category as category_lib
from datamodel import task as task_lib
from datamodel import taxonomy as taxonomy_lib


class Error(Exception):
  """Base error class."""


class GetTaxonomyError(Error):
  """Error class for TaxonomyService."""


class TaxonomyService:
  """A class to write embeddings for a Taxonomy to postres."""

  def __init__(
      self,
      postgres_client: postgres_client_lib.PostgresClient,
      vertex_client: vertex_client_lib.VertexClient,
      storage_client: storage_client_lib.StorageClient,
      ai_platform_client: ai_platform_client_lib.AiPlatformClient,
      task_id: str,
  ) -> None:
    """Constructor.

    Args:
      postgres_client: A read postgres client instance.
      vertex_client: A vertex client instance.
      storage_client: A storage client instance.
      ai_platform_client: An ai platform client instance.
      task_id: The taxonomy task ID.
    """
    credentials, _ = google.auth.default(
        scopes=[
            'https://spreadsheets.google.com/feeds',
            'https://www.googleapis.com/auth/drive',
        ]
    )
    self._sheets_client = gspread.authorize(credentials)
    self._postgres_client = postgres_client
    self._vertex_client = vertex_client
    self._storage_client = storage_client
    self._ai_platform_client = ai_platform_client
    self.task_id = task_id
    self._postgres_client.add_task(self.task_id)
    logging.info('TaxonomyService: Initialized with id %s.', self.task_id)

  def create_taxonomy_embeddings_index_endpoint(
      self,
      spreadsheet_id: str,
      worksheet_name: str,
      worksheet_col_index: int,
      header: bool = True,
  ) -> None:
    """Writes a Taxonomy to Google Cloud Storage.

    Args:
      spreadsheet_id: A spreadsheet alphanumeric ID.
      worksheet_name: The worksheet name e.g., Sheet1
      worksheet_col_index: The worksheet column index (1-based) that contains
        the categories.
      header: Whether or not the column contains a header row.
    """
    taxonomy = self._get_taxonomy_from_spreadsheet(
        spreadsheet_id, worksheet_name, worksheet_col_index, header
    )

    taxonomy_with_embeddings = self._add_embeddings_to_taxonomy(taxonomy)

    self._postgres_client.update_task(
        self.task_id, task_lib.TaskStatus.IN_PROGRESS_WRITING_EMBEDDINGS_TO_GCS
    )

    self._storage_client.write_taxonomy_embeddings(taxonomy_with_embeddings)
    logging.info('TaxonomyService: Wrote taxonomy embeddings to storage.')

    self._postgres_client.update_task(
        self.task_id, task_lib.TaskStatus.IN_PROGRESS_CREATING_EMBEDDINGS_INDEX
    )

    self._ai_platform_client.delete_all_embedding_index_endpoints()
    logging.info(
        'TaxonomyService: Removed all previously created embedding index'
        ' endpoints.'
    )

    embeddings_index = self._ai_platform_client.create_embeddings_index()
    logging.info(
        'TaxonomyService: Created embeddings index: %s', embeddings_index.name
    )

    self._postgres_client.update_task(
        self.task_id,
        task_lib.TaskStatus.IN_PROGRESS_CREATING_EMBEDDINGS_INDEX_ENDPOINT
    )
    embeddings_index_endpoint = (
        self._ai_platform_client.create_embeddings_index_endpoint()
    )
    logging.info(
        'TaxonomyService: Created embeddings index endpoint: %s',
        embeddings_index_endpoint.name,
    )

    self._postgres_client.update_task(
        self.task_id,
        task_lib.TaskStatus.IN_PROGRESS_DEPLOYING_EMBEDDINGS_INDEX_TO_ENDPOINT
    )

    self._ai_platform_client.deploy_embedding_index_to_endpoint(
        embeddings_index, embeddings_index_endpoint
    )
    logging.info('TaxonomyService: Deployed embeddings index to endpoint.')

    self._postgres_client.update_task(
        self.task_id, task_lib.TaskStatus.SUCCEEDED)

  def _get_taxonomy_from_spreadsheet(
      self,
      spreadsheet_id: str,
      worksheet_name: str,
      worksheet_col_index: int,
      header: bool = True,
  ) -> taxonomy_lib.Taxonomy:
    """Gets a Taxonomy from a spreadsheet.

    Args:
      spreadsheet_id: A spreadsheet alphanumeric ID.
      worksheet_name: The worksheet name e.g., Sheet1
      worksheet_col_index: The worksheet column index (1-based) that contains
        the categories.
      header: Whether or not the column contains a header row.

    Returns:
      A Taxonomy object.
    """
    logging.info('TaxonomyService: Reading taxonomy from spreadsheet.')

    spreadsheet = self._sheets_client.open_by_key(spreadsheet_id)
    worksheet = spreadsheet.worksheet(worksheet_name)
    values = worksheet.col_values(worksheet_col_index)
    values = values[1:] if header else values

    categories = []
    for index, value in enumerate(values):
      categories.append(category_lib.Category(id=str(index), name=value))

    taxonomy = taxonomy_lib.Taxonomy(
        entity_id=self.task_id, categories=categories
    )
    logging.info('TaxonomyService: Read taxonomy from spreadsheet.')
    return taxonomy

  def _add_embeddings_to_taxonomy(
      self, taxonomy: taxonomy_lib.Taxonomy
  ) -> taxonomy_lib.Taxonomy:
    """Adds embeddings to a Taxonomy.

    Args:
      taxonomy: A taxonomy object.

    Returns:
      A taxonomy object with categories and their embeddings.
    """
    logging.info('TaxonomyService: Adding embeddings to taxonomy.')

    self._postgres_client.update_task(
        self.task_id, task_lib.TaskStatus.IN_PROGRESS_GETTING_EMBEDDINGS
    )

    category_names = [category.name for category in taxonomy.categories]
    category_embeddings = self._vertex_client.get_embeddings_batch(
        category_names
    )
    for category in taxonomy.categories:
      category.embeddings = category_embeddings[category.name]
    logging.info('TaxonomyService: Added embeddings to taxonomy.')
    return taxonomy
