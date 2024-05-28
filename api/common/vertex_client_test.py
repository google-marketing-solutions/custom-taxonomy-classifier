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

"""Tests for vertex_client.py."""

import os
from unittest import mock
import google.api_core
import vertexai
from vertexai import generative_models
from vertexai.language_models import TextEmbeddingModel
from custom_taxonomy_classifier.api.common import vertex_client as vertex_client_lib
from absl.testing import absltest
from absl.testing import parameterized


_TEXT_EMBEDDING_MODEL_RESPONSE = [
    vertexai.language_models.TextEmbedding(
        values=[0.1, 0.2, 0.3], statistics=None, _prediction_response=None
    )
]


class VertexClientTest(parameterized.TestCase):

  def setUp(self):
    super().setUp()
    self.mock_vertex_init = self.enter_context(
        mock.patch.object(vertexai, 'init', autospec=True)
    )
    self.enter_context(
        mock.patch.dict(os.environ, {'GCP_PROJECT_ID': 'fake_project'})
    )
    self.mock_model = self.enter_context(
        mock.patch.object(
            TextEmbeddingModel,
            'from_pretrained',
            autospec=True,
        )
    )
    mock_text_generation_response = mock.MagicMock()
    mock_text_generation_response.text.return_value = 'fake_text'
    self.mock_text_generation_model = self.enter_context(
        mock.patch.object(
            generative_models,
            'GenerativeModel',
            autospec=True,
        )
    )
    self.mock_text_generation_model.return_value.generate_content.return_value = (
        mock_text_generation_response
    )
    self.mock_part = self.enter_context(
        mock.patch.object(
            generative_models,
            'Part',
            autospec=True,
        )
    )

  @parameterized.named_parameters(
      dict(
          testcase_name='text',
          text_list=['fake_text'],
          media_descriptions=None,
          expected={'fake_text': [0.1, 0.2, 0.3]},
      ),
      dict(
          testcase_name='text_list',
          text_list=['fake_text1', 'fake_text2', 'fake_text3'],
          media_descriptions=None,
          expected={
              'fake_text1': [0.1, 0.2, 0.3],
              'fake_text2': [0.1, 0.2, 0.3],
              'fake_text3': [0.1, 0.2, 0.3],
          },
      ),
      dict(
          testcase_name='long_list',
          text_list=['fake_text' for _ in range(300)],
          media_descriptions=None,
          expected={'fake_text': [0.1, 0.2, 0.3]},
      ),
      dict(
          testcase_name='empty',
          text_list='',
          media_descriptions=None,
          expected={},
      ),
      dict(
          testcase_name='medias',
          text_list=None,
          media_descriptions=[
              ('gs://fake/path/to/media.jpeg', 'fake_media_text'),
              ('gs://fake/path/to/media2.jpeg', 'fake_media_text2'),
          ],
          expected={
              'gs://fake/path/to/media.jpeg': [0.1, 0.2, 0.3],
              'gs://fake/path/to/media2.jpeg': [0.1, 0.2, 0.3],
          },
      ),
      dict(
          testcase_name='no_input',
          text_list=None,
          media_descriptions=None,
          expected={},
      ),
  )
  def test_get_embeddings_batch(self, text_list, media_descriptions, expected):
    text_length = len(text_list) if text_list else 0
    media_length = len(media_descriptions) if media_descriptions else 0
    self.mock_model.return_value.get_embeddings.return_value = (
        _TEXT_EMBEDDING_MODEL_RESPONSE * (text_length + media_length)
    )
    vertex_client = vertex_client_lib.VertexClient()

    actual = vertex_client.get_embeddings_batch(
        text_list=text_list, media_descriptions=media_descriptions
    )

    self.assertDictEqual(actual, expected)
    self.mock_vertex_init.assert_called_once_with(project='fake_project')

  def test_get_embeddings_batch_multiple(self):
    text_list = ['fake_text' for _ in range(300)]
    expected = {'fake_text': [0.1, 0.2, 0.3]}
    self.mock_model.return_value.get_embeddings.return_value = (
        _TEXT_EMBEDDING_MODEL_RESPONSE * len(text_list)
    )
    vertex_client = vertex_client_lib.VertexClient()

    actual = vertex_client.get_embeddings_batch(text_list=text_list)

    self.assertDictEqual(actual, expected)
    self.mock_model.return_value.get_embeddings.assert_has_calls(
        [mock.call(text_list[:200]), mock.call(text_list[200:300])]
    )

  def test_get_embeddings_batch_logs(self):
    text_list = ['fake_text' for _ in range(300)]
    with self.assertLogs(level='INFO') as log_output:
      vertex_client = vertex_client_lib.VertexClient()
      vertex_client.get_embeddings_batch(text_list=text_list)

      self.assertEqual(
          log_output.output,
          [
              'INFO:absl:Vertex Client: Initialized',
              (
                  'INFO:absl:Vertex Client: Processing batch 1 of 2 with size'
                  ' 200: 50% complete'
              ),
              (
                  'INFO:absl:Vertex Client: Processing batch 2 of 2 with size'
                  ' 100: 100% complete'
              ),
          ],
      )

  @parameterized.named_parameters(
      dict(
          testcase_name='image',
          mime_type='image/jpeg',
          file_uri='gs://fake-project/fake-file.jpeg',
          prompt='This image shows:',
      ),
      dict(
          testcase_name='video',
          mime_type='video/mp4',
          file_uri='gs://fake-project/fake-file.mp4',
          prompt='This video shows:',
      ),
  )
  @mock.patch.object(generative_models, 'GenerationResponse', autospec=True)
  def test_get_text_from_medias(
      self, mock_text_generation_response, mime_type, file_uri, prompt
  ):
    mock_file_part = mock.MagicMock()
    mock_file_part.file_type = mock.MagicMock()
    mock_file_part.file_type.mime_type = mime_type
    mock_file_part.file_type.file_uri = file_uri
    self.mock_part.from_uri.return_value = mock_file_part
    mock_text_generation_response.text = 'Some media description.'
    self.mock_text_generation_model.return_value.generate_content.return_value = (
        mock_text_generation_response
    )

    actual = vertex_client_lib.VertexClient().generate_descriptions_from_medias(
        media_paths=[file_uri]
    )
    expected = [(file_uri, 'Some media description.')]

    self.assertListEqual(actual, expected)
    self.assertEqual(actual[0][0], expected[0][0])
    self.assertEqual(actual[0][1], expected[0][1])
    self.mock_text_generation_model.return_value.generate_content.assert_called_once_with(
        contents=[mock_file_part, prompt],
        stream=False,
        generation_config=mock.ANY,
    )

  def test_get_text_from_media_raises_value_error(self):
    with self.assertRaises(ValueError):
      vertex_client_lib.VertexClient().generate_descriptions_from_medias(
          media_paths=['gs://fake-project/fake-file.json']
      )

  @mock.patch.object(generative_models, 'GenerationResponse', autospec=True)
  def test_generate_descriptions_from_medias_retries(
      self, mock_text_generation_response
  ):
    mock_file_part = mock.MagicMock()
    mock_file_part.file_type = mock.MagicMock()
    mock_file_part.file_type.mime_type = 'media/jpeg'
    mock_file_part.file_type.file_uri = 'gs://fake-project/fake-file.jpeg'
    self.mock_part.from_uri.return_value = mock_file_part
    mock_text_generation_response.text = 'Some media description.'
    self.mock_text_generation_model.return_value.generate_content.side_effect = [
        google.api_core.exceptions.ResourceExhausted('fake_error'),
        mock_text_generation_response,
    ]

    vertex_client_lib.VertexClient().generate_descriptions_from_medias(
        media_paths=['gs://fake-project/fake-file.jpeg']
    )

    self.mock_text_generation_model.return_value.generate_content.assert_has_calls([
        mock.call(
            contents=[mock_file_part, 'This image shows:'],
            stream=False,
            generation_config=mock.ANY,
        ),
        mock.call(
            contents=[mock_file_part, 'This image shows:'],
            stream=False,
            generation_config=mock.ANY,
        ),
    ])


if __name__ == '__main__':
  absltest.main()
