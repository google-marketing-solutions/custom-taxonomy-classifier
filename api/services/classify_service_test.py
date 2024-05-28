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

"""Tests for classifier."""

from unittest import mock
from google.cloud import aiplatform
from custom_taxonomy_classifier.api.common import ai_platform_client as ai_platform_client_lib
from custom_taxonomy_classifier.api.common import vertex_client as vertex_client_lib
from custom_taxonomy_classifier.api.database import postgres_client as postgres_client_lib
from custom_taxonomy_classifier.api.services import classify_service as classify_service_lib
from absl.testing import absltest
from absl.testing import parameterized


def _get_find_neightbors_return_value(
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


class ClassifierTest(parameterized.TestCase):

  def setUp(self):
    super().setUp()
    self.maxDiff = None
    self.postgres_client = mock.create_autospec(
        postgres_client_lib.PostgresClient,
        instance=True,
        spec_set=True,
    )

    self.vertex_client = mock.create_autospec(
        vertex_client_lib.VertexClient, instance=True, spec_set=True
    )
    self.ai_platform_client = mock.create_autospec(
        ai_platform_client_lib.AiPlatformClient, instance=True, spec_set=True
    )

  @parameterized.named_parameters(
      dict(
          testcase_name='text',
          text_input=['fake_text_1', 'fake_text_2'],
          media_input=None,
          get_embeddings_batch_return_value={
              'fake_text_1': [0.1, 0.2, 0.3],
              'fake_text_2': [0.1, 0.2, 0.3],
          },
          find_neighbors_result_count=2,
          generate_descriptions_from_medias_return_value={},
          expected=[
              classify_service_lib.ClassifyResult(
                  text='fake_text_1',
                  categories=[
                      {
                          'name': 'fake_id',
                          'similarity': mock.ANY,
                      },
                  ],
              ),
              classify_service_lib.ClassifyResult(
                  text='fake_text_2',
                  categories=[
                      {
                          'name': 'fake_id',
                          'similarity': mock.ANY,
                      },
                  ],
              ),
          ],
      ),
      dict(
          testcase_name='text_and_media',
          text_input=['fake_text_1', 'fake_text_2'],
          media_input=['gs://fake/path_1.jpeg', 'gs://fake/path_2.jpeg'],
          get_embeddings_batch_return_value={
              'fake_text_1': [0.1, 0.2, 0.3],
              'fake_text_2': [0.1, 0.2, 0.3],
              'gs://fake/path_1.jpeg': [0.1, 0.2, 0.3],
              'gs://fake/path_2.jpeg': [0.1, 0.2, 0.3],
          },
          find_neighbors_result_count=4,
          generate_descriptions_from_medias_return_value={
              'gs://fake/path_1.jpeg': 'fake_text_1',
              'gs://fake/path_2.jpeg': 'fake_text_2',
          },
          expected=[
              classify_service_lib.ClassifyResult(
                  text='fake_text_1',
                  categories=[
                      {
                          'name': 'fake_id',
                          'similarity': mock.ANY,
                      },
                  ],
              ),
              classify_service_lib.ClassifyResult(
                  text='fake_text_2',
                  categories=[
                      {
                          'name': 'fake_id',
                          'similarity': mock.ANY,
                      },
                  ],
              ),
              classify_service_lib.ClassifyResult(
                  media_uri='gs://fake/path_1.jpeg',
                  categories=[
                      {
                          'name': 'fake_id',
                          'similarity': mock.ANY,
                      },
                  ],
              ),
              classify_service_lib.ClassifyResult(
                  media_uri='gs://fake/path_2.jpeg',
                  categories=[
                      {
                          'name': 'fake_id',
                          'similarity': mock.ANY,
                      },
                  ],
              ),
          ],
      ),
  )
  def test_classify(
      self,
      text_input,
      media_input,
      get_embeddings_batch_return_value,
      find_neighbors_result_count,
      generate_descriptions_from_medias_return_value,
      expected,
  ):
    self.vertex_client.generate_descriptions_from_medias.return_value = (
        generate_descriptions_from_medias_return_value
    )
    self.vertex_client.get_embeddings_batch.return_value = (
        get_embeddings_batch_return_value
    )
    self.ai_platform_client.find_neighbors_for_vectors.return_value = (
        _get_find_neightbors_return_value(
            find_neighbors_result_count, neighbors_count=1
        )
    )
    classifier = classify_service_lib.ClassifyService(
        self.postgres_client, self.vertex_client, self.ai_platform_client
    )
    actual = classifier.classify(text_input, media_input)
    self.assertEqual(actual, expected)

  def test_classify_without_media_text_input(self):
    classifier = classify_service_lib.ClassifyService(
        self.postgres_client, self.vertex_client, self.ai_platform_client
    )
    classifier.classify('fake_media_text', None)
    self.vertex_client.generate_descriptions_from_medias.assert_not_called()

  def test_classify_with_media_input(self):
    classifier = classify_service_lib.ClassifyService(
        self.postgres_client, self.vertex_client, self.ai_platform_client
    )
    classifier.classify(None, 'gs://fake/path_1.jpeg')
    self.vertex_client.generate_descriptions_from_medias.assert_called()

  def test_classify_with_raises_value_error(self):

    with self.assertRaises(ValueError):
      classifier = classify_service_lib.ClassifyService(
          self.postgres_client, self.vertex_client, self.ai_platform_client
      )
      classifier.classify(None, 'gs://fake/path_1.xyz')


if __name__ == '__main__':
  absltest.main()
