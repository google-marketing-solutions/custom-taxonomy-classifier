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

"""Tests for the classify client."""

import os
from unittest import mock
import freezegun
from google.cloud import bigquery
import bigquery_client as bigquery_client_lib
from absl.testing import absltest


class ClassifyTest(absltest.TestCase):

  def setUp(self):
    super().setUp()
    self.mock_bq_client = self.enter_context(
        mock.patch.object(bigquery, 'Client', autospec=True)
    )
    self.enter_context(
        mock.patch.dict(os.environ, {'ADS_TRANSFER_DATASET': 'fake_dataset'})
    )
    self.enter_context(
        mock.patch.dict(os.environ, {'CLASSIFICATIONS_DATASET': 'fake_dataset'})
    )
    self.enter_context(
        mock.patch.dict(os.environ, {'ADS_TRANSFER_ACCOUNT_ID': '1234'})
    )
    self.enter_context(
        mock.patch.dict(os.environ, {'DAILY_COST_THRESHOLD_MICROS': '1000000'})
    )

  def test_get_spending_keywords(self):
    expected_query = (
        'SELECT K.ad_group_criterion_keyword_text AS keyword_text, FROM  '
        ' fake_dataset.ads_Keyword_1234 AS K   INNER JOIN  '
        ' fake_dataset.ads_KeywordBasicStats_1234 AS S USING'
        ' (ad_group_criterion_criterion_id) WHERE S.metrics_cost_micros >='
        ' 1000000 AND S._DATA_DATE = DATE_SUB(CURRENT_DATE(), INTERVAL 3 DAY)'
        ' AND K._DATA_DATE = K._LATEST_DATE GROUP BY  1;'
    )
    mock_row = mock.MagicMock()
    mock_row.keyword_text = 'keyword1'
    mock_job = mock.MagicMock()
    mock_job.result.return_value = [mock_row]
    self.mock_bq_client.return_value.query.return_value = mock_job

    expected = ['keyword1']
    actual = bigquery_client_lib.BigQueryClient().get_spending_keywords()

    self.assertEqual(actual, expected)
    self.mock_bq_client.return_value.query.assert_called_once_with(
        expected_query
    )

  def test_get_current_keyword_mappings(self):
    expected_query = (
        'SELECT DISTINCT keyword_text, FIRST_VALUE(category_name) OVER (ORDER'
        ' BY updated_at DESC) AS category_name FROM fake_dataset.keywords;'
    )
    mock_row = mock.MagicMock()
    mock_row.keyword_text = 'keyword1'
    mock_row.category_name = 'fake_category'
    mock_job = mock.MagicMock()
    mock_job.result.return_value = [mock_row]
    self.mock_bq_client.return_value.query.return_value = mock_job

    expected = {'keyword1': 'fake_category'}
    actual = bigquery_client_lib.BigQueryClient().get_current_keyword_mappings()

    self.assertEqual(actual, expected)
    self.mock_bq_client.return_value.query.assert_called_once_with(
        expected_query
    )

  @freezegun.freeze_time('2024-01-01')
  def test_write_classified_keywords(self):
    fake_classified_keywords = {'keyword1': 'fake_category'}

    expected_query_1 = 'TRUNCATE TABLE fake_dataset.keywords_staging;'
    expected_query_2 = (
        'MERGE fake_dataset.keywords K USING fake_dataset.keywords_staging S ON'
        ' K.keyword_text = S.keyword_text WHEN MATCHED THEN UPDATE SET  '
        ' category_name = S.category_name,   updated_at = S.datetime WHEN NOT'
        ' MATCHED THEN INSERT (keyword_text, category_name, updated_at)'
        ' VALUES(S.keyword_text, S.category_name, S.datetime);'
    )
    expected_query_3 = (
        'MERGE     fake_dataset.keywords_scd AS scd USING    '
        ' fake_dataset.keywords AS dim ON     scd.keyword_text ='
        ' dim.keyword_text WHEN NOT MATCHED THEN INSERT (     id,    '
        ' keyword_text,     category_name,     start_datetime,     end_datetime'
        ' ) VALUES (     GENERATE_UUID(),     dim.keyword_text,    '
        ' dim.category_name,     dim.updated_at,     NULL     ) WHEN MATCHED'
        ' AND scd.end_datetime IS NULL AND scd.category_name <>'
        ' dim.category_name THEN UPDATE SET scd.end_datetime = dim.updated_at;'
        ' INSERT INTO  fake_dataset.keywords_scd ( id, keyword_text,'
        ' category_name, start_datetime, end_datetime ) ( SELECT  '
        ' GENERATE_UUID(), dim.keyword_text, dim.category_name, dim.updated_at'
        ' as start_datetime, NULL AS end_datetime FROM '
        ' fake_dataset.keywords_scd AS scd INNER JOIN  fake_dataset.keywords AS'
        ' dim ON dim.keyword_text = scd.keyword_text AND dim.updated_at ='
        ' scd.end_datetime AND scd.category_name <> dim.category_name ); '
    )

    expected_insert = [{
        'keyword_text': 'keyword1',
        'category_name': 'fake_category',
        'datetime': '2024-01-01 00:00:00.000000',
    }]

    bigquery_client_lib.BigQueryClient().write_classified_keywords(
        fake_classified_keywords
    )

    self.mock_bq_client.return_value.insert_rows_json.assert_called_once_with(
        'fake_dataset.keywords_staging', expected_insert
    )
    self.mock_bq_client.return_value.query.assert_has_calls([
        mock.call(expected_query_1),
        mock.call().result(),
        mock.call(expected_query_2),
        mock.call().result(),
        mock.call(expected_query_3),
        mock.call().result(),
    ])


if __name__ == '__main__':
  absltest.main()
