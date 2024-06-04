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

"""Base-class for queries defined in class docstrings."""

from typing import Type

import sqlalchemy

from database import errors


class Query:
  """Base-class for queries defined in class docstrings."""

  def __init__(self):
    raise TypeError('Cannot instantiate Query')


def _extract_query_string(query_class: Type[Query]) -> str:
  """Extract the query string from a query class."""
  query = query_class.__doc__
  if not query or isinstance(query_class, str):
    raise errors.BadUsageError(
        'bind_query() requires as an arg a class, the '
        'docstring of which is the query string.'
    )
  if not hasattr(query_class, '__class__'):
    raise errors.BadUsageError(
        'Passing an old-style class as an argument to bind_query()'
    )
  return query


def bind_query(query_class: Type[Query]) -> sqlalchemy.sql.elements.TextClause:
  """Creates a sqlalechemy SQL query object from a query class."""
  query_string = _extract_query_string(query_class)
  return sqlalchemy.text(query_string)
