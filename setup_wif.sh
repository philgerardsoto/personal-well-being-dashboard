#!/bin/bash
# setup_wif.sh
# Helper script to setup Workload Identity Federation for GitHub Actions

export PROJECT_ID=$(gcloud config get-value project)
export REPO="philgerardsoto/personal-well-being-dashboard" # Adjust if needed
export APP_NAME="pwbd"
export SERVICE_ACCOUNT="pwbd-runner"

echo "Setting up Workload Identity Federation for Project: $PROJECT_ID"

# 1. Create Artifact Registry Repository
gcloud artifacts repositories create pwbd-repo \
    --repository-format=docker \
    --location=us-central1 \
    --description="Docker repository for PWBD"

# 2. Create Workload Identity Pool
gcloud iam workload-identity-pools create "${APP_NAME}-pool" \
    --project="${PROJECT_ID}" \
    --location="global" \
    --display-name="${APP_NAME} Pool"

export WORKLOAD_IDENTITY_POOL_ID=$(gcloud iam workload-identity-pools describe "${APP_NAME}-pool" \
  --project="${PROJECT_ID}" \
  --location="global" \
  --format="value(name)")

# 3. Create Provider
gcloud iam workload-identity-pools providers create-oidc "${APP_NAME}-provider" \
    --project="${PROJECT_ID}" \
    --location="global" \
    --workload-identity-pool="${APP_NAME}-pool" \
    --display-name="${APP_NAME} Provider" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
    --issuer-uri="https://token.actions.githubusercontent.com"

# 4. Allow GitHub Repo to impersonate Service Account
gcloud iam service-accounts add-iam-policy-binding "${SERVICE_ACCOUNT}@${PROJECT_ID}.iam.gserviceaccount.com" \
    --project="${PROJECT_ID}" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/${WORKLOAD_IDENTITY_POOL_ID}/attribute.repository/${REPO}"

# 5. Output for GitHub Secrets
echo ""
echo "--------------------------------------------------------"
echo "SETUP COMPLETE! Add these to your GitHub Repository Secrets:"
echo "--------------------------------------------------------"
echo "GCP_PROJECT_ID: $PROJECT_ID"
echo "GCP_WORKLOAD_IDENTITY_PROVIDER: projects/${PROJECT_ID}/locations/global/workloadIdentityPools/${APP_NAME}-pool/providers/${APP_NAME}-provider"
echo "--------------------------------------------------------"
