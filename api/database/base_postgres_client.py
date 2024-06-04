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

"""Module with the base Postgres client inherited by the write/read classes."""

import os

from absl import logging
import sqlalchemy

from database import errors
from database import models as models_lib

_DRIVER = 'pg8000'
_ENGINE_POOL_SIZE = 25
_ENGINE_OVERFLOW_MAX = 5


# TODO: b/321252366 - Consolidate Base, Write and Read clients.
class BasePostgresClient:
  """Base class for any type of Postgres reader or writing client.

  This base class handles choosing the correct Postgres instance and database
  and initializing the Postgres client.
  """

  def __init__(self) -> None:
    """Initializes the postgres client."""

    self._project_id = os.environ['GCP_PROJECT_ID']
    self._region = os.environ['GCP_REGION']
    self._db_user = os.environ['POSTGRES_DB_USER']
    self._db_password = os.environ['POSTGRES_DB_PASSWORD']
    self._db_name = os.environ['POSTGRES_DB_NAME']
    self._instance_host = os.environ['POSTGRES_INSTANCE_HOST']
    self._instance_port = os.environ['POSTGRES_INSTANCE_PORT']
    self.engine = self._get_engine(_ENGINE_POOL_SIZE, _ENGINE_OVERFLOW_MAX)

  def create_tables_if_not_exist(self):
    """Creates all tables if they do not exist."""
    try:
      models_lib.Base.metadata.create_all(bind=self.engine)
    except (sqlalchemy.exc.DatabaseError, sqlalchemy.exc.DBAPIError) as err:
      logging.exception(
          'BasePostgresClient: Could not create tables.'
      )
      raise errors.BasePostgresClientError(err) from err
    logging.info('BasePostgresClient: Created tables or aready existed.')

  def _get_engine(
      self, pool_size: int, max_overflow: int
  ) -> sqlalchemy.engine.Engine:
    """Creates an engine engine for a postgres connection.

    Args:
      pool_size: The size of the connection pool.
      max_overflow: The number of connections allowed to overflow the pool size.

    Returns:
      A SQL alchemy engine engine.
    """
    url = sqlalchemy.engine.url.URL.create(
        drivername=f'postgresql+{_DRIVER}',
        username=self._db_user,
        password=self._db_password,
        host=self._instance_host,
        port=self._instance_port,
        database=self._db_name,
    )
    engine = sqlalchemy.create_engine(
        url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        echo_pool=True,
        pool_timeout=60,
        pool_recycle=1200,
    )
    return engine
