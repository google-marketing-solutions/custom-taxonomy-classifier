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

"""A set of constants and queries."""

KEYWORD_DIM_TABLE_NAME = '{classifications_dataset}.keywords'

KEYWORD_DIM_STAGING_TABLE_NAME = '{classifications_dataset}.keywords_staging'

# Extracts keywords with at least $1 spend over a single day 3 days ago.
SPENDING_KEYWORDS_QUERY = (
    'SELECT K.ad_group_criterion_keyword_text AS keyword_text, FROM  '
    ' {ads_transfer_dataset}.ads_Keyword_{ads_transfer_account_id} AS K   INNER'
    ' JOIN  '
    ' {ads_transfer_dataset}.ads_KeywordBasicStats_{ads_transfer_account_id} AS'
    ' S USING (ad_group_criterion_criterion_id) WHERE S.metrics_cost_micros >='
    ' {daily_cost_threshold_micros} AND S._DATA_DATE = DATE_SUB(CURRENT_DATE(),'
    ' INTERVAL 3 DAY) AND K._DATA_DATE = K._LATEST_DATE GROUP BY  1;'
)

# Extracts the currently existing keyword mappings for the keywords prod table.
CURRENT_KEYWORD_MAPPINGS_QUERY = (
    'SELECT DISTINCT keyword_text, FIRST_VALUE(category_name) OVER (ORDER BY'
    f' updated_at DESC) AS category_name FROM {KEYWORD_DIM_TABLE_NAME};'
)

# Updates the keywords table with new data that arrived in staging if the
# category name changed.
MERGE_STAGING_TO_PROD_QUERY = (
    'MERGE {classifications_dataset}.keywords K USING'
    ' {classifications_dataset}.keywords_staging S ON K.keyword_text ='
    ' S.keyword_text WHEN MATCHED THEN UPDATE SET   category_name ='
    ' S.category_name,   updated_at = S.datetime WHEN NOT MATCHED THEN INSERT'
    ' (keyword_text, category_name, updated_at) VALUES(S.keyword_text,'
    ' S.category_name, S.datetime);'
)

# Truncates the keywords staging table.
TRUNCATE_STAGING_TABLE_QUERY = (
    f'TRUNCATE TABLE {KEYWORD_DIM_STAGING_TABLE_NAME};'
)

# Query to create a slowly changing dimensions (Type 2) table based on it's
# single dimension version (<dataset>.keywords). Will insert new rows and update
# rows that changed category.
MERGE_PROD_TO_SCD_QUERY = (
    'MERGE     {classifications_dataset}.keywords_scd AS scd USING    '
    ' {classifications_dataset}.keywords AS dim ON     scd.keyword_text ='
    ' dim.keyword_text WHEN NOT MATCHED THEN INSERT (     id,     keyword_text,'
    '     category_name,     start_datetime,     end_datetime ) VALUES (    '
    ' GENERATE_UUID(),     dim.keyword_text,     dim.category_name,    '
    ' dim.updated_at,     NULL     ) WHEN MATCHED AND scd.end_datetime IS NULL'
    ' AND scd.category_name <> dim.category_name THEN UPDATE SET'
    ' scd.end_datetime = dim.updated_at; INSERT INTO '
    ' {classifications_dataset}.keywords_scd ( id, keyword_text, category_name,'
    ' start_datetime, end_datetime ) ( SELECT   GENERATE_UUID(),'
    ' dim.keyword_text, dim.category_name, dim.updated_at as start_datetime,'
    ' NULL AS end_datetime FROM  {classifications_dataset}.keywords_scd AS scd'
    ' INNER JOIN  {classifications_dataset}.keywords AS dim ON dim.keyword_text'
    ' = scd.keyword_text AND dim.updated_at = scd.end_datetime AND'
    ' scd.category_name <> dim.category_name ); '
)
