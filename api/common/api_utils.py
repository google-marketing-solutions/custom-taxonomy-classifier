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

"""Common utilities for Google REST HTTP clients."""

from typing import Any

from absl import logging
import requests

_METADATA_URL = 'http://metadata.google.internal/computeMetadata/v1/'
_METADATA_HEADERS = {'Metadata-Flavor': 'Google'}
_SERVICE_ACCOUNT = 'default'


def _get_header() -> dict[str, str]:
  """Retrieves access token from the metadata server.

  Returns:
      The access token.
  """
  url = f'{_METADATA_URL}instance/service-accounts/{_SERVICE_ACCOUNT}/token'

  # Request an access token from the metadata server.
  r = requests.get(url, headers=_METADATA_HEADERS)
  r.raise_for_status()

  # Extract the access token from the response.
  access_token = r.json()['access_token']
  headers = {'Authorization': f'Bearer {access_token}'}
  return headers


def send_api_request(
    url: str,
    params: dict[str, Any] | None,
    method: str = 'POST',
) -> Any:
  """Call the requested API endpoint with the given parameters.

  Args:
    url: The API endpoint to call.
    params: The parameters to pass into the API call.
    method: The request method to use.

  Returns:
    The JSON data from the response (this can sometimes be a list or dictionary,
      depending on the API used).
  """
  headers = _get_header()
  response = requests.request(
      url=url, method=method, json=params, headers=headers
  )

  if not response.ok:
    logging.error('%s Caught: %s', response.status_code, response.json())
    response.raise_for_status()

  return response.json()
