# Personal Well-being Dashboard

In recent years, there has been a significant increase in business investments in data infrastructure and capabilities. This is due to the realization of the immense value in consolidating data from various systems or sources, providing a comprehensive view of different facets of the business. The rise in popularity of various data tools aligns with the acknowledgment that data-driven insights can lead to improved decision-making and strategic planning.

Similarly, the Personal Well-being Dashboard aims to help individuals consolidate various aspects of their well-being: physical, financial, and digital. The goal of the project is not to consolidate data from various individuals, but to enable each person to access their own stats for personal consumption.

While the ultimate aim is a dashboard, the majority of the project will be focused on the data engineering aspect: ingesting, transforming, and modeling data. We aim for the process to be as automated and streamlined as possible.

## Setup Guide

### Local Development
1.  **Clone the repository**:
    ```bash
    git clone https://github.com/philgerardsoto/personal-well-being-dashboard.git
    cd personal-well-being-dashboard
    ```

2.  **Create Virtual Environment**:
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

3.  **Local Credentials (Required for BQ & Secret Manager)**:
    - Place your `client_secret.json` in the root directory.
    - Run `python gmail_fetcher.py` once locally to generate `gmail_token.json`.    
    If you want to run `gmail_pipeline.py` locally to extract and load data using `dlt`:
    1. Authenticate with your Google account:
    ```bash
    gcloud auth application-default login
    ```
    2. Run the pipeline with your Google Cloud Project ID:
    ```bash
    # Windows CMD
    set PROJECT_ID=[YOUR_PROJECT_ID]&& python gmail_pipeline.py
    
    # Linux/Mac
    export PROJECT_ID=[YOUR_PROJECT_ID]
    python gmail_pipeline.py
    ```
    This allows the script to access Secret Manager and BigQuery on your behalf.

### Cloud Deployment (Google Cloud Run)
This project is designed to run as a **Cloud Run Job**, using **Secret Manager** for credentials.

1.  **Prerequisites**:
    - Google Cloud Project with Billing Enabled.
    - `gcloud` CLI installed and authenticated.

2.  **Enable APIs**:
    ```bash
    gcloud services enable secretmanager.googleapis.com run.googleapis.com artifactregistry.googleapis.com cloudbuild.googleapis.com cloudscheduler.googleapis.com
    ```

3.  **Setup Secrets**:
    Store your local credentials in Google Cloud Secret Manager:
    ```bash
    gcloud secrets create gmail-token --data-file=gmail_token.json
    gcloud secrets create client-secret --data-file=client_secret.json
    ```

4.  **Create Service Account**:
    Create a runner account and give it access to Secrets and BigQuery:
    ```bash
    gcloud iam service-accounts create pwbd-runner
    
    # Grant Secret Access
    gcloud projects add-iam-policy-binding [YOUR_PROJECT_ID] \
      --member="serviceAccount:pwbd-runner@[YOUR_PROJECT_ID].iam.gserviceaccount.com" \
      --role="roles/secretmanager.secretAccessor"
      
    # Grant BigQuery Access
    gcloud projects add-iam-policy-binding [YOUR_PROJECT_ID] \
      --member="serviceAccount:pwbd-runner@[YOUR_PROJECT_ID].iam.gserviceaccount.com" \
      --role="roles/bigquery.dataEditor"
    ```

5.  **Deploy**:
    ```bash
    gcloud run jobs deploy pwbd-loader \
      --source . \
      --service-account pwbd-runner@[YOUR_PROJECT_ID].iam.gserviceaccount.com \
      --region asia-southeast1
    ```

6.  **Create Cloud Scheduler (Daily Trigger)**:
    Set up the Cloud Scheduler to trigger the loader automatically every day (e.g., at 12:30 AM PHT):
    ```bash
    gcloud scheduler jobs create http pwbd-loader-trigger \
      --location asia-southeast1 \
      --schedule="30 0 * * *" \
      --time-zone="Asia/Manila" \
      --uri="https://asia-southeast1-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/[YOUR_PROJECT_ID]/jobs/pwbd-loader:run" \
      --http-method=POST \
      --oauth-service-account-email="pwbd-runner@[YOUR_PROJECT_ID].iam.gserviceaccount.com" \
      --project [YOUR_PROJECT_ID]
    ```

## Contributing
We're looking for anyone who wants to contribute! No prior experience is required. You can contribute in any capacity that matches your skills and interests. We can also provide guidance if needed.

## Useful links:
- [Data and Work Flow GSheet](https://docs.google.com/spreadsheets/d/1SJqBCFfW5xbAVZHrJTgjHP72mbmL_OkWQybg7wFjV3E/edit?usp=sharing)
- [Collaboration GSheet](https://docs.google.com/spreadsheets/d/1CqKHzhlnyljzaUbkVFH_9-DAhEfuX9-Owumpikoj8gM/edit?usp=sharing)
- [Facebook Group Chat](https://m.me/j/AbaL6CMK9vjk3U8l/)
- [Youtube Project Intro Videos](https://www.youtube.com/watch?v=Gup80_6nNw4&list=PLgB1IGvclbuMWY6V9Z4dgL370FpqvyAlM)

## Credits
Credits are given to below repositories.
Please refer to their documentation for the setup guides:
- https://github.com/jeremyephron/simplegmail
- https://github.com/sladkovm/stravaio
