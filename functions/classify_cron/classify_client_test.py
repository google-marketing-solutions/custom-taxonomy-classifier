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

"""Tests for the classify client."""

import os
from unittest import mock
import classify_client as classify_client_lib
import utils
from absl.testing import absltest


class ClassifyTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self.mock_send_api_request = self.enter_context(
        mock.patch.object(utils, 'send_api_request', autospec=True)
    )
    self.enter_context(
        mock.patch.dict(os.environ, {'CLASSIFY_API_URL': 'fake_api_url'})
    )

  def test_classify_keywords(self):
    self.mock_send_api_request.return_value = [{
        'text': 'test1',
        'categories': [
            {'name': 'Some category', 'similarity': 0.9},
        ],
    }]
    keywords = ['test1']
    expected = {'test1': 'Some category'}
    actual = classify_client_lib.ClassifyClient().classify_keywords(keywords)
    self.assertEqual(actual, expected)
    self.mock_send_api_request.assert_called_once_with(
        'fake_api_url', {'text': ['test1']}
    )


if __name__ == '__main__':
  absltest.main()
