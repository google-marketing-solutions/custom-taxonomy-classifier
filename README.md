# Customer Classification API

## Problem

Existing classification APIs such as Cloud NLP and others may not accurately
reflect a company's business lines, product categories or segments. Training a
custom model for classifying text content into a custom taxonomy is costly and
time-consuming.

## Solution

Using an existing LLM's text embeddings we can calculate the dot product
similarity and apply unit-norm normalization for a given piece of text and every
category in a custom taxonomy. The higher the dot product similarity the higher
the confidence that the passed text is part of that category. Dot Product
Similarity is a standard metric in natural language classification systems and
has several advantages. Most importantly, it measures the similarity between
text and categories by calculating the cosine of the angle between their vector
representations. The dot product of the vectors are then calculated by
multiplying their corresponding elements and summing the results. The cosine of
the angle between them is then calculated by dividing the dot product by the
product of the magnitudes of the vectors. It also works well with
high-dimensional text data containing many zero elements and scores ranging from
0 (no similarity) to 1 (perfect match), providing intuitive insights.

## Prerequisites

1.  The user deploying the application to Google Cloud must be a `Project
    Owner`.
2.  Have a Google Spreadsheet containing the taxonomy (list of category names).

## Deployment

To deploy, run the following commands in a Google Cloud Shell and follow the
instructions. If there's a problem with the deployment then address the error
message and run the command again.

```sh
git clone https://professional-services.googlesource.com/solutions/custom_taxonomy_classifier && \
cd custom_taxonomy_classifier/api && \
chmod 775 ./setup.sh && \
./setup.sh
```

Grant the application service account `Viewer` access to the Google Spreadsheet
containing the taxonomy. Replace the `<your-cloud-project-id>` with the name of
the Google Cloud project you intend to use.

`classify-api-sa@<your-cloud-project-id>.iam.gserviceaccount.com`

## Usage

The API has 3 endpoints:

1.  **POST /generate_taxonomy_embeddings**

    Used to generate and store the vector embeddings for each of the taxonomy
    nodes. This will run as a background process and returns a task_id.

1.  **GET /task_status/{task_id}**

    Used to get the current status of the background process to generate and
    store the taxonomy embeddings vectors.

1.  **POST /classify**

    Used to get the top 10 categories in terms of embeddings vector similarity
    for the passed text. The below graph illustrates the architecture for the
    classify call:

### Generate Taxonomy Embeddings

The endpoint triggers a background process to get the category names from a
Google Spreadsheet, generates their embeddings and writes them to a postgres
database. Calling the endpoint creates a task, which can be used to retrieve the
task status using the task_status endpoint.

#### Request format

**Parameters**

*   *spreadsheet_id* (required): The ID of the Google Spreadsheet.
*   *worksheet_name* (required): The name of the worksheet that contains the
    taxonomy.
*   *worksheet_col_index* (required): The 1-based column index of the column
    containing the list of categories.
*   *header* (optional): Whether or not the column has a header row. Defaults to
    true.

```sh
curl -X POST \
-H "Authorization: Bearer $(gcloud auth print-identity-token)" \
-H 'Content-Type: application/json' \
-d '{"spreadsheet_id": "[YOUR-GOOGLE-SPREADSHEET-ID]", "worksheet_name": "Sheet1", "worksheet_col_index": "1", "header": "False"}' \
-i [YOUR-CLOUD-RUN-URL]/generate_taxonomy_embeddings
```

#### Response format

The API response will return a task_id including a message.

**Attributes**

*   *task_id*: The ID of the task created by the background process.
*   *message*: An informational message about the task creation.

```sh
{
  "task_id": "9687244b-6883-474a-97f6-a29f5f91b522",
  "message": "Generate Taxonomy Embeddings task sent in the background."
}
```

### Task Status

The endpoint can be used to retrieve the current status of a particular task.

#### Request format

**Parameters**

*   *task_id* (required): The ID of the Google Spreadsheet.

```sh
curl -X GET \
-H "Authorization: Bearer $(gcloud auth print-identity-token)" \
-i [YOUR-CLOUD-RUN-URL]/task_status/9687244b-6883-474a-97f6-a29f5f91b522
```

#### Response format

The API response will return a task_id including a message.

**Attributes**

*   *task_id*: The ID of the task created by the background process.
*   *status*: The status of the task.
*   *created_time*: The time the task was created.
*   *updated_time*: The time the task was last updated.
*   *message*: An informational message about the task. Is empty by fault but
    will be populated on error.

```sh
{
  "task_id": "9687244b-6883-474a-97f6-a29f5f91b522",
  "status": "SUCCESS",
  "created_time": "2024-01-17T15:07:52.633122Z",
  "created_updated": "2024-01-17T15:11:42.954784Z",
  "message": null
}
```

### Classify

The endpoint returns a list of the top 10 best matching categories, along with
their corresponding scores (similarity).

#### Request format

**Parameters**

*   *text* (optional): The text content to classify. This can be a single string
    or a list of strings.
*   *media_uri* (optional): The media to classify. This can be a single file
    path to a GCS location or a list of file paths. Note that only the following
    media extensions are supported: `.jpg, .jpeg, .png, .x-flv, .mov, .mpeg,
    .mpegps, .mpg, .mp4, .webm, .wmv, .3gpp`

With a list of strings:

```sh
curl -X POST \
-H "Authorization: Bearer $(gcloud auth print-identity-token)" \
-H 'Content-Type: application/json' \
-d '{"text": ["Text to classify","Some other Text to classify"]}' \
-i [YOUR-CLOUD-RUN-URL]/classify
```

With a single string:

```sh
curl -X POST \
-H "Authorization: Bearer $(gcloud auth print-identity-token)" \
-H 'Content-Type: application/json' \
-d '{"text": "Text to classify"}' \
-i [YOUR-CLOUD-RUN-URL]/classify
```

#### Response format

The API response will show the top 10 categories in terms of dot product
similarity to the passed text.

##### Categories Similarity Object

**Attributes**:

*   *name*: The name of the category within the given taxonomy.
*   *similarity*: A float of the dot product similarity of the category to the
    passed text.

##### Results Object

**Attributes**:

*   *text*: The text content string to classify.
*   *categories*: An array containing category similarity objects.

**Example Response**:

The below would be a response for the following request data:

```sh
{
  "text": "Text to classify",
  "media_uri": "gs://path/to/image.jpg"
}
```

```sh
[
  {
    "text": "Text to classify"
    "media_uri": "null",
    "categories": [
      {
        "name": "Some category",
        "similarity": 0.9
      },
      {
        "name": "Some other category",
        "similarity": 0.8
      },
      ...
    ]
  },
  {
    "text": "null",
    "media_uri": "gs://path/to/image.jpg",
    "categories": [
      {
        "name": "Some category",
        "similarity": 0.9
      },
      {
        "name": "Some other category",
        "similarity": 0.8
      },
      ...
    ]
  }
]
```
