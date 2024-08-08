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

"""A client to make calls to Vertex API."""

from concurrent import futures
import dataclasses
import math
import mimetypes
import multiprocessing
import os
from typing import Optional, cast
from absl import logging
import google.api_core
import vertexai
from vertexai import generative_models
from vertexai.language_models import TextEmbeddingModel
import tenacity

_TEXT_EMBEDDING_MODEL = 'textembedding-gecko-multilingual@001'
_GENERATIVE_MODEL = 'gemini-1.5-flash-001'

_GENERATION_CONFIG = generative_models.GenerationConfig(
    temperature=0.8,
    top_p=0.95,
    top_k=20,
    candidate_count=1,
    stop_sequences=['STOP!'],
)
_MAX_BATCH_SIZE = 200

SUPPORTED_VIDEO_TYPES = frozenset([
    'x-flv',
    'mov',
    'mpeg',
    'mpegps',
    'mpg',
    'mp4',
    'webm',
    'wmv',
    '3gpp',
])

SUPPORTED_IMAGE_TYPES = frozenset(['jpeg', 'jpg', 'png'])

SUPPORTED_MEDIA_TYPES = frozenset().union(
    *[SUPPORTED_VIDEO_TYPES, SUPPORTED_IMAGE_TYPES]
)


@dataclasses.dataclass(frozen=True)
class Prompt:
  IMAGE = 'This image shows:'
  VIDEO = 'This video shows:'


class VertexClient:
  """A client to make requests to the Vertex API.

  Example usage:
    vertex_client = VertexClient()
    embeddings = vertex_client.get_embeddings(['Some text'])
  """

  def __init__(self) -> None:
    """Constructor."""
    vertexai.init(project=os.environ['GCP_PROJECT_ID'])
    self._text_embeddings_client = TextEmbeddingModel.from_pretrained(
        _TEXT_EMBEDDING_MODEL
    )
    self._text_generation_client = generative_models.GenerativeModel(
        model_name=_GENERATIVE_MODEL
    )
    logging.info('Vertex Client: Initialized')

  def generate_descriptions_from_medias(
      self, media_paths: list[str]
  ) -> list[tuple[str, str]]:
    """Generates text from medias.

    Args:
      media_paths: A list of URIs to media files on Google Cloud Storage.

    Returns:
      The media URI and generated text pairs.
    """
    num_workers = multiprocessing.cpu_count()
    with futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
      generation_responses = executor.map(
          lambda media_path: self._generate_descriptions_from_media(
              media_path=media_path
          ),
          media_paths,
      )
    results = []
    for generation_response in generation_responses:
      results.append(generation_response)
    return results

  @tenacity.retry(
      retry=tenacity.retry_if_exception_type(
          google.api_core.exceptions.ResourceExhausted
      ),
      wait=tenacity.wait_exponential(min=5, multiplier=2, max=70),
      reraise=False,
      stop=tenacity.stop_after_attempt(10),
  )
  def _generate_descriptions_from_media(
      self, media_path: str
  ) -> tuple[str, str]:
    """Generates the gemini generated text for a media.

    Args:
      media_path: A URI to a media file on Google Cloud Storage.

    Returns:
      The media URI and generated text.
    """
    file_extension = os.path.splitext(media_path)[1].replace('.', '')
    file_type = self._get_file_type_from_extension(file_extension)
    mime_type = mimetypes.guess_type(media_path)[0]
    media_content = generative_models.Part.from_uri(media_path, mime_type)
    response = self._text_generation_client.generate_content(
        contents=[media_content, getattr(Prompt, file_type.upper())],
        stream=False,
        generation_config=_GENERATION_CONFIG,
    )
    generation_response = cast(generative_models.GenerationResponse, response)
    return (media_path, generation_response.text.strip())

  def _get_file_type_from_extension(self, file_extension: str) -> str:
    """Gets the file type from the file extension.

    Args:
      file_extension: The file extension.

    Returns:
      The file type.

    Raises:
      ValueError: If the file extension is not supported.
    """
    if file_extension in SUPPORTED_IMAGE_TYPES:
      return 'image'
    elif file_extension in SUPPORTED_VIDEO_TYPES:
      return 'video'
    else:
      raise ValueError(f'Unsupported file type: {file_extension}')

  def _build_input_object_for_embeddings(
      self,
      text_list: Optional[list[str]] = None,
      media_descriptions: Optional[list[tuple[str, str]]] = None,
  ) -> tuple[list[str], list[str]]:
    """Builds the input object for generating the embeddings.

    For the text_list the output keys and text values will be the same.

    Args:
      text_list: A list of texts.
      media_descriptions: List of (media path, description) tuples.

    Returns:
      A tuple of two lists containing the text for which to generate embeddings
      and keys used for the output embeddings.
    """
    text_list = [] if text_list is None else text_list
    media_descriptions = (
        [] if media_descriptions is None else media_descriptions
    )
    unified_list = text_list + media_descriptions

    text_values = []
    output_keys = []

    for element in unified_list:
      if isinstance(element, tuple):
        text_values.append(element[1])
        output_keys.append(element[0])
      else:
        text_values.append(element)
        output_keys.append(element)

    return output_keys, text_values

  def get_embeddings_batch(
      self,
      text_list: Optional[list[str]] = None,
      media_descriptions: Optional[list[tuple[str, str]]] = None,
  ) -> dict[str, list[float]]:
    """Gets the embeddings for texts and maps their embeddings.

    Args:
      text_list: A list of texts or key value pairs.
      media_descriptions: List of (media path, description) tuples.

    Returns:
      A dictionary with list elements as keys in a dictionary with their
      embeddings.
    """
    output_keys, text_values = self._build_input_object_for_embeddings(
        text_list, media_descriptions
    )
    batch_start = 0
    embeddings_vectors = []
    num_batches = math.ceil(len(text_values) / _MAX_BATCH_SIZE)
    current_batch = 1
    while batch_start < len(text_values):
      batch, next_batch_index = self._get_text_list_batch(
          text_values, batch_start
      )
      pct_complete = f'{int(round(current_batch / num_batches * 100, 0))}%'
      logging.info(
          'Vertex Client: Processing batch %d of %d with size %d: %s complete',
          current_batch,
          num_batches,
          len(batch),
          pct_complete,
      )
      embeddings = self._text_embeddings_client.get_embeddings(batch)
      for embedding in embeddings:
        vector = embedding.values
        embeddings_vectors.append(vector)
      batch_start = next_batch_index
      current_batch += 1
    text_embeddings = [
        (key, value) for key, value in zip(output_keys, embeddings_vectors)
    ]
    return dict(text_embeddings)

  def _get_text_list_batch(
      self,
      text_list: list[str],
      batch_start: int,
      batch_size: int = _MAX_BATCH_SIZE,
  ) -> tuple[list[str], int]:
    """Returns a batch from a list of strings.

    Args:
      text_list: A list of texts.
      batch_start: The start index for the batch.
      batch_size: The number of elements per batch.

    Returns:
      A tuple of batch and end index.
    """
    batch_end = batch_start + batch_size
    return text_list[batch_start:batch_end], batch_end
