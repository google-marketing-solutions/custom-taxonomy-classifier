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

"""Tests for postgres_client."""

import datetime
from unittest import mock
import freezegun
from google.cloud.sql.connector import connector
import pandas as pd
import sqlalchemy
from database import errors
from database import postgres_client as postgres_client_lib
from absl.testing import absltest


class TestPostgresClient(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self.mock_connector = self.enter_context(
        mock.patch.object(connector, 'Connector', autospec=True)
    )
    self.mock_connector.return_value.connect.return_value = mock.MagicMock()

    self.mock_engine = self.enter_context(
        mock.patch.object(sqlalchemy, 'create_engine', autospec=True)
    )
    self.mock_engine.return_value = mock.MagicMock()
    self.mock_execution = mock.MagicMock()
    self.mock_to_sql = self.enter_context(
        mock.patch.object(pd.DataFrame, 'to_sql', autospec=True)
    )

  def test_get_task_status(self):
    fake_task_id = 'fake_task_id'
    fake_datetime = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    self.mock_execution.fetchall.return_value = [
        (fake_task_id, 'SUCCEEDED', fake_datetime, fake_datetime),
    ]
    self.mock_engine.return_value.connect().__enter__.return_value.execute.return_value = (
        self.mock_execution
    )
    expected = {
        'task_id': fake_task_id,
        'status': 'SUCCEEDED',
        'time_created': fake_datetime,
        'time_updated': fake_datetime,
    }
    actual = postgres_client_lib.PostgresClient(
        self.mock_engine.return_value
    ).get_task_status(fake_task_id)
    self.assertDictEqual(actual, expected)

  def test_get_task_status_not_found(self):
    fake_task_id = 'fake_task_id'
    self.mock_execution.fetchall.return_value = []
    self.mock_engine.return_value.connect().__enter__.return_value.execute.return_value = (
        self.mock_execution
    )
    expected = {
        'task_id': fake_task_id,
        'status': 'NOT_FOUND',
    }
    actual = postgres_client_lib.PostgresClient(
        self.mock_engine.return_value
    ).get_task_status(fake_task_id)
    self.assertDictEqual(actual, expected)

  def test_get_task_status_raises_error(self):
    fake_task_id = 'fake_task_id'
    fake_datetime = datetime.datetime(2024, 1, 1, tzinfo=datetime.timezone.utc)
    self.mock_execution.fetchall.return_value = [
        (fake_task_id, 'SUCCEEDED', fake_datetime, fake_datetime),
    ]
    self.mock_engine.return_value.connect().__enter__.return_value.execute.side_effect = sqlalchemy.exc.DatabaseError(
        'fake-error', 'fake-params', 'fake-orig'
    )
    client = postgres_client_lib.PostgresClient(self.mock_engine.return_value)

    with self.assertRaises(errors.PostgresClientError):
      client.get_task_status(fake_task_id)

  def test_add_task(self):
    client = postgres_client_lib.PostgresClient(self.mock_engine.return_value)
    client.add_task('fake_task_id')

    self.mock_engine.return_value.connect().__enter__.return_value.execute.assert_called_once()
    self.mock_engine.return_value.connect().__enter__.return_value.commit.assert_called_once()

  def test_add_task_raises_dataase_rror(self):
    self.mock_engine.return_value.connect().__enter__.return_value.execute.side_effect = sqlalchemy.exc.DatabaseError(
        'fake-error', 'fake-params', 'fake-orig'
    )
    client = postgres_client_lib.PostgresClient(self.mock_engine.return_value)

    with self.assertRaises(errors.PostgresClientError):
      client.add_task('fake_task_id')

  @freezegun.freeze_time('2024-01-01')
  def test_add_task_integrity_error_resets_status(self):
    self.mock_engine.return_value.connect().__enter__.return_value.execute.side_effect = [
        sqlalchemy.exc.IntegrityError('fake-error', 'fake-params', 'fake-orig'),
        None,
    ]
    client = postgres_client_lib.PostgresClient(self.mock_engine.return_value)
    client.add_task('fake_task_id')

    self.mock_engine.return_value.connect().__enter__.return_value.execute.assert_has_calls([
        mock.call(
            statement=mock.ANY,
            parameters={
                'task_id': 'fake_task_id',
                'status': 'STARTED',
            },
        ),
        mock.call(
            statement=mock.ANY,
            parameters={
                'task_id': 'fake_task_id',
                'status': 'STARTED',
                'time_updated': datetime.datetime(
                    2024, 1, 1, 0, 0, 0, tzinfo=datetime.timezone.utc
                ),
            },
        ),
    ])


if __name__ == '__main__':
  absltest.main()
