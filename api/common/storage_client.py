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

"""A client to write taxonomy embeddings to a GCS bucket as JSON files."""

import json
import math
import os
from absl import logging
import google.auth
from google.auth import compute_engine
from google.auth import transport
from google.cloud import exceptions
from google.cloud import storage
import numpy as np
from datamodel import taxonomy as taxonomy_lib


_CATEGORIES_PER_FILE = 3500


class Error(Exception):
  pass


class WriteTaxonomyError(Error):
  pass


class StorageClient:
  """A client to write json files to a Google Cloud Storage bucket.

  Example usage:
    storage_client = StorageClient(bucket_name)
    download_urls = storage_client.write_taxonomy(taxonomy)
  """

  def __init__(self) -> None:
    credentials, project = google.auth.default()
    self._storage_client = storage.Client(
        credentials=credentials, project=project
    )
    auth_request = transport.requests.Request()
    credentials.refresh(request=auth_request)
    self._signing_credentials = compute_engine.IDTokenCredentials(
        auth_request,
        '',
        service_account_email=credentials.service_account_email,
    )
    self._bucket_name = os.environ['BUCKET_NAME']
    self._bucket = self._storage_client.bucket(self._bucket_name)

  def write_taxonomy_embeddings(self, taxonomy: taxonomy_lib.Taxonomy) -> None:
    """Writes a taxonomy to a Google Cloud Storage bucket.

    Args:
      taxonomy: A taxonomy object with added embeddings.
    """
    category_embeddings = taxonomy.to_category_embedding_list()
    file_prefix = 'embeddings'
    num_chunks = (
        math.ceil(len(category_embeddings) / _CATEGORIES_PER_FILE)
        if len(category_embeddings) > _CATEGORIES_PER_FILE
        else 1
    )
    chunks = np.array_split(category_embeddings, num_chunks)
    file_name = 'Unassigned'
    try:
      for index, chunk in enumerate(chunks):
        data_jsonl = '\n'.join(
            [json.dumps(record, separators=(',', ':')) for record in chunk]
        )
        file_name = f'{file_prefix}_{index}.json'
        blob = self._bucket.blob(file_name)
        blob.upload_from_string(
            data=data_jsonl, content_type='application/octet-stream'
        )
    except exceptions.ClientError as client_err:
      logging.exception(
          'Could not write files to GCS. Bucket: %s | File: %s',
          self._bucket.name,
          file_name,
      )
      raise WriteTaxonomyError(
          f'Could not write files to GCS. Bucket: {self._bucket.name} | File:'
          f' {file_name}') from client_err
