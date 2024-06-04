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

"""Tests for query."""

import sqlalchemy
from database import errors
from database import query
from absl.testing import absltest


class QueryDocstring:
  """This is the query string."""


class QueryNoDocstring:
  pass


class QueryTest(absltest.TestCase):

  def test_instantiation_raises_exception(self):
    with self.assertRaises(TypeError):
      query.Query()

  def test_valid_query_class(self):
    query_string = query._extract_query_string(QueryDocstring)
    self.assertEqual(query_string, 'This is the query string.')

  def test_no_docstring(self):
    with self.assertRaises(errors.BadUsageError):
      query._extract_query_string(QueryNoDocstring)

  def test_invalid_class(self):
    with self.assertRaises(errors.BadUsageError):
      query._extract_query_string('This is a string, not a class')

  def test_bind_query(self):
    query_result = query.bind_query(QueryDocstring)
    self.assertIsInstance(query_result, sqlalchemy.sql.elements.TextClause)
    self.assertEqual(
        str(query_result.compile(compile_kwargs={'literal_binds': True})),
        'This is the query string.',
    )


if __name__ == '__main__':
  absltest.main()
