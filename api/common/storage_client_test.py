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

"""Tests for storage_client."""

import os
from unittest import mock

import google.auth
from google.cloud import exceptions
from google.cloud import storage

from common import storage_client as storage_client_lib
from datamodel import category as category_lib
from datamodel import taxonomy as taxonomy_lib
from absl.testing import absltest

_FAKE_BUCKET_NAME = 'fake_bucket_name'

_FAKE_CATEGORY_1 = category_lib.Category(
    id='1',
    name='fake_category_name_1',
    embeddings=[0.1, 0.2, 0.3],
)
_FAKE_CATEGORY_2 = category_lib.Category(
    id='2',
    name='fake_category_name_2',
    embeddings=[0.1, 0.2, 0.3],
)
_FAKE_TAXONOMY = taxonomy_lib.Taxonomy(
    categories=[_FAKE_CATEGORY_1, _FAKE_CATEGORY_2]
)

_EXPECTED_JSON_FILE_CONTENTS = '{"id":"fake_category_name_1","embedding":[0.1,0.2,0.3]}\n{"id":"fake_category_name_2","embedding":[0.1,0.2,0.3]}'


class StorageClientTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self.enter_context(
        mock.patch.dict(os.environ, {'BUCKET_NAME': 'fake_bucket_name'})
    )
    self.mock_credentials = mock.create_autospec(
        google.auth.credentials.Credentials
    )
    self.mock_credentials.service_account_email = 'fake_service_account_email'
    self.mock_auth = self.enter_context(
        mock.patch.object(
            google.auth,
            'default',
            autospec=True,
            return_value=(self.mock_credentials, ''),
        )
    )
    self.storage_client_mock = self.enter_context(
        mock.patch.object(storage, 'Client', autospec=True)
    )
    self.mock_bucket = mock.create_autospec(storage.Bucket)
    self.mock_blob = mock.create_autospec(storage.Blob, spec_set=True)
    self.mock_bucket.return_value = self.mock_blob
    self.mock_bucket.blob.return_value = self.mock_blob
    self.mock_bucket.name = _FAKE_BUCKET_NAME
    self.storage_client_mock.return_value.bucket.return_value = self.mock_bucket

  def test_write_taxonomy_embeddings(self):
    client = storage_client_lib.StorageClient()
    client.write_taxonomy_embeddings(_FAKE_TAXONOMY)

    self.mock_blob.upload_from_string.assert_has_calls([
        mock.call(
            data=_EXPECTED_JSON_FILE_CONTENTS,
            content_type='application/octet-stream',
        )
    ])

  def test_write_taxonomy_embeddings_raises_error(self):
    self.mock_blob.upload_from_string.side_effect = exceptions.ClientError(
        'Could not write files to GCS bucket fake_bucket_name.'
    )
    client = storage_client_lib.StorageClient()

    with self.assertRaises(storage_client_lib.WriteTaxonomyError):
      client.write_taxonomy_embeddings(_FAKE_TAXONOMY)


if __name__ == '__main__':
  absltest.main()
