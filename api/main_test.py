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

import datetime
import os
from unittest import mock
import uuid

from fastapi import testclient
from google import auth

import main
from common import ai_platform_client as ai_platform_client_lib
from common import api_utils
from common import vertex_client as vertex_client_lib
from database import base_postgres_client as base_postgres_client_lib
from database import models as models_lib
from database import postgres_client as postgres_client_lib
from services import classify_service as classify_service_lib
from absl.testing import absltest


_TEST_CLASSIFY_RESPONSE_SUCCESS = [
    {
        'text': 'foobar',
        'media_uri': None,
        'media_description': None,
        'categories': [
            {'name': 'category_1', 'similarity': 0.98},
            {'name': 'category_2', 'similarity': 0.89},
        ],
        'embedding': [0.1, 0.2, 0.3],
    },
]

_TEST_CLASSIFY_RESPONSE_SUCCESS_NO_EMBEDDINGS = [
    {
        'text': 'foobar',
        'media_uri': None,
        'media_description': None,
        'categories': [
            {'name': 'category_1', 'similarity': 0.98},
            {'name': 'category_2', 'similarity': 0.89},
        ],
        'embedding': None,
    },
]

_TEST_CLASSIFY_RESPONSE_ERROR = {
    'detail': 'The server could not process the request.',
}

_TEST_GET_TASK_STATUS_RESPONSE_SUCCESS = {
    'task_id': 'fake_task_id',
    'status': 'SUCCEEDED',
    'time_created': '2024-01-01T00:00:00+00:00',
    'time_updated': '2024-01-01T00:00:00+00:00',
}

_TEST_GET_TASK_STATUS_RESPONSE_NOT_EXIST = {
    'task_id': 'fake_task_id',
    'status': 'NOT_FOUND',
    'time_created': None,
    'time_updated': None,
}

_TEST_OVERRIDE_SPECS = {
    'overrides': {
        'container_overrides': [
            {
                'env': [
                    {
                        'name': 'SPREADSHEET_ID',
                        'value': 'fake_spreadsheet_id',
                    },
                    {
                        'name': 'WORKSHEET_NAME',
                        'value': 'fake_worksheet_name',
                    },
                    {
                        'name': 'WORKSHEET_COL_INDEX',
                        'value': 'fake_worksheet_col_index',
                    },
                    {'name': 'HEADER', 'value': 'True'},
                    {'name': 'TASK_ID', 'value': 'fake_task_id'},
                ]
            },
        ]
    }
}


class MainTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
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
    self.mock_base_postgres_client.return_value.engine = mock.MagicMock()
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
    self.mock_classify_service = self.enter_context(
        mock.patch.object(
            classify_service_lib, 'ClassifyService', autospec=True
        )
    )
    self.mock_classify_service.return_value.taxonomy_embeddings = {
        'fake_category': [0.1]
    }
    self.mock_send_api_request = self.enter_context(
        mock.patch.object(api_utils, 'send_api_request', autospec=True)
    )
    self.enter_context(
        mock.patch.dict(os.environ, {'TAXONOMY_JOB_URL': 'fake_run_url'})
    )

  def test_root(self):
    client = testclient.TestClient(main.app)
    response = client.get('/')
    self.assertEqual(response.status_code, 200)
    self.assertEqual(response.json(), {'message': 'Welcome to Classify API!!!'})

  def test_startup(self):
    with testclient.TestClient(main.app):
      self.mock_postgres_client.assert_called_once()
      self.mock_vertex_client.assert_called_once()
      self.mock_ai_platform_client.assert_called_once()

      self.mock_classify_service.assert_called_once_with(
          self.mock_postgres_client.return_value,
          self.mock_vertex_client.return_value,
          self.mock_ai_platform_client.return_value,
      )
      self.mock_base_postgres_client.return_value.create_tables_if_not_exist.assert_called_once_with()

  def test_classify_service(self):
    self.mock_classify_service.return_value.classify.return_value = [
        {
            'text': 'foobar',
            'categories': [
                {'name': 'category_1', 'similarity': 0.98},
                {'name': 'category_2', 'similarity': 0.89},
            ],
            'embedding': [0.1, 0.2, 0.3],
        },
    ]
    with testclient.TestClient(main.app) as client:
      actual = client.post(
          '/classify', json={'text': 'foobar', 'embeddings': True}
      )

      self.assertEqual(actual.status_code, 200)
      self.assertListEqual(actual.json(), _TEST_CLASSIFY_RESPONSE_SUCCESS)

  def test_classify_service_use_vector_search(self):
    self.mock_classify_service.return_value.classify.return_value = [
        {
            'text': 'foobar',
            'categories': [
                {'name': 'category_1', 'similarity': 0.98},
                {'name': 'category_2', 'similarity': 0.89},
            ],
            'embedding': [0.1, 0.2, 0.3],
        },
    ]
    with testclient.TestClient(main.app) as client:
      actual = client.post(
          '/classify', json={'text': 'foobar', 'embeddings': True}
      )
      self.mock_classify_service.return_value.classify.assert_called_once_with(
          'foobar', None, True
      )
      self.assertEqual(actual.status_code, 200)
      self.assertListEqual(actual.json(), _TEST_CLASSIFY_RESPONSE_SUCCESS)

  def test_classify_service_with_list(self):
    self.mock_classify_service.return_value.classify.return_value = [
        {
            'text': 'foobar',
            'categories': [
                {'name': 'category_1', 'similarity': 0.98},
                {'name': 'category_2', 'similarity': 0.89},
            ],
        },
    ]

    with testclient.TestClient(main.app) as client:
      response = client.post('/classify', json={'text': ['foobar']})

      self.assertEqual(response.status_code, 200)
      self.assertListEqual(
          response.json(), _TEST_CLASSIFY_RESPONSE_SUCCESS_NO_EMBEDDINGS
      )

  def test_classify_service_with_medias(self):
    self.mock_classify_service.return_value.classify.return_value = [
        {
            'text': 'foobar',
            'categories': [
                {'name': 'category_1', 'similarity': 0.98},
                {'name': 'category_2', 'similarity': 0.89},
            ],
        },
    ]
    with testclient.TestClient(main.app) as client:
      response = client.post('/classify', json={'media_uri': ['foobar']})

      self.assertEqual(response.status_code, 200)
      self.assertListEqual(
          response.json(), _TEST_CLASSIFY_RESPONSE_SUCCESS_NO_EMBEDDINGS
      )

  def test_classify_service_with_error(self):
    self.mock_classify_service.return_value.classify.return_value = (
        _TEST_CLASSIFY_RESPONSE_ERROR
    )
    self.mock_classify_service.return_value.classify.side_effect = Exception(
        'An error occurred.'
    )
    with testclient.TestClient(main.app) as client:
      response = client.post('/classify', json={'text': 'foobar'})
      self.assertEqual(response.status_code, 500)
      self.assertDictEqual(response.json(), _TEST_CLASSIFY_RESPONSE_ERROR)

  @mock.patch.object(uuid, 'uuid4', autospec=True, return_value='fake_task')
  async def test_generate_taxonomy_embeddings(self, uuid_mock):
    del uuid_mock  # Unused.
    with testclient.TestClient(main.app) as client:
      response = await client.post(
          '/generate_taxonomy_embeddings',
          json={
              'spreadsheet_id': 'fake_spreadsheet_id',
              'worksheet_name': 'fake_worksheet_name',
              'worksheet_col_index': 'fake_worksheet_col_index',
          },
      )
      self.mock_send_api_request.assert_called_once_with(
          'fake_run_url', _TEST_OVERRIDE_SPECS
      )

      self.assertEqual(response.status_code, 201)
      self.assertDictEqual(
          response.json(),
          {
              'task_id': 'fake_task',
              'message': (
                  'Generate Taxonomy Embeddings task sent in the background.'
              ),
          },
      )

  def test_get_task_status(self):
    fake_task_id = 'fake_task_id'
    fake_datetime = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)

    self.mock_postgres_client.return_value.get_task_status.return_value = {
        'task_id': fake_task_id,
        'status': 'SUCCEEDED',
        'time_created': fake_datetime,
        'time_updated': fake_datetime,
    }
    with testclient.TestClient(main.app) as client:
      response = client.get(f'/task_status/{fake_task_id}')
      self.assertEqual(response.status_code, 200)
      self.assertDictEqual(
          response.json(), _TEST_GET_TASK_STATUS_RESPONSE_SUCCESS
      )

  def test_get_task_status_not_exist(self):
    self.mock_postgres_client.return_value.get_task_status.return_value = {
        'task_id': 'fake_task_id',
        'status': 'NOT_FOUND',
    }
    with testclient.TestClient(main.app) as client:
      response = client.get('/task_status/fake_task_id')

      self.assertDictEqual(
          response.json(), _TEST_GET_TASK_STATUS_RESPONSE_NOT_EXIST
      )


if __name__ == '__main__':
  absltest.main()
