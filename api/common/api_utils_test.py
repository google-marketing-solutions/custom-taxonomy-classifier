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

"""Tests for the api_utils module."""

import requests
import requests_mock
from common import api_utils
from absl.testing import absltest


class ApiUtilsTest(absltest.TestCase):

  @requests_mock.Mocker()
  def test_send_api_request(self, mock_requests):
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
        json=expected_response,
    )

    actual_response = api_utils.send_api_request(
        url='https://www.googleapis.com/v1/someapi',
        params=fake_params,
        method='POST',
    )

    self.assertEqual(expected_response, actual_response)

  @requests_mock.Mocker()
  def test_get_header_request_raises_error_for_status(self, mock_requests):

    fake_params = {
        'overrides': {'container_overrides': [{'fake_override': 'value'}]}
    }

    expected_response = {
        'data': 'some data',
        'info': 'some info',
    }

    mock_requests.get(
        'http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token',
        status_code=500,
        json=expected_response,
    )

    with self.assertRaises(requests.HTTPError):
      api_utils.send_api_request(
          url='https://www.googleapis.com/v1/someapi',
          params=fake_params,
          method='POST',
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

    with self.assertRaises(requests.HTTPError):
      api_utils.send_api_request(
          url='https://www.googleapis.com/v1/someapi',
          params=fake_params,
          method='POST',
      )


if __name__ == '__main__':
  absltest.main()
