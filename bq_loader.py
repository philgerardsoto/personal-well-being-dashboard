import os
import io
import json
import logging
import pandas as pd
from datetime import datetime, timedelta
from google.cloud import bigquery
from google.cloud import secretmanager
import gmail_fetcher

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
PROJECT_ID = os.environ.get("PROJECT_ID")
DATASET_ID = "digital" # TODO: Make configurable or environmental
TABLE_ID = "gmail_raw"
SECRET_ID_TOKEN = "gmail-token"
SECRET_ID_CLIENT = "client-secret"

def access_secret_version(secret_id, version_id="latest"):
    """
    Accesses a secret version in Secret Manager.
    """
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

def setup_credentials_files():
    """
    Fetches secrets from Secret Manager and writes them to temp files.
    Returns the paths to these files.
    """
    logger.info("Fetching credentials from Secret Manager...")
    try:
        token_data = access_secret_version(SECRET_ID_TOKEN)
        client_data = access_secret_version(SECRET_ID_CLIENT)
        
        # Write to temp files
        token_path = "/tmp/gmail_token.json"
        client_path = "/tmp/client_secret.json"
        
        with open(token_path, "w") as f:
            f.write(token_data)
        
        with open(client_path, "w") as f:
            f.write(client_data)
            
        return client_path, token_path
    
    except Exception as e:
        logger.warning(f"Could not fetch secrets from Secret Manager: {e}")
        logger.info("Assuming local execution and checking for local files.")
        if os.path.exists("client_secret.json") and os.path.exists("gmail_token.json"):
             return "client_secret.json", "gmail_token.json"
        else:
             raise FileNotFoundError("Credentials not found in Secret Manager or locally.")

def get_max_date_from_bq(client, table_ref):
    """
    Queries BigQuery for the maximum date in the table.
    """
    try:
        query = f"SELECT MAX(date) as max_date FROM `{table_ref}`"
        query_job = client.query(query)
        results = query_job.result()
        for row in results:
            return row.max_date
    except Exception as e:
        logger.info(f"Table might not exist or is empty: {e}")
        return None

def load_to_bigquery(df, client, table_ref):
    """
    Loads DataFrame to BigQuery using ARRAYS for list columns.
    """
    # Transform list columns to be compatible with BQ Arrays
    # Pandas lists often need to be ensured they are actual lists, not strings
    list_cols = ['labels', 'cc', 'bcc']
    for col in list_cols:
        df[col] = df[col].apply(lambda x: [str(item) for item in x] if isinstance(x, (list, tuple)) else [])

    # Convert date column to datetime objects for BigQuery TIMESTAMP
    df['date'] = pd.to_datetime(df['date'], utc=True)

    # Configure job options for Append
    job_config = bigquery.LoadJobConfig(
        write_disposition="WRITE_APPEND",
        schema=[
            bigquery.SchemaField("id", "STRING"),
            bigquery.SchemaField("thread_id", "STRING"),
            bigquery.SchemaField("date", "TIMESTAMP"),
            bigquery.SchemaField("sender", "STRING"),
            bigquery.SchemaField("recipient", "STRING"),
            bigquery.SchemaField("subject", "STRING"),
            bigquery.SchemaField("snippet", "STRING"),
            bigquery.SchemaField("body", "STRING"),
            bigquery.SchemaField("labels", "STRING", mode="REPEATED"),
            bigquery.SchemaField("cc", "STRING", mode="REPEATED"),
            bigquery.SchemaField("bcc", "STRING", mode="REPEATED"),
        ],
    )

    logger.info(f"Loading {len(df)} rows to {table_ref}...")
    job = client.load_table_from_dataframe(df, table_ref, job_config=job_config)
    job.result()  # Wait for the job to complete
    logger.info("Loaded successfully.")

def main():
    if not PROJECT_ID:
        logger.error("PROJECT_ID environment variable not set.")
        return

    # 1. Setup Auth
    client_secret_path, token_path = setup_credentials_files()
    
    # 2. Init BQ
    bq_client = bigquery.Client(project=PROJECT_ID)
    table_ref = f"{PROJECT_ID}.{DATASET_ID}.{TABLE_ID}"
    
    # 3. Get Incremental State
    max_date = get_max_date_from_bq(bq_client, table_ref)
    start_date = None
    
    if max_date:
        # Add a small buffer to ensure we don't miss anything, duplicates handled by ID usually?
        # Actually, let's just use the max date. Our fetcher uses "after: YYYY/MM/DD".
        # Gmail API date filter is day-granularity.
        # If max_date is today, we fetch today again.
        start_date = max_date
        logger.info(f"Incremental load: Fetching emails since {start_date}")
    else:
        logger.info("Initial load: Fetching default history.")

    # 4. Fetch Data
    df = gmail_fetcher.fetch_emails(
        start_date=start_date,
        client_secret_file=client_secret_path,
        creds_file=token_path
    )
    
    if df.empty:
        logger.info("No new emails found.")
        return

    # 5. Load/Upsert
    # Basic Append for now. 
    # Improvement: Identify IDs already in BQ?
    # For now, let's just load. A 'MERGE' query would be better for true upsert.
    load_to_bigquery(df, bq_client, table_ref)

if __name__ == "__main__":
    main()
