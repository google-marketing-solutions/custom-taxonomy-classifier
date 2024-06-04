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

"""Module for reading entities from a Google Cloud SQL postgres database."""

import datetime
from typing import Union

from absl import logging
import sqlalchemy

from database import errors
from database import queries
from database import query as query_lib
from datamodel import task as task_lib


class PostgresClient:
  """Reader for querying the a postgres database.

  Example usage:
    base_client = base_postgres_client.BasePostgresClient()
    client = PostgresClient(base_client.write_engne, base_client.read_engine)
    taxonomy_embeddings = client.get_similar_categories_for_vector(
        [0.1,...])
  """

  def __init__(
      self,
      engine: sqlalchemy.engine.Engine,
  ):
    """Initializes the PostgresClient.

    Args:
      engine: A SQLAlchemy engine for the instance.
    """
    self.engine = engine

  def add_task(self, task_id: str) -> None:
    """Creates a task.

    Args:
      task_id: A taxonomy task id.
    """
    try:
      with self.engine.connect() as db_conn:
        query = query_lib.bind_query(queries.AddTask)
        db_conn.execute(
            statement=query,
            parameters={
                'task_id': task_id,
                'status': task_lib.TaskStatus.STARTED.name,
            },
        )
        db_conn.commit()
    except sqlalchemy.exc.IntegrityError as integrity_err:
      logging.debug(
          'PostgresClient: Task %s already exists: %s.', task_id, integrity_err
      )
      self.update_task(task_id, task_lib.TaskStatus.STARTED)
    except (sqlalchemy.exc.DatabaseError, sqlalchemy.exc.DBAPIError) as err:
      logging.exception('PostgresClient: Could not create task %s.', task_id)
      raise errors.PostgresClientError(err) from err
    logging.info('PostgresClient: Created task %s.', task_id)

  def update_task(self, task_id: str, status: task_lib.TaskStatus) -> None:
    """Updates a task status.

    Args:
      task_id: A taxonomy task id.
      status: The new status to set.
    """
    try:
      with self.engine.connect() as db_conn:
        query = query_lib.bind_query(queries.UpdateTaskStatus)
        db_conn.execute(
            statement=query,
            parameters={
                'task_id': task_id,
                'status': status.name,
                'time_updated': datetime.datetime.now(datetime.timezone.utc),
            },
        )
        db_conn.commit()
    except (sqlalchemy.exc.DatabaseError, sqlalchemy.exc.DBAPIError) as err:
      logging.exception(
          'PostgresClient:Could not update status for task %s.', task_id
      )
      raise errors.PostgresClientError(err) from err
    logging.info(
        'PostgresClient: Set status for task %s: %s', task_id, status.name
    )

  def get_task_status(
      self, task_id: str
  ) -> dict[str, Union[str, datetime.datetime]]:
    """Gets the status of a task.

    Args:
      task_id: The task to get the status for.

    Returns:
      The task id, status, created and updated times.
    """
    try:
      with self.engine.connect() as db_conn:
        query = query_lib.bind_query(queries.GetTaskStatus)
        rows = db_conn.execute(
            statement=query, parameters={'task_id': task_id}
        ).fetchall()
    except sqlalchemy.exc.DatabaseError as err:
      logging.exception('Could not get status for task %s.', task_id)
      raise errors.PostgresClientError(err) from err
    result = {}
    if rows:
      for task_id, status, time_created, time_updated in rows:
        result['task_id'] = task_id
        result['status'] = status
        result['time_created'] = time_created
        result['time_updated'] = time_updated
    else:
      result['task_id'] = task_id
      result['status'] = task_lib.TaskStatus.NOT_FOUND.name
    return result
