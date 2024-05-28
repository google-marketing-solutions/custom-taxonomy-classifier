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

"""Task status."""

import enum


class TaskStatus(enum.Enum):
  STARTED = 1
  IN_PROGRESS_GETTING_EMBEDDINGS = 2
  IN_PROGRESS_WRITING_EMBEDDINGS_TO_DB = 3
  IN_PROGRESS_WRITING_EMBEDDINGS_TO_GCS = 4
  IN_PROGRESS_CREATING_EMBEDDINGS_INDEX = 5
  IN_PROGRESS_CREATING_EMBEDDINGS_INDEX_ENDPOINT = 6
  IN_PROGRESS_DEPLOYING_EMBEDDINGS_INDEX_TO_ENDPOINT = 7
  SUCCEEDED = 80
  NOT_FOUND = 90
  FAILED = 100
