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

"""Tests for generate_taxonomy_embeddings."""

import os
from unittest import mock

import freezegun
from google import auth
from googleapiclient import discovery

from custom_taxonomy_classifier.api import generate_taxonomy_embeddings
from common import ai_platform_client as ai_platform_client_lib
from common import storage_client as storage_client_lib
from common import vertex_client as vertex_client_lib
from database import base_postgres_client as base_postgres_client_lib
from database import models as models_lib
from database import postgres_client as postgres_client_lib
from datamodel import task as task_lib
from services import taxonomy_service as taxonomy_service_lib
from absl.testing import absltest


class GenerateTaxonomyEmbeddingsTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self.maxDiff = None
    self._mock_getenv = self.enter_context(
        mock.patch.object(os, 'getenv', autospec=True)
    )
    self._mock_getenv.side_effect = [
        'fake_spreadsheet_id',
        'fake_worksheet',
        '1',
        'fake_task_id',
        'fake_project_id',
        'fake_region',
        'fake_service_name',
    ]

    self.enter_context(
        mock.patch.object(auth._default, 'default', autospec=True)
    )
    self.mock_base = self.enter_context(
        mock.patch.object(models_lib, 'Base', autospec=True)
    )
    self.mock_base_postgres_client = self.enter_context(
        mock.patch.object(
            base_postgres_client_lib, 'BasePostgresClient', autospec=True
        )
    )
    self.mock_discovery_build = self.enter_context(
        mock.patch.object(discovery, 'build', autospec=True)
    )
    self.mock_discovery_build.return_value = mock.MagicMock()
    self.mock_discovery_build.return_value.projects.return_value.locations.return_value.services.return_value.get.return_value.execute.return_value = {
        'template': {'containers': [{'env': []}]},
    }
    self.mock_discovery_build.return_value.projects.return_value.locations.return_value.services.return_value.patch.return_value.execute.return_value = {
        'done': True,
        'name': 'fake_operation_name',
    }
    self.mock_base_postgres_client.return_value.engine = mock.MagicMock()
    self.mock_storage_client = self.enter_context(
        mock.patch.object(storage_client_lib, 'StorageClient', autospec=True)
    )
    self.mock_vertex_client = self.enter_context(
        mock.patch.object(vertex_client_lib, 'VertexClient', autospec=True)
    )
    self.mock_postgres_client = self.enter_context(
        mock.patch.object(postgres_client_lib, 'PostgresClient', autospec=True)
    )
    self.mock_ai_platform_client = self.enter_context(
        mock.patch.object(
            ai_platform_client_lib, 'AiPlatformClient', autospec=True
        )
    )
    self.mock_taxonomy_service = self.enter_context(
        mock.patch.object(
            taxonomy_service_lib, 'TaxonomyService', autospec=True
        )
    )

  def test_create_taxonomy_embeddings_index_endpoint_updates_task_status_on_exception(
      self
    ):
    self.mock_taxonomy_service.return_value.create_taxonomy_embeddings_index_endpoint.side_effect = Exception(
        'Something went wrong.')

    generate_taxonomy_embeddings.setup_vector_search_endpoint_from_spreadsheet_data(
        'fake_spreadsheet_id',
        'fake_worksheet',
        1,
        True,
        'fake_task_id',
    )

    self.mock_postgres_client.return_value.update_task.assert_called_once_with(
        'fake_task_id', task_lib.TaskStatus.FAILED
    )

  def test_create_taxonomy_embeddings_index_endpoint(self):
    generate_taxonomy_embeddings.setup_vector_search_endpoint_from_spreadsheet_data(
        'fake_spreadsheet_id',
        'fake_worksheet',
        1,
        True,
        'fake_task_id',
    )
    self.mock_taxonomy_service.return_value.create_taxonomy_embeddings_index_endpoint.assert_called_once_with(
        'fake_spreadsheet_id', 'fake_worksheet', 1, True
    )

  @freezegun.freeze_time('2024-01-01')
  def test_restart_cloud_run_service(self):
    generate_taxonomy_embeddings.restart_cloud_run_service(
        'fake_project_id',
        'fake_region',
        'fake_service_name',
    )
    self.mock_discovery_build.return_value.projects.return_value.locations.return_value.services.return_value.patch.assert_called_once_with(
        name='projects/fake_project_id/locations/fake_region/services/fake_service_name',
        body={
            'template': {
                'containers': [{
                    'env': [{
                        'name': 'RESTART_TIME',
                        'value': '2024-01-01 00:00:00',
                    }]
                }]
            }
        },
    )


if __name__ == '__main__':
  absltest.main()
