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

"""Test for the Taxonomy class."""

from datamodel import category as category_lib
from datamodel import taxonomy as taxonomy_lib
from absl.testing import absltest


class TaxonomyTest(absltest.TestCase):

  def test_category_emebedding_list(self):
    expected_category_embedding_list = [
        {
            'id': '1',
            'embedding': [1.0, 2.0],
        },
        {
            'id': '2',
            'embedding': [3.0, 4.0],
        },
    ]
    categories = [
        category_lib.Category(id='1', name='1', embeddings=[1.0, 2.0]),
        category_lib.Category(id='2', name='2', embeddings=[3.0, 4.0]),
    ]
    taxonomy = taxonomy_lib.Taxonomy(categories=categories)
    actual_category_embedding_list = taxonomy.to_category_embedding_list()
    self.assertEqual(actual_category_embedding_list,
                     expected_category_embedding_list)


if __name__ == '__main__':
  absltest.main()
