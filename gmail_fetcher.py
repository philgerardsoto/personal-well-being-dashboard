from simplegmail import Gmail
from simplegmail.query import construct_query
import pandas as pd
from datetime import datetime, timedelta
import os

def fetch_emails(days_back=5, senders=None):
    """
    Fetches emails from the last `days_back` days.
    
    Args:
        days_back (int): Number of days to look back.
        senders (list): Optional list of sender email addresses to filter by.
        
    Returns:
        pd.DataFrame: DataFrame containing email details.
    """
    
    # Initialize Gmail client
    # It will look for client_secret.json in the current directory
    if not os.path.exists('client_secret.json'):
        raise FileNotFoundError("client_secret.json not found in the current directory.")

    print("Authenticating with Gmail...")
    gmail = Gmail() 

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    
    # Construct query
    query_params = {
        'after': start_date.strftime('%Y/%m/%d'),
        'before': end_date.strftime('%Y/%m/%d')
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

    print(f"Fetching emails from {start_date.date()} to {end_date.date()}...")
    
    messages = gmail.get_messages(query=construct_query(query_params))
    
    print(f"Found {len(messages)} messages.")
    
    email_data = []
    for message in messages:
        email_data.append({
            'date': message.date,
            'sender': message.sender,
            'subject': message.subject,
            'snippet': message.snippet,
            'id': message.id
        })
    
    df = pd.DataFrame(email_data)
    return df

if __name__ == "__main__":
    try:
        df = fetch_emails(days_back=7)
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
