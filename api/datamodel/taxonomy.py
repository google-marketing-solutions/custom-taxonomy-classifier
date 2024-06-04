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

"""Module for domain entities related to a Taxonomy."""

from typing import Any, Optional
import pandas as pd
from datamodel import category as category_lib


class Taxonomy:
  """Value object of a taxonomy and associated category embeddings."""

  def __init__(
      self,
      entity_id: Optional[str] = None,
      categories: Optional[list[category_lib.Category]] = None,
  ) -> None:
    self.entity_id = entity_id
    self.categories = categories if categories else []

  def __eq__(self, other):
    return (
        isinstance(other, Taxonomy)
        and self.entity_id == other.entity_id
        and self.categories.sort(key=lambda x: x.name, reverse=False)
        == other.categories.sort(key=lambda x: x.name, reverse=False)
    )

  def to_df(self) -> pd.DataFrame:
    """Returns the taxonomy as a dataframe."""
    return (
        pd.DataFrame([category.__dict__ for category in self.categories])
        if self.categories
        else pd.DataFrame()
    )

  def to_category_embedding_list(self) -> list[dict[str, Any]]:
    """Returns the taxonomy as a list of categories and embeddings."""
    out = []
    for category in self.categories:
      out.append({
          'id': category.name,
          'embedding': category.embeddings,
      })
    return out
