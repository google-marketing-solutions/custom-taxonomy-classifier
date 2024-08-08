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

"""Module to classify text against an existing taxonomy."""

import dataclasses
import os
from typing import Optional, Union
from absl import logging
from common import ai_platform_client as ai_platform_client_lib
from common import vertex_client as vertex_client_lib
from database import postgres_client as postgres_client_lib


@dataclasses.dataclass
class ClassifyResult:
  text: Optional[str] = None
  media_uri: Optional[str] = None
  media_description: Optional[str] = None
  categories: Optional[list[dict[str, Union[str, float]]]] = None
  embedding: Optional[list[float]] = None


ClassifyResults = list[ClassifyResult]


def _has_valid_extension(path: str) -> bool:
  """Checks if the string has valid media extension.

  Args:
    path: The path to check.

  Returns:
    True if the text ends with an media extension, False otherwise.
  """
  valid_extensions = vertex_client_lib.SUPPORTED_MEDIA_TYPES
  extension = os.path.splitext(path)[1].replace('.', '')
  return extension.lower() in valid_extensions


class ClassifyService:
  """A class to classify text against an existing taxonomy."""

  def __init__(
      self,
      postgres_client: postgres_client_lib.PostgresClient,
      vertex_client: vertex_client_lib.VertexClient,
      ai_platform_client: ai_platform_client_lib.AiPlatformClient,
  ) -> None:
    """Constructor.

    Args:
      postgres_client: A read postgres client instance.
      vertex_client: A vertex client instance.
      ai_platform_client: An ai platform client instance.
    """
    self.postgres_client = postgres_client
    self.vertex_client = vertex_client
    self.ai_platform_client = ai_platform_client
    logging.info('Classify Service: Initialized.')

  def classify(
      self,
      text: Optional[Union[str, list[str]]] = None,
      media_uri: Optional[Union[str, list[str]]] = None,
      embeddings: bool = False,
  ) -> ClassifyResults:
    """Gets the semantic similarty of the passed input relative to the taxonomy.

    The method returns a dictionary of the result from comparing the embeddings
    of the passed text input relative to each of the taxonomy nodes embeddings.

    Args:
      text: A string or a list of strings.
      media_uri: A file path or list of file paths.
      embeddings: A boolean indicating whether to return the embeddings.

    Returns:
      A response object containing the text input elements as keys and their
      similarity to each of the taxonomies nodes.

    Raises:
      ValueError: If the media paths contain unsupported extensions.
    """
    text_list = [text] if isinstance(text, str) else text
    media_uris = [media_uri] if isinstance(media_uri, str) else media_uri
    if media_uris and not all(
        [_has_valid_extension(element) for element in media_uris]
    ):
      raise ValueError('Request contains an invalid media extensions.')
    if not text_list and not media_uris:
      return []
    media_descriptions = None
    if media_uris:
      media_descriptions = self.vertex_client.generate_descriptions_from_medias(
          media_uris
      )
    text_embeddings = self.vertex_client.get_embeddings_batch(
        text_list, media_descriptions
    )
    return self._find_nearest_neighbors_for_text(
        text_embeddings, media_descriptions, embeddings
    )

  def _find_nearest_neighbors_for_text(
      self,
      text_embeddings: dict[str, list[float]],
      media_descriptions: Optional[list[tuple[str, str]]] = None,
      embeddings: bool = False,
  ) -> ClassifyResults:
    """Finds the nearest neighbors for text.

    Args:
      text_embeddings: An object containing embeddings for all text elements.
      media_descriptions: List of (media path, description) tuples.
      embeddings: A boolean indicating whether to return the embeddings.

    Returns:
      A list of dict objects with text as the key and the similarities to
      taxonomy nodes as values.
    """
    media_descriptions_dict = (
        dict(media_descriptions) if media_descriptions else {}
    )
    vectors = list(text_embeddings.values())
    text_list = list(text_embeddings.keys())
    results = self.ai_platform_client.find_neighbors_for_vectors(
        vectors=vectors
    )
    classify_results = []
    for text, result in zip(text_list, results):
      similar_categories = []
      for category in result:
        similar_categories.append(
            {'name': category.id, 'similarity': category.distance}
        )
      if _has_valid_extension(text):
        classify_results.append(
            ClassifyResult(
                media_uri=text,
                categories=similar_categories,
                media_description=media_descriptions_dict[text],
                embedding=text_embeddings[text] if embeddings else None,
            )
        )
      else:
        classify_results.append(
            ClassifyResult(
                text=text,
                categories=similar_categories,
                embedding=text_embeddings[text] if embeddings else None,
            )
        )
    return classify_results
