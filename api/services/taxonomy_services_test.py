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

"""Tests for taxonomy service."""

from unittest import mock
import google.auth
import gspread
from common import ai_platform_client as ai_platform_client_lib
from common import storage_client as storage_client_lib
from common import vertex_client as vertex_client_lib
from database import postgres_client as postgres_client_lib
from datamodel import category as category_lib
from datamodel import task as task_lib
from datamodel import taxonomy as taxonomy_lib
from services import taxonomy_service as taxonomy_service_lib
from absl.testing import absltest
from absl.testing import parameterized


_FAKE_SPREADSHEET_ID = 'fake_spreadsheet_id'
_FAKE_WORKSHEET_NAME = 'fake_worksheet_name'
_FAKE_COLUMN_ID = 'fake_column_id'
_FAKE_TASK_ID = 'fake_task_id'


class TaxonomyServiceTest(parameterized.TestCase):

  def setUp(self):
    super().setUp()
    self.maxDiff = None
    self._postgres_client = mock.create_autospec(
        postgres_client_lib.PostgresClient,
        instance=True,
        spec_set=True,
    )

    self._storage_client = mock.create_autospec(
        storage_client_lib.StorageClient, instance=True, spec_set=True
    )

    self._ai_platform_client = mock.create_autospec(
        ai_platform_client_lib.AiPlatformClient, instance=True, spec_set=True
    )

    self._vertex_client = mock.create_autospec(
        vertex_client_lib.VertexClient, instance=True, spec_set=True
    )
    self._vertex_client.get_embeddings_batch.return_value = {
        'fake_category_1': [0.1],
        'fake_category_2': [0.2],
    }

    self._sheet = mock.MagicMock()
    self._worksheet = mock.MagicMock()
    self._worksheet.col_values.return_value = [
        'fake_header',
        'fake_category_1',
        'fake_category_2',
    ]
    self._sheet.worksheet.return_value = self._worksheet

    self.enter_context(
        mock.patch.object(
            google.auth,
            'default',
            autospec=True,
            return_value=(mock.MagicMock(), mock.MagicMock()),
        )
    )
    self._gspread_mock = self.enter_context(
        mock.patch.object(gspread, 'authorize', autospec=True)
    )
    self._gspread_mock.return_value.open_by_key.return_value = self._sheet
    self._gspread_mock.return_value.open_by_key.return_value.worksheet.return_value = (
        self._worksheet
    )

  def test_taxonomy_service_init(self):
    taxonomy_service_lib.TaxonomyService(
        self._postgres_client,
        self._vertex_client,
        self._storage_client,
        self._ai_platform_client,
        _FAKE_TASK_ID,
    )

    self._postgres_client.add_task.assert_called_once_with(_FAKE_TASK_ID)

  def test_add_embeddings_to_taxonomy(self):
    taxonomy_without_embeddings = taxonomy_lib.Taxonomy(
        entity_id=_FAKE_TASK_ID,
        categories=[
            category_lib.Category(name='fake_category_1'),
            category_lib.Category(name='fake_category_2'),
        ],
    )
    expected = taxonomy_lib.Taxonomy(
        entity_id=_FAKE_TASK_ID,
        categories=[
            category_lib.Category(name='fake_category_1', embeddings=[0.1]),
            category_lib.Category(name='fake_category_2', embeddings=[0.2]),
        ],
    )
    actual = taxonomy_service_lib.TaxonomyService(
        self._postgres_client,
        self._vertex_client,
        self._storage_client,
        self._ai_platform_client,
        _FAKE_TASK_ID,
    )._add_embeddings_to_taxonomy(taxonomy_without_embeddings)

    for actual_category, expected_category in zip(
        actual.categories, expected.categories
    ):
      self.assertEqual(actual_category.name, expected_category.name)
      self.assertEqual(actual_category.embeddings, expected_category.embeddings)

  @parameterized.named_parameters(
      dict(
          testcase_name='with_headers',
          headers=True,
          expected=taxonomy_lib.Taxonomy(
              entity_id='fake_task_id',
              categories=[
                  category_lib.Category(name='fake_category_1'),
                  category_lib.Category(name='fake_category_2'),
              ],
          ),
      ),
      dict(
          testcase_name='no_headers',
          headers=False,
          expected=taxonomy_lib.Taxonomy(
              entity_id='fake_task_id',
              categories=[
                  category_lib.Category(name='fake_header'),
                  category_lib.Category(name='fake_category_1'),
                  category_lib.Category(name='fake_category_2'),
              ],
          ),
      ),
  )
  def test_get_embeddings_from_spreadsheet(self, headers, expected):
    actual = taxonomy_service_lib.TaxonomyService(
        self._postgres_client,
        self._vertex_client,
        self._storage_client,
        self._ai_platform_client,
        _FAKE_TASK_ID,
    )._get_taxonomy_from_spreadsheet(
        _FAKE_SPREADSHEET_ID, _FAKE_WORKSHEET_NAME, _FAKE_COLUMN_ID, headers
    )

    for actual_category, expected_category in zip(
        actual.categories, expected.categories
    ):
      self.assertEqual(actual_category.name, expected_category.name)

    self._gspread_mock.return_value.open_by_key.assert_called_once_with(
        _FAKE_SPREADSHEET_ID
    )
    self._gspread_mock.return_value.open_by_key.return_value.worksheet.assert_called_once_with(
        _FAKE_WORKSHEET_NAME
    )
    self._gspread_mock.return_value.open_by_key.return_value.worksheet.return_value.col_values.assert_called_once_with(
        _FAKE_COLUMN_ID
    )

  def test_create_taxonomy_embeddings_index_endpoint(self):
    taxonomy_service_lib.TaxonomyService(
        self._postgres_client,
        self._vertex_client,
        self._storage_client,
        self._ai_platform_client,
        _FAKE_TASK_ID,
    ).create_taxonomy_embeddings_index_endpoint(
        _FAKE_SPREADSHEET_ID, _FAKE_WORKSHEET_NAME, _FAKE_COLUMN_ID, True
    )

    taxonomy_with_embeddings = taxonomy_lib.Taxonomy(
        entity_id=_FAKE_TASK_ID,
        categories=[
            category_lib.Category(
                id='0', name='fake_category_1', embeddings=[0.1],
            ),
            category_lib.Category(
                id='1', name='fake_category_2', embeddings=[0.2]),
        ],
    )
    self._vertex_client.get_embeddings_batch.assert_called_once_with(
        ['fake_category_1', 'fake_category_2']
    )
    self._storage_client.write_taxonomy_embeddings.assert_called_once_with(
        taxonomy_with_embeddings
    )
    self._ai_platform_client.create_embeddings_index.assert_called_once_with()
    self._ai_platform_client.create_embeddings_index_endpoint.assert_called_once_with()
    self._ai_platform_client.deploy_embedding_index_to_endpoint.assert_called_once()
    self._ai_platform_client.delete_all_embedding_index_endpoints.assert_called_once()

    self._postgres_client.add_task.assert_called_once_with(_FAKE_TASK_ID)

    mock_update_task_calls = [
        mock.call(
            _FAKE_TASK_ID, task_lib.TaskStatus.IN_PROGRESS_GETTING_EMBEDDINGS
        ),
        mock.call(
            _FAKE_TASK_ID,
            task_lib.TaskStatus.IN_PROGRESS_WRITING_EMBEDDINGS_TO_GCS
        ),
        mock.call(
            _FAKE_TASK_ID,
            task_lib.TaskStatus.IN_PROGRESS_CREATING_EMBEDDINGS_INDEX
        ),
        mock.call(
            _FAKE_TASK_ID,
            task_lib.TaskStatus.IN_PROGRESS_CREATING_EMBEDDINGS_INDEX_ENDPOINT
        ),
        mock.call(
            _FAKE_TASK_ID,
            task_lib.TaskStatus.IN_PROGRESS_DEPLOYING_EMBEDDINGS_INDEX_TO_ENDPOINT
        ),
        mock.call(
            _FAKE_TASK_ID, task_lib.TaskStatus.SUCCEEDED
        ),
    ]

    self._postgres_client.update_task.assert_has_calls(mock_update_task_calls)


if __name__ == '__main__':
  absltest.main()
