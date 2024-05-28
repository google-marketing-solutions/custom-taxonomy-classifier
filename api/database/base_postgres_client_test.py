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

"""Tests for base_postgres_client."""

import os
from unittest import mock
import sqlalchemy
from custom_taxonomy_classifier.api.database import base_postgres_client
from custom_taxonomy_classifier.api.database import errors
from custom_taxonomy_classifier.api.database import models as models_lib
from absl.testing import absltest


_FAKE_PROJECT = 'fake-project'
_FAKE_REGION = 'fake-region'
_FAKE_DB_NAME = 'fake-database'
_FAKE_INSTANCE_HOST = 'fake-ip'
_FAKE_INSTANCE_PORT = '3306'
_FAKE_DB_USER = 'fake-db-user'
_FAKE_DB_PASSWORD = 'fake-db-password'


class BasePostgresClientTest(absltest.TestCase):

  def setUp(self):
    super().setUp()

    self.mock_engine = self.enter_context(
        mock.patch.object(sqlalchemy, 'create_engine', autospec=True)
    )
    self.enter_context(
        mock.patch.dict(os.environ, {'GCP_PROJECT_ID': _FAKE_PROJECT})
    )
    self.enter_context(
        mock.patch.dict(os.environ, {'GCP_REGION': _FAKE_REGION})
    )
    self.enter_context(
        mock.patch.dict(
            os.environ, {'POSTGRES_INSTANCE_HOST': _FAKE_INSTANCE_HOST}
        )
    )
    self.enter_context(
        mock.patch.dict(
            os.environ, {'POSTGRES_INSTANCE_PORT': _FAKE_INSTANCE_PORT}
        )
    )
    self.enter_context(
        mock.patch.dict(os.environ, {'POSTGRES_DB_USER': _FAKE_DB_USER})
    )
    self.enter_context(
        mock.patch.dict(os.environ, {'POSTGRES_DB_PASSWORD': _FAKE_DB_PASSWORD})
    )
    self.enter_context(
        mock.patch.dict(os.environ, {'POSTGRES_DB_NAME': _FAKE_DB_NAME})
    )

  def test_init(self):
    base_postgres_client.BasePostgresClient()
    expected_connection_url = sqlalchemy.engine.url.URL.create(
        drivername='postgresql+pg8000',
        username=_FAKE_DB_USER,
        password=_FAKE_DB_PASSWORD,
        host=_FAKE_INSTANCE_HOST,
        port=_FAKE_INSTANCE_PORT,
        database=_FAKE_DB_NAME,
    )

    self.mock_engine.assert_called_once_with(
        expected_connection_url,
        pool_size=25,
        max_overflow=5,
        echo_pool=True,
        pool_timeout=60,
        pool_recycle=1200,
    )

  @mock.patch.object(
      models_lib.Base.metadata,
      'create_all',
      autospec=True,
  )
  def test_create_tables_if_not_exist(self, mock_create_all):

    client = base_postgres_client.BasePostgresClient()
    client.create_tables_if_not_exist()

    mock_create_all.assert_called_once_with(client.engine)

  @mock.patch.object(
      models_lib.Base.metadata,
      'create_all',
      autospec=True,
  )
  def test_create_tables_if_not_exist_raises_api_error(self, mock_create_all):

    mock_create_all.side_effect = sqlalchemy.exc.DBAPIError(
        'fake-error', 'fake-params', 'fake-orig'
    )

    with self.assertRaises(errors.BasePostgresClientError):
      client = base_postgres_client.BasePostgresClient()
      client.create_tables_if_not_exist()

  @mock.patch.object(
      models_lib.Base.metadata,
      'create_all',
      autospec=True,
  )
  def test_create_tables_if_not_exist_raises_database_error(
      self, mock_create_all
  ):

    mock_create_all.side_effect = sqlalchemy.exc.DatabaseError(
        'fake-error', 'fake-params', 'fake-orig'
    )

    with self.assertRaises(errors.BasePostgresClientError):
      client = base_postgres_client.BasePostgresClient()
      client.create_tables_if_not_exist()


if __name__ == '__main__':
  absltest.main()
