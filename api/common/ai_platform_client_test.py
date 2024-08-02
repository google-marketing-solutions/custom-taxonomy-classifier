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

"""Test for aiplatform_client."""

import os
import random
from unittest import mock

import freezegun
from google.api_core import exceptions
import google.auth
from google.cloud import aiplatform

from common import ai_platform_client as ai_platform_client_lib
from absl.testing import absltest


_DEFAULT_INDEX_DISPLAY_NAME = 'embedding_index'
_DEFAULT_INDEX_ENDPOINT_DISPLAY_NAME = 'embedding_index_endpoint'
_DEFAULT_INDEX_DEPLOYED_DISPLAY_NAME = 'embedding_index_deployed'
_DEFAULT_MIN_REPLICA_COUNT = 1
_DEFAULT_MAX_REPLICA_COUNT = 10
_DEFAULT_MACHINE_TYPE = 'e2-standard-2'
_DEFAULT_SHARD_SIZE = 'SHARD_SIZE_SMALL'


def _get_random_768_vectors(count: int = 1):
  vectors = []
  for _ in range(count):
    vector = []
    for _ in range(768):
      vector.append(random.uniform(0, 1))
    vectors.append(vector)
  return vectors


def _get_find_neighbors_return_value(
    result_count: int = 1, neighbors_count: int = 10
):
  result = []
  for _ in range(result_count):
    neighbors = []
    for _ in range(neighbors_count):
      neighbors.append(
          aiplatform.matching_engine.matching_engine_index_endpoint.MatchNeighbor(
              id='fake_id', distance=1
          )
      )
    result.append(neighbors)
  return result


