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

"""The classify library."""

from concurrent import futures
import math
import multiprocessing
import os
import time
from typing import Any

from absl import logging

import utils


_BATCH_SIZE = 1000


class ClassifyClient:
  """Class to classify keywords via the classify api endpoint."""

  def __init__(self) -> None:
    self._url = os.environ['CLASSIFY_API_URL']

  def classify_keywords(self, keywords: list[str]) -> dict[str, str]:
    """Classifies a list of keywords.

    Args:
      keywords: A list of keywords.

    Returns:
      A list of BigQuery row objects containing the classified keywords.
    """
    logging.info('Classify: Starting classification...')
    params = self._build_api_param_batches(keywords)
    classify_api_results = self._send_classify_api_requests(params)
    classified_keywords_rows = self._build_dict_from_classify_api_results(
        classify_api_results
    )
    return classified_keywords_rows

  def _build_api_param_batches(
      self, keywords: list[str]
  ) -> list[dict[str, list[str]]]:
    """Builds batches from a list of keywords.

    Args:
      keywords: A list of keywords.

    Returns:
      A list of json object for the API request.
    """
    keywords_to_process = keywords
    num_batches = math.ceil(len(keywords) / _BATCH_SIZE)
    logging.info('Classify: Using %s batches.', num_batches)
    params_batches = []
    while keywords_to_process:
      chunk, keywords_to_process = (
          keywords_to_process[:_BATCH_SIZE],
          keywords_to_process[_BATCH_SIZE:],
      )
      params_batches.append({'text': chunk})
    return params_batches

  def _send_classify_api_requests(
      self, params_batches: list[dict[str, list[str]]]
  ) -> list[Any]:
    """Sends API requests in parallel.

    Args:
      params_batches: A list of API request parameters.

    Returns:
      A list of responses.
    """
    start_time = time.time()
    num_workers = multiprocessing.cpu_count() + 4
    logging.info(
        'Classify: Processing batches in parallel using %s workers.',
        num_workers,
    )
    with futures.ThreadPoolExecutor(max_workers=num_workers) as executor:
      responses = executor.map(
          lambda params: utils.send_api_request(
              self._url,
              params,
          ),
          params_batches,
      )
    end_time = time.time()
    duration = round(end_time - start_time, 1)
    logging.info('Classify: Took %s seconds in total.', duration)
    results = []
    for response in responses:
      results.extend(response)
    return results

  def _build_dict_from_classify_api_results(
      self, classify_api_results: list[Any]
  ) -> dict[str, str]:
    """Formats the api results into BigQuery row objects.

    Args:
      classify_api_results: A list of API responses.

    Returns:
      Keyword classifications as dict, e.g. {'some keyword': 'some category'}
    """
    classified_keywords = dict()
    for result in classify_api_results:
      classified_keywords[result['text']] = result['categories'][0]['name']
    return classified_keywords
