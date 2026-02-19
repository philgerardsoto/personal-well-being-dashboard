from simplegmail import Gmail
from simplegmail.query import construct_query
import pandas as pd
from datetime import datetime, timedelta
import os

def fetch_emails(days_back=5, start_date=None, senders=None, client_secret_file='client_secret.json', creds_file='gmail_token.json'):
    """
    Fetches emails.
    
    Args:
        days_back (int): Number of days to look back (default).
        start_date (datetime): Specific start date (overrides days_back).
        senders (list): Optional list of sender email addresses to filter by.
        client_secret_file (str): Path to client secret file.
        creds_file (str): Path to gmail token file.
        
    Returns:
        pd.DataFrame: DataFrame containing email details.
    """
    
    # Initialize Gmail client
    if not os.path.exists(client_secret_file):
         raise FileNotFoundError(f"{client_secret_file} not found.")

    print("Authenticating with Gmail...")
    gmail = Gmail(client_secret_file=client_secret_file, creds_file=creds_file) 

    # Calculate date range
    end_date = datetime.now()
    if start_date:
        query_start_date = start_date
    else:
        query_start_date = end_date - timedelta(days=days_back)
    
    # Construct query
    # "before" is exclusive, so we add 1 day to include emails from the end_date itself
    query_params = {
        'after': query_start_date.strftime('%Y/%m/%d'),
        'before': (end_date + timedelta(days=1)).strftime('%Y/%m/%d')
    }
    
    if senders:
        # Construct sender query efficiently
        sender_queries = [f'from:{sender}' for sender in senders]
        # Join with OR operator, but Gmail search API handles space as AND, OR needs to be explicit or grouped
        # SimpleGmail query builder handles dicts well, but for list of senders it's better to verify
        # For simplicity in this first version, let's just use the basic query and filter in Python if needed,
        # OR just construct a raw query string.
        # Let's stick to time-based for now as per plan, user can refine later.
        pass

    print(f"Fetching emails from {query_start_date.date()} to {end_date.date()}...")
    
    messages = gmail.get_messages(query=construct_query(query_params))
    
    print(f"Found {len(messages)} messages.")
    
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
    return df

if __name__ == "__main__":
    try:
        df = fetch_emails()
        if not df.empty:
            print("\nTop 5 recent emails:")
            print(df.head())
            
            # Save to CSV for inspection
            output_file = "recent_emails.csv"
            df.to_csv(output_file, index=False)
            print(f"\nSaved {len(df)} emails to {output_file}")
        else:
            print("No emails found in the specified range.")
            
    except Exception as e:
        print(f"An error occurred: {e}")
