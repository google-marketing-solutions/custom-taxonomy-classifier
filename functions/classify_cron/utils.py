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

import os
from typing import Any
import google.auth.transport.requests
import google.oauth2.id_token
import requests
import tenacity


def _get_header(audience: str) -> dict[str, str]:
  """Retrieves ID token from the google-auth client library.

  Args:
    audience: The target audience.

  Returns:
    The header.
  """
  auth_req = google.auth.transport.requests.Request()
  id_token = google.oauth2.id_token.fetch_id_token(auth_req, audience)

  headers = {'Authorization': f'Bearer {id_token}'}
  return headers


@tenacity.retry(
    retry=tenacity.retry_if_exception_type(requests.exceptions.HTTPError),
    wait=tenacity.wait_exponential(min=3, multiplier=2, max=10),
    reraise=False,
    stop=tenacity.stop_after_attempt(5),
)
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

  Raises:
    HTTPError: If the response was not ok.
  """
  audience = os.path.dirname(url)
  headers = _get_header(audience)
  response = requests.request(
      url=url, method=method, json=params, headers=headers
  )

  if not response.ok:
    response.raise_for_status()

  return response.json()
