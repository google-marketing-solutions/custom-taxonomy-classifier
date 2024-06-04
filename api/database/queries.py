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

"""Module to hold Postgres DB queries."""

from database import query as query_lib


class DeleteTask(query_lib.Query):
  """-- Deletes a task from the task status table.

  DELETE FROM task_status WHERE task_id = :task_id;
  """


class AddTask(query_lib.Query):
  """-- Writes a task status.

  INSERT INTO task_status (task_id, status) VALUES
    (:task_id, :status);
  """


class UpdateTaskStatus(query_lib.Query):
  """-- Updates a task status.

  UPDATE task_status
  SET status = :status, time_updated = :time_updated WHERE
  task_status.task_id = :task_id
  """


class GetTaskStatus(query_lib.Query):
  """-- Gets a task status.

  SELECT
    task_id,
    status,
    time_created,
    time_updated
  FROM task_status
  WHERE task_id = :task_id
  ORDER BY time_updated DESC
  LIMIT 1
  """
