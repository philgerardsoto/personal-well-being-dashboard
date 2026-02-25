import os
import logging
import dlt
import dlt.destinations
from dlt.common.typing import TDataItem
from simplegmail import Gmail
from simplegmail.query import construct_query
import pandas as pd
from datetime import datetime, timedelta
from google.cloud import secretmanager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Secret Manager Config
PROJECT_ID = os.environ.get("PROJECT_ID")
SECRET_ID_TOKEN = "gmail-token"
SECRET_ID_CLIENT = "client-secret"

def access_secret_version(secret_id, version_id="latest"):
    """Accesses a secret version in Secret Manager."""
    if not PROJECT_ID:
        raise ValueError("PROJECT_ID must be set in environment variables to access Secret Manager.")
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_id}/versions/{version_id}"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

def setup_credentials_files():
    """Fetches secrets from Secret Manager and writes them to temp files."""
    logger.info("Fetching credentials from Secret Manager...")
    try:
        token_data = access_secret_version(SECRET_ID_TOKEN)
        client_data = access_secret_version(SECRET_ID_CLIENT)
        
        # Write to temp files
        token_path = "/tmp/gmail_token.json"
        client_path = "/tmp/client_secret.json"
        
        # Ensure /tmp exists on Windows for compatibility or use a more robust temp dir
        os.makedirs("/tmp", exist_ok=True)
        
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
             raise FileNotFoundError("Credentials not found in Secret Manager or locally. Please authenticate.")

# Pydantic is native to dlt for strict schemas, but we can also define them as dicts.
# We'll use dlt's built-in column hinting for strictness.
@dlt.resource(
    name="gmail_messages",
    write_disposition="merge",
    primary_key="id",
)
def fetch_gmail_resource(
    start_date: dlt.sources.incremental[str] = dlt.sources.incremental(
        "date",
        initial_value="2026-02-23T00:00:00Z" # Default to fetching from start of Feb 23, 2026 if no state exists
    )
) -> TDataItem:
    """
    DLT Resource that wraps the existing simplegmail fetcher.
    Tracks state via the 'date' field.
    """
    
    # DLT's incremental start_date is either the initial_value, 
    # or the last successfully loaded date.
    last_load_date = start_date.last_value
    
    # gmail_fetcher expects a datetime object for start_date
    query_start_date = None
    if last_load_date:
        if isinstance(last_load_date, str):
            # Parse the string format we expect back from BQ/dlt
            try:
                # Handle standard ISO format from BQ
                query_start_date = datetime.fromisoformat(last_load_date.replace('Z', '+00:00'))
            except ValueError:
                # Fallback purely in case
                logger.warning(f"Could not parse last_value {last_load_date}. Falling back to default fetch.")
        elif isinstance(last_load_date, datetime):
            query_start_date = last_load_date

    logger.info(f"DLT Incremental Cursor (start_date): {query_start_date}")

    # Fetch secrets or use local files
    client_secret_path, token_path = setup_credentials_files()

    # Initialize Gmail client
    try:
        if not os.path.exists(client_secret_path):
            raise FileNotFoundError(f"{client_secret_path} not found.")
        gmail = Gmail(client_secret_file=client_secret_path, creds_file=token_path)
    except Exception as e:
        logger.error(f"Failed to authenticate with Gmail: {e}")
        raise

    # Calculate date range
    end_date = datetime.now()
    if not query_start_date:
        query_start_date = end_date - timedelta(days=5) # Default 5 days back
    
    # Construct query
    query_params = {
        'after': query_start_date.strftime('%Y/%m/%d'),
        'before': (end_date + timedelta(days=1)).strftime('%Y/%m/%d')
    }
    
    logger.info(f"Fetching emails from {query_start_date.date()} to {end_date.date()}...")
    
    messages = gmail.get_messages(query=construct_query(query_params))
    
    logger.info(f"Found {len(messages)} messages.")
    
    email_data = []
    for message in messages:
        email_data.append({
            'id': message.id,
            'thread_id': message.thread_id,
            'date': message.date,
            'sender': message.sender,
            'recipient': message.recipient,
            'subject': message.subject,
            'snippet': message.snippet,
            'body': message.plain,
            'labels': message.label_ids,
            'cc': message.cc,
            'bcc': message.bcc
        })
    
    df = pd.DataFrame(email_data)
    
    if df.empty:
        logger.info("No new emails found.")
        return

    # Transform list columns to comma-separated strings
    list_cols = ['labels', 'cc', 'bcc']
    for col in list_cols:
        df[col] = df[col].apply(lambda x: ", ".join([str(item) for item in x]) if isinstance(x, (list, tuple)) else str(x) if x is not None else None)

    # Yield the dataframe to DLT (DLT can consume DataFrames natively)
    yield df


# Define the source and attach the schema definition
@dlt.source(name="personal_email")
def my_gmail_source():
    # We apply the strict schema contract here
    resource = fetch_gmail_resource()
    
    # Apply schema types and structure explicitly
    resource.apply_hints(
        schema_contract="freeze", # Fail the pipeline if data doesn't match this schema
        columns={
            "id": {"data_type": "text", "nullable": False},
            "thread_id": {"data_type": "text", "nullable": True},
            "date": {"data_type": "timestamp", "nullable": False},
            "sender": {"data_type": "text", "nullable": True},
            "recipient": {"data_type": "text", "nullable": True},
            "subject": {"data_type": "text", "nullable": True},
            "snippet": {"data_type": "text", "nullable": True},
            "body": {"data_type": "text", "nullable": True},
            "labels": {"data_type": "text", "nullable": True}, 
            "cc": {"data_type": "text", "nullable": True},
            "bcc": {"data_type": "text", "nullable": True},
        }
    )
    return resource

def main():
    # 1. Initialize Pipeline
    pipeline_name = "pwbd_gmail_pipeline"
    dataset_name = "digital"
    
    destination = dlt.destinations.bigquery(
        credentials=dlt.secrets.value,
        location="asia-southeast1" # Explicitly set BQ dataset location
    ) if os.environ.get("PROJECT_ID") else "duckdb"
    
    logger.info(f"Initializing DLT pipeline targeting: {'bigquery (asia-southeast1)' if os.environ.get('PROJECT_ID') else 'duckdb'}")
    
    pipeline = dlt.pipeline(
        pipeline_name=pipeline_name,
        destination=destination,
        dataset_name=dataset_name,
    )

    # 2. Run Pipeline
    load_info = pipeline.run(
        my_gmail_source(),
        loader_file_format="jsonl"
    )

    # 3. Log Results
    logger.info(load_info)

if __name__ == "__main__":
    main()
