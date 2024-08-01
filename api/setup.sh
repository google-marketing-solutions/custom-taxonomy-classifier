#!/bin/bash
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


# Suppress apt-get warnings if run in an ephemeral cloud shell.
mkdir ~/.cloudshell touch ~/.cloudshell/no-apt-get-warning
sudo apt-get install fzf

# Enable the APIs.
REQUIRED_APIS=(
  storage.googleapis.com
  iap.googleapis.com
  compute.googleapis.com
  run.googleapis.com
  cloudbuild.googleapis.com
  cloudresourcemanager.googleapis.com
)

for API in "${REQUIRED_APIS[@]}"; do
  gcloud services enable "$API"
done

# Get a list of accessible gcloud projects and store them in an array
projects=($(gcloud projects list --format="value(projectId)"))

# Use fzf to interactively select a project
selected_project=$(printf "%s\n" "${projects[@]}" | fzf --prompt="Select a project: ")

# Check if a project was selected
if [[ -n $selected_project ]]; then
    echo "Selected project: $selected_project"
    # Pass the selected project to a variable or use it directly in your script
    # For example, you can export it to make it available in the environment
    export GOOGLE_CLOUD_PROJECT="$selected_project"
else
    echo "No project selected."
fi

echo "Setting Project ID: ${GOOGLE_CLOUD_PROJECT}"
gcloud config set project "${GOOGLE_CLOUD_PROJECT}"

regions=($(gcloud compute regions list --format="value(name)"))

# Display a select menu for the user to choose a region
PS3="Select a region: "
select selected_region in "${regions[@]}"; do
    if [[ -n $selected_region ]]; then
        echo "Selected region: $selected_region"
        # Pass the selected region to a variable or use it directly in your script
        # For example, you can export it to make it available in the environment
        export GOOGLE_CLOUD_REGION="$selected_region"
        break
    else
        echo "Invalid choice, please select a valid region."
    fi
done

# Get other required info for the API.
echo "Enter a postgres database name."
read -r postgres_db_name
POSTGRES_DB_NAME=$postgres_db_name

echo "Enter the postgres DB user name the API will be using."
read -r postgres_db_user
POSTGRES_DB_USER=$postgres_db_user

echo "Enter a postgres DB password for the provided user."
read -r postgres_db_password
POSTGRES_DB_PASSWORD=$postgres_db_password

terraform_state_bucket_name="${GOOGLE_CLOUD_PROJECT}-bucket-tfstate"
classify_service_image="gcr.io/${GOOGLE_CLOUD_PROJECT}/classify-service"
taxonomy_job_image="gcr.io/${GOOGLE_CLOUD_PROJECT}/taxonomy-job"

# Create a GCS bucket to store terraform state files.
echo "Creating terraform state cloud storage bucket..."
gcloud storage buckets create gs://"${terraform_state_bucket_name}" \
  --project="${GOOGLE_CLOUD_PROJECT}"
# Enable versioning.
gcloud storage buckets update gs://"${terraform_state_bucket_name}" \
  --versioning

# Build docker images.
echo "Building API backend."
gcloud builds submit --config=cloudbuild.yaml \
  --substitutions _CLASSIFY_SERVICE_IMAGE="$classify_service_image",_TAXONOMY_JOB_IMAGE="$taxonomy_job_image"

echo "SUCCESS: Images built successfully."

# Setup & Run Terraform.
terraform -chdir=./terraform init \
  -backend-config="bucket=$terraform_state_bucket_name" \
  -get=true \
  -upgrade \
  -reconfigure

terraform -chdir=./terraform plan \
  -var "classify_service_image=$classify_service_image" \
  -var "taxonomy_job_image=$taxonomy_job_image" \
  -var "project_id=$GOOGLE_CLOUD_PROJECT" \
  -var "region=$GOOGLE_CLOUD_REGION" \
  -var "postgres_db_name=$POSTGRES_DB_NAME" \
  -var "postgres_db_user=$POSTGRES_DB_USER" \
  -var "postgres_db_password=$POSTGRES_DB_PASSWORD" \
  -out="/tmp/tfplan"

terraform_apply_exit_code=$(terraform -chdir=./terraform apply "/tmp/tfplan" | tee /dev/tty | ( ! grep "Error applying plan" ); echo $?)

if [[ "$terraform_apply_exit_code" -ne 0 ]]; then
  echo "--------------------------------------------------------------------------------------"
  echo "Oops! Something didn't work, ensure you have Project Owner permissions and try again. "
  echo "--------------------------------------------------------------------------------------"
else
  echo "-----------------------------------------------------"
  echo "Congrats! You successfully deployed Classify API."
  echo "-----------------------------------------------------"
fi