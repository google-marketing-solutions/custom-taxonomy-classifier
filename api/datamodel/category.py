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

import dataclasses
from typing import Optional


@dataclasses.dataclass
class Category:
  """Value object of a taxonomy and associated embeddings.

  Embeddings are a vector representation of text. See more details here:
  https://cloud.google.com/vertex-ai/docs/generative-ai/embeddings/get-text-embeddings#use
  """

  name: str
  id: Optional[str] = None
  embeddings: Optional[list[float]] = None
