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

"""A client to make calls to AI Platform API."""

import os
import time

from absl import logging
from google.api_core import exceptions
import google.auth
from google.cloud import aiplatform


_DEFAULT_INDEX_DISPLAY_NAME = 'embedding_index'
_DEFAULT_INDEX_ENDPOINT_DISPLAY_NAME = 'embedding_index_endpoint'
_DEFAULT_INDEX_DEPLOYED_DISPLAY_NAME = 'embedding_index_deployed'
_DEFAULT_NUM_NEIGHBORS = 10
_DEFAULT_MIN_REPLICA_COUNT = 1
_DEFAULT_MAX_REPLICA_COUNT = 10
_DEFAULT_MACHINE_TYPE = 'e2-standard-2'
_DEFAULT_SHARD_SIZE = 'SHARD_SIZE_SMALL'

_MatchNeighbor = (
    aiplatform.matching_engine.matching_engine_index_endpoint.MatchNeighbor
)


class Error(Exception):
  pass


class IndexCreationInProgressError(Error):
  pass


class NotFoundError(Error):
  pass


class AiPlatformClient:
  """A client to make requests to the AI Platform API.

  Example usage:
    aiplatform_client = AiPlatformClient()

    # Creates the embeddings index
    embeddings_index = aiplatform_client.create_embeddings_index()

    # Creates the embedding index endpoint
    embeddings_index_endpoint =
      aiplatform_client.create_embeddings_index_endpoint()

    # Deploys the embedding index to the endpoint
    aiplatform_client.deploy_embedding_index_to_endpoint(
        embeddings_index, embeddings_index_endpoint)

  Refs:
    https://cloud.google.com/vertex-ai/docs/vector-search/quickstart
    https://cloud.google.com/python/docs/reference/aiplatform/latest/google.cloud.aiplatform
  """

  def __init__(self) -> None:
    """Initializes the AI Platform client."""
    credentials, project = google.auth.default()
    aiplatform.init(
        project=project,
        location=os.environ['GCP_REGION'],
        credentials=credentials,
    )
    self._bucket_name = os.environ['BUCKET_NAME']
    self._vpc_network_id = os.environ['VPC_NETWORK_ID']
    self.embedding_index_endpoint = self._getembedding_index_endpoint()
    self.embedding_index_deployed_id = (
        self._getembedding_index_endpoint_deployed_index_id(
            self.embedding_index_endpoint
        )
    )

    logging.info('AiPlatform Client: Initialized')

  def find_neighbors_for_vectors(
      self,
      vectors: list[list[float]],
      num_neighbors: int = _DEFAULT_NUM_NEIGHBORS,
  ) -> list[list[_MatchNeighbor]] | None:
    """Finds nearest neighbors for a list of embedding vectors.

    Args:
      vectors: A list of embedding vectors.
      num_neighbors: The number of neighbors.

    Returns:
      A list of 10 nearest neighbors for each vector in vectors.

    Raises:
      NotFoundError: If the matching index endpoint has no deployments.
    """
    if not self.embedding_index_endpoint:
      logging.error('AiPlatform Client: No index endpoint found.')
      raise NotFoundError('AiPlatform Client: No index endpoint found.')
    logging.info(
        'AiPlatform Client: Running query with embedding index endpoint: %s',
        self.embedding_index_endpoint.display_name,
    )
    if not self.embedding_index_deployed_id:
      logging.error(
          'AiPlatform Client: No index deployed at the chosen endpoint.'
      )
      raise NotFoundError(
          'AiPlatform Client: No index deployed at the chosen endpoint.'
      )
    response = self.embedding_index_endpoint.match(
        deployed_index_id=self.embedding_index_deployed_id,
        queries=vectors,
        num_neighbors=num_neighbors,
    )
    logging.info(
        'AiPlatform Client: Got response from embedding index endpoint: %s',
        response,
    )
    return response

  def _getembedding_index_endpoint_deployed_index_id(
      self,
      embedding_index_endpoint: aiplatform.MatchingEngineIndexEndpoint,
      embedding_index_deployed_display_name: str = _DEFAULT_INDEX_DEPLOYED_DISPLAY_NAME,
  ) -> str | None:
    """Get the last deployed index id for an endpoint.

    Args:
      embedding_index_endpoint: The AI Platform MatchingEngineIndexEndpoint.
      embedding_index_deployed_display_name: The deployed index display names to
        look for.

    Returns:
      The ID of the latest deployed index on the passed endpoint.
    """
    if not embedding_index_endpoint:
      logging.warning(
          'AiPlatform Client: No index endpoint found on initialization.'
      )
      return None
    deployed_indexes = embedding_index_endpoint.deployed_indexes
    for deployed_index in sorted(
        deployed_indexes, key=lambda c: c.create_time, reverse=True
    ):
      if deployed_index.display_name == embedding_index_deployed_display_name:
        logging.info(
            'AiPlatform Client: Last deployed index has id: %s',
            deployed_index.id,
        )
        return str(deployed_index.id)
    logging.warning(
        'AiPlatform Client: Could not find a deployed index with display'
        ' name %s',
        embedding_index_deployed_display_name,
    )

  def _getembedding_index_endpoint(
      self,
      embedding_index_endpoint_display_name: str = _DEFAULT_INDEX_ENDPOINT_DISPLAY_NAME,
  ) -> aiplatform.MatchingEngineIndexEndpoint:
    """Get the embedding index endpoint.

    Args:
      embedding_index_endpoint_display_name: The AI Platform
        MatchingEngineIndexEndpoint display name.

    Returns:
      An AI Platform MatchingEngineIndexEndpoint resource.
    """
    existing_index_endpoints = aiplatform.MatchingEngineIndexEndpoint.list()
    logging.info(
        'AiPlatform Client: Found %s endpoints', len(existing_index_endpoints)
    )
    for existing_index_endpoint in existing_index_endpoints:
      if (
          existing_index_endpoint.display_name
          == embedding_index_endpoint_display_name
      ):
        logging.info(
            'AiPlatform Client: Index endpoint already exists: %s',
            embedding_index_endpoint_display_name,
        )
        return aiplatform.MatchingEngineIndexEndpoint(
            existing_index_endpoint.name
        )
    logging.warning(
        'AiPlatform Client: Could not find embedding index endpoint'
        ' resource: %s',
        embedding_index_endpoint_display_name,
    )

  def create_embeddings_index(
      self,
      display_name: str = _DEFAULT_INDEX_DISPLAY_NAME,
      shard_size: str = _DEFAULT_SHARD_SIZE,
  ) -> aiplatform.MatchingEngineIndex:
    """Creates an embedding index on the files in the bucket.

    Args:
      display_name: The name of the index to create.
      shard_size: The shard size for the index.

    Returns:
      An AI Platform MatchingEngineIndex resource.
    """
    logging.info(
        'AiPlatform Client: Creating index %s on files in bucket: %s',
        display_name,
        self._bucket_name,
    )
    embedding_index = aiplatform.MatchingEngineIndex.create_tree_ah_index(
        display_name=display_name,
        contents_delta_uri=f'gs://{self._bucket_name}',
        dimensions=768,
        approximate_neighbors_count=10,
        distance_measure_type='DOT_PRODUCT_DISTANCE',
        shard_size=shard_size,
        feature_norm_type='UNIT_L2_NORM',
    )

    return embedding_index

  def create_embeddings_index_endpoint(
      self,
      display_name: str = _DEFAULT_INDEX_ENDPOINT_DISPLAY_NAME,
  ) -> aiplatform.MatchingEngineIndexEndpoint:
    """Creates an embedding index endpoint.

    Args:
      display_name: The name of the endpoint to create.

    Returns:
      An AI Platform MatchingEngineIndexEndpoint resource.
    """

    logging.info('AiPlatform Client: Creating index endpoint: %s', display_name)
    embedding_index_endpoint = aiplatform.MatchingEngineIndexEndpoint.create(
        display_name=display_name,
        network=self._vpc_network_id,
    )
    logging.info(
        'AiPlatform Client: Creating index endpoint succeeded: %s',
        display_name,
    )
    return embedding_index_endpoint

  def deploy_embedding_index_to_endpoint(
      self,
      embedding_index: aiplatform.MatchingEngineIndex,
      embedding_index_endpoint: aiplatform.MatchingEngineIndexEndpoint,
      deployed_index_display_name: str = _DEFAULT_INDEX_DEPLOYED_DISPLAY_NAME,
      min_replica_count: int = _DEFAULT_MIN_REPLICA_COUNT,
      max_replica_count: int = _DEFAULT_MAX_REPLICA_COUNT,
      machine_type: str = _DEFAULT_MACHINE_TYPE,
  ) -> None:
    """Deploys an embedding index endpoint.

    Args:
      embedding_index: An AI Platform MatchingEngineIndex resource.
      embedding_index_endpoint: The AI Platform MatchingIndexEndpoint resource.
      deployed_index_display_name: The display name of the deployed index.
      min_replica_count: The minimum number of replicas.
      max_replica_count: The maximium number of replicas.
      machine_type: The machine type to use for the deployed index.
    """
    time_id = int(time.time_ns())
    deployed_index_id = f'{deployed_index_display_name}_{time_id}'
    try:
      logging.info(
          'AiPlatformClient: Deploying index endpoint: %s',
          embedding_index_endpoint.display_name,
      )
      embedding_index_endpoint.deploy_index(
          index=embedding_index,
          deployed_index_id=deployed_index_id,
          display_name=deployed_index_display_name,
          min_replica_count=min_replica_count,
          max_replica_count=max_replica_count,
          machine_type=machine_type,
      )
      logging.info(
          'AiPlatformClient Client: Deployed index endpoint: %s',
          embedding_index_endpoint.display_name,
      )
      self.embedding_index_deployed_id = deployed_index_id
    except RuntimeError as runtime_err:
      logging.error(
          'AiPlatformClient: MatchingEngineIndex resource with id  %s'
          ' has not been created. Try again later.',
          deployed_index_id,
      )
      raise IndexCreationInProgressError(runtime_err) from runtime_err
    except exceptions.AlreadyExists:
      logging.info(
          'AiPlatformClient Client: MatchingEngineIndexEndpoint resource with'
          ' id  %s already exists.',
          deployed_index_id,
      )
      raise

  def delete_all_embedding_index_endpoints(
      self,
  ) -> None:
    """Deletes all existing embedding index endpoints."""
    existing_endpoints = aiplatform.MatchingEngineIndexEndpoint.list()
    for endpoint_name in existing_endpoints:
      logging.info(
          'AiPlatformClient: Deleting index endpoint: %s',
          endpoint_name.display_name,
      )
      index_endpoint = aiplatform.MatchingEngineIndexEndpoint(
          endpoint_name.name
      )
      index_endpoint.delete(
          force=True
      )  # Force undeployes indexes, before deleting the endpoint.
      logging.info(
          'AiPlatformClient: Deleted index endpoint: %s',
          endpoint_name.display_name,
      )
    self.embedding_index_endpoint = None
    self.embedding_index_deployed_id = None