class AiplatformClientTest(absltest.TestCase):

  def setUp(self):
    super().setUp()

    self.enter_context(
        mock.patch.dict(os.environ, {'CLOUD_ML_PROJECT_ID': 'fake_project'})
    )

    self.enter_context(
        mock.patch.dict(os.environ, {'GCP_PROJECT_ID': 'fake_project'})
    )

    self.enter_context(
        mock.patch.dict(os.environ, {'GCP_REGION': 'fake_region'})
    )
    self.enter_context(
        mock.patch.dict(os.environ, {'BUCKET_NAME': 'fake_bucket_name'})
    )
    self.enter_context(
        mock.patch.dict(os.environ, {'VPC_NETWORK_ID': 'fake_network'})
    )

    self.enter_context(mock.patch.object(aiplatform, 'init', autospec=True))

    self.mock_matching_engine_index = self.enter_context(
        mock.patch.object(aiplatform, 'MatchingEngineIndex', autospec=True)
    )
    self.mock_matching_engine_endpoint = self.enter_context(
        mock.patch.object(
            aiplatform, 'MatchingEngineIndexEndpoint', autospec=True
        )
    )
    self.mock_matching_engine_endpoint.name = 'fake_name'
    self.mock_matching_engine_endpoint.display_name = (
        _DEFAULT_INDEX_ENDPOINT_DISPLAY_NAME
    )
    self.deployed_index_mock = mock.MagicMock()
    self.deployed_index_mock.id = (
        f'{_DEFAULT_INDEX_DEPLOYED_DISPLAY_NAME}_1704067200000000000'
    )
    self.deployed_index_mock.display_name = _DEFAULT_INDEX_DEPLOYED_DISPLAY_NAME

    self.deployed_index_mock.create_time = 1
    self.mock_matching_engine_endpoint.return_value.deployed_indexes = [
        self.deployed_index_mock
    ]
    self.mock_matching_engine_endpoint.return_value.match.return_value = (
        _get_find_neighbors_return_value(2)
    )
    self.mock_matching_engine_endpoint.list.return_value = [
        self.mock_matching_engine_endpoint
    ]

    self.mock_credentials = mock.create_autospec(
        google.auth.credentials.Credentials
    )
    self.mock_credentials.service_account_email = 'fake_service_account_email'
    self.mock_auth = self.enter_context(
        mock.patch.object(
            google.auth,
            'default',
            autospec=True,
            return_value=(self.mock_credentials, 'fake_project'),
        )
    )

  def test_find_neighbors_for_vectors(self):
    ai_platform_client = ai_platform_client_lib.AiPlatformClient()
    expected_vectors = _get_find_neighbors_return_value(2)
    vectors = _get_random_768_vectors(2)

    actual_vectors = ai_platform_client.find_neighbors_for_vectors(
        vectors=vectors
    )

    self.assertEqual(expected_vectors, actual_vectors)
    self.mock_matching_engine_endpoint.return_value.match.assert_called_once_with(
        deployed_index_id=(
            f'{_DEFAULT_INDEX_DEPLOYED_DISPLAY_NAME}_1704067200000000000'
        ),
        queries=vectors,
        num_neighbors=10,
    )

  def test_find_neighbors_for_vectors_endpoint_not_found_raises_error(self):
    vectors = _get_random_768_vectors(2)
    self.deployed_index_mock.display_name = 'not_found'
    self.mock_matching_engine_endpoint.return_value.deployed_indexes = [
        self.deployed_index_mock
    ]
    self.mock_matching_engine_index.list.return_value = [
        self.mock_matching_engine_endpoint
    ]
    ai_platform_client = ai_platform_client_lib.AiPlatformClient()

    with self.assertRaises(ai_platform_client_lib.NotFoundError):
      ai_platform_client.find_neighbors_for_vectors(vectors=vectors)

  @freezegun.freeze_time('2024-01-01')
  def test_create_embeddings_index(self):
    ai_platform_client = ai_platform_client_lib.AiPlatformClient()
    ai_platform_client.create_embeddings_index()

    self.mock_matching_engine_index.create_tree_ah_index.assert_called_once_with(
        display_name=_DEFAULT_INDEX_DISPLAY_NAME,
        contents_delta_uri='gs://fake_bucket_name',
        dimensions=768,
        approximate_neighbors_count=10,
        distance_measure_type='DOT_PRODUCT_DISTANCE',
        shard_size=_DEFAULT_SHARD_SIZE,
        feature_norm_type='UNIT_L2_NORM',
    )

  def test_create_embeddings_index_endpoint(self):
    ai_platform_client = ai_platform_client_lib.AiPlatformClient()
    ai_platform_client.create_embeddings_index_endpoint()

    self.mock_matching_engine_endpoint.create.assert_called_once_with(
        display_name='embedding_index_endpoint',
        network='fake_network',
    )

  @freezegun.freeze_time('2024-01-01')
  def test_deploy_embedding_index_to_endpoint(self):
    ai_platform_client = ai_platform_client_lib.AiPlatformClient()

    ai_platform_client.deploy_embedding_index_to_endpoint(
        embedding_index=self.mock_matching_engine_index,
        embedding_index_endpoint=self.mock_matching_engine_endpoint,
    )

    self.mock_matching_engine_endpoint.deploy_index.assert_called_once_with(
        index=self.mock_matching_engine_index,
        deployed_index_id='embedding_index_deployed_1704067200000000000',
        display_name='embedding_index_deployed',
        min_replica_count=_DEFAULT_MIN_REPLICA_COUNT,
        max_replica_count=_DEFAULT_MAX_REPLICA_COUNT,
        machine_type=_DEFAULT_MACHINE_TYPE,
    )

  def test_deploy_embedding_index_to_endpoint_runtime_error(self):
    ai_platform_client = ai_platform_client_lib.AiPlatformClient()

    ai_platform_client.deploy_embedding_index_to_endpoint(
        embedding_index=self.mock_matching_engine_index,
        embedding_index_endpoint=self.mock_matching_engine_endpoint,
    )

    self.mock_matching_engine_endpoint.deploy_index.side_effect = RuntimeError(
        'fake_error'
    )

    with self.assertRaises(ai_platform_client_lib.IndexCreationInProgressError):
      ai_platform_client.deploy_embedding_index_to_endpoint(
          embedding_index=self.mock_matching_engine_index,
          embedding_index_endpoint=self.mock_matching_engine_endpoint,
      )

  def test_deploy_embedding_index_to_endpoint_already_exists_error(self):
    ai_platform_client = ai_platform_client_lib.AiPlatformClient()

    ai_platform_client.deploy_embedding_index_to_endpoint(
        embedding_index=self.mock_matching_engine_index,
        embedding_index_endpoint=self.mock_matching_engine_endpoint,
    )

    self.mock_matching_engine_endpoint.deploy_index.side_effect = (
        exceptions.AlreadyExists('fake_error')
    )

    with self.assertRaises(exceptions.AlreadyExists):
      ai_platform_client.deploy_embedding_index_to_endpoint(
          embedding_index=self.mock_matching_engine_index,
          embedding_index_endpoint=self.mock_matching_engine_endpoint,
      )

  def test_find_neighbors_for_vectors_no_endpoint_raises_error(self):
    self.mock_matching_engine_endpoint.list.return_value = []
    vectors = _get_random_768_vectors(2)

    ai_platform_client = ai_platform_client_lib.AiPlatformClient()

    with self.assertRaises(ai_platform_client_lib.NotFoundError):
      ai_platform_client.find_neighbors_for_vectors(vectors=vectors)

  def test_delete_all_embedding_index_endpoints(self):
    ai_platform_client = ai_platform_client_lib.AiPlatformClient()
    ai_platform_client.delete_all_embedding_index_endpoints()

    self.mock_matching_engine_endpoint.return_value.delete.assert_called_once_with(
        force=True
    )

    self.assertIsNone(ai_platform_client.embedding_index_endpoint)
    self.assertIsNone(ai_platform_client.embedding_index_deployed_id)


if __name__ == '__main__':
  absltest.main()
