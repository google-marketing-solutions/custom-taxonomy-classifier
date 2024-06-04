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

"""Tests for the utils module."""

from unittest import mock
import google.auth.transport.requests
import google.oauth2.id_token
import requests_mock
import tenacity
import utils
from absl.testing import absltest


class ApiUtilsTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self.mock_fetch_id_token = self.enter_context(
        mock.patch.object(
            google.oauth2.id_token, 'fetch_id_token', autospec=True
        )
    )

  @requests_mock.Mocker()
  def test_send_api_request(self, mock_requests):

    fake_params = {
        'overrides': {'container_overrides': [{'fake_override': 'value'}]}
    }

    expected_response = {
        'data': 'some data',
        'info': 'some info',
    }

    mock_requests.post(
        'https://www.googleapis.com/v1/someapi',
        json=expected_response,
    )

    actual_response = utils.send_api_request(
        url='https://www.googleapis.com/v1/someapi',
        params=fake_params,
        method='POST',
    )

    self.assertEqual(expected_response, actual_response)

    self.mock_fetch_id_token.assert_called_once_with(
        mock.ANY, 'https://www.googleapis.com/v1'
    )

  @requests_mock.Mocker()
  def test_send_api_request_raises_error_for_status(self, mock_requests):
    fake_access_token = {'access_token': 'fake_access_token'}
    mock_requests.get(
        'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token',
        json=fake_access_token,
    )

    fake_params = {
        'overrides': {'container_overrides': [{'fake_override': 'value'}]}
    }

    expected_response = {
        'data': 'some data',
        'info': 'some info',
    }

    mock_requests.post(
        'https://www.googleapis.com/v1/someapi',
        status_code=500,
        json=expected_response,
    )

    with self.assertRaises(tenacity.RetryError):
      utils.send_api_request(
          url='https://www.googleapis.com/v1/someapi',
          params=fake_params,
          method='POST',
      )


if __name__ == '__main__':
  absltest.main()
