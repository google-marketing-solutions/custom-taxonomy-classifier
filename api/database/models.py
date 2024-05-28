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

"""Database models."""

import datetime


import sqlalchemy  # pylint:disable=unused-import,disable=invalid-import-order,g-bad-import-order
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

# TODO: b/320658095 - Add database models and creation tests.

Base = declarative_base()


class TaxonomyEmbeddingsStatus(Base):
  __tablename__ = 'task_status'

  task_id = sqlalchemy.Column(sqlalchemy.String, primary_key=True)
  status = sqlalchemy.Column(sqlalchemy.String)
  time_created = sqlalchemy.Column(
      sqlalchemy.DateTime(timezone=True),
      server_default=func.now(),
  )
  time_updated = sqlalchemy.Column(
      sqlalchemy.DateTime(timezone=True),
      default=datetime.datetime.utcnow,
      onupdate=datetime.datetime.utcnow,
  )
