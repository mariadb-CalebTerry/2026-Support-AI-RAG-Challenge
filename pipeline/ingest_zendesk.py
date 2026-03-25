import os
import requests
import sys
import json
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN")
ZENDESK_TOKEN = os.getenv("ZENDESK_OAUTH_TOKEN")
RAG_API_URL = os.getenv("RAG_API_URL", "http://localhost:8000")
RAG_API_USER = os.getenv("RAG_API_USER", "admin")
RAG_API_PASSWORD = os.getenv("RAG_API_PASSWORD", os.getenv("DB_PASSWORD", "mariadb_rag_password_2024"))

TEMP_DIR = "/tmp/zendesk_attachments"
if os.name == 'nt':
    TEMP_DIR = os.path.join(os.environ.get('TEMP', 'C:\\Temp'), "zendesk_attachments")

os.makedirs(TEMP_DIR, exist_ok=True)

def get_rag_api_token():
    print(f"Authenticating with RAG API at {RAG_API_URL}...")
    try:
        response = requests.post(
            f"{RAG_API_URL}/token",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={"username": RAG_API_USER, "password": RAG_API_PASSWORD}
        )
        response.raise_for_status()
        return response.json().get("access_token")
    except requests.exceptions.RequestException as e:
        print(f"Error authenticating with RAG API: {e}")
        sys.exit(1)

def generate_metadata(ticket, is_attachment=False, attachment_name=None):
    subject = ticket.get("subject", "").lower() if ticket.get("subject") else ""
    description = ticket.get("description", "").lower() if ticket.get("description") else ""
    content = f"{subject} {description}"
    
    # Determine technical area
    technical_area = "general"
    if any(w in content for w in ["slow", "memory", "cpu", "performance"]):
        technical_area = "performance"
    elif any(w in content for w in ["replica", "master", "slave", "gtid", "binlog"]):
        technical_area = "replication"
    elif any(w in content for w in ["connection", "timeout", "refused"]):
        technical_area = "connectivity"
    elif any(w in content for w in ["backup", "restore", "dump"]):
        technical_area = "backup"
    
    # Determine ticket type
    ticket_type = "general"
    if any(w in content for w in ["bug", "error", "issue", "problem"]):
        ticket_type = "bug"
    elif any(w in content for w in ["how to", "guide", "help"]):
        ticket_type = "howto"
        
    # Determine complexity
    complexity = "basic"
    if technical_area in ["performance", "replication"] or "advanced" in content:
        complexity = "advanced"
        
    metadata = {
        "ticket_id": ticket.get("id"),
        "ticket_type": ticket_type,
        "technical_area": technical_area,
        "complexity": complexity,
        "is_attachment": is_attachment,
        "status": ticket.get("status", "unknown"),
        "source": "zendesk"
    }
    
    if attachment_name:
        metadata["attachment_name"] = attachment_name
        
    return metadata

def fetch_zendesk_tickets(limit=None):
    print(f"Fetching tickets from Zendesk (Limit: {limit if limit else 'None'})...")
    url = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/tickets.json"
    headers = {
        "Authorization": f"Bearer {ZENDESK_TOKEN}",
        "Content-Type": "application/json",
    }

    tickets = []
    while url:
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            if hasattr(e, 'response') and e.response is not None and e.response.status_code == 429:
                retry_after = int(e.response.headers.get("Retry-After", 60))
                print(f"Rate limited. Waiting for {retry_after} seconds...")
                time.sleep(retry_after)
                continue
            else:
                print(f"Failed to fetch tickets: {e}")
                break

        data = response.json()
        tickets.extend(data.get("tickets", []))

        if limit and len(tickets) >= limit:
            tickets = tickets[:limit]
            break

        url = data.get("next_page")

    return tickets

def fetch_ticket_comments(ticket_id):
    url = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/tickets/{ticket_id}/comments.json"
    headers = {
        "Authorization": f"Bearer {ZENDESK_TOKEN}",
        "Content-Type": "application/json",
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json().get("comments", [])
    except requests.exceptions.RequestException as e:
        if hasattr(e, 'response') and e.response is not None and e.response.status_code == 429:
            retry_after = int(e.response.headers.get("Retry-After", 60))
            time.sleep(retry_after)
            return fetch_ticket_comments(ticket_id)
        print(f"Failed to fetch comments for ticket {ticket_id}: {e}")
        return []

def download_attachment(url, filename):
    headers = {"Authorization": f"Bearer {ZENDESK_TOKEN}"}
    local_path = os.path.join(TEMP_DIR, filename)
    try:
        with requests.get(url, headers=headers, stream=True) as r:
            r.raise_for_status()
            with open(local_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        return local_path
    except requests.exceptions.RequestException as e:
        print(f"Failed to download attachment {filename}: {e}")
        return None

def ingest_to_rag_api(file_path, metadata, token):
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f)}
            data = {'metadata': json.dumps(metadata)}
            
            response = requests.post(
                f"{RAG_API_URL}/documents/ingest",
                headers=headers,
                files=files,
                data=data
            )
            response.raise_for_status()
            print(f"Successfully ingested {os.path.basename(file_path)}")
            return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to ingest {os.path.basename(file_path)}: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return False

def ingest_data(tickets, token):
    print(f"Processing and ingesting {len(tickets)} tickets into RAG API...")

    for ticket in tickets:
        ticket_id = ticket["id"]
        print(f"Processing ticket #{ticket_id}...")
        
        # 1. Fetch comments and build summary
        comments = fetch_ticket_comments(ticket_id)
        
        summary_md = f"# Ticket #{ticket_id}: {ticket.get('subject', 'No Subject')}\n\n"
        summary_md += f"**Status:** {ticket.get('status', 'unknown')}\n"
        summary_md += f"**Created:** {ticket.get('created_at')}\n\n"
        summary_md += f"## Description\n{ticket.get('description', '')}\n\n"
        summary_md += "## Comments\n"
        
        attachments = []
        for comment in comments:
            summary_md += f"### Comment by {comment.get('author_id')} at {comment.get('created_at')}\n"
            summary_md += f"{comment.get('body', '')}\n\n"
            if comment.get("attachments"):
                attachments.extend(comment["attachments"])
                
        # Save summary to temp file
        summary_filename = f"ticket_{ticket_id}_summary.md"
        summary_path = os.path.join(TEMP_DIR, summary_filename)
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary_md)
            
        # Generate metadata and ingest summary
        metadata = generate_metadata(ticket, is_attachment=False)
        if ingest_to_rag_api(summary_path, metadata, token):
            os.remove(summary_path)
            
        # 2. Process attachments
        for att in attachments:
            att_filename = f"ticket_{ticket_id}_{att['file_name']}"
            att_url = att['content_url']
            
            print(f"  Downloading attachment: {att_filename}...")
            local_att_path = download_attachment(att_url, att_filename)
            
            if local_att_path:
                att_metadata = generate_metadata(ticket, is_attachment=True, attachment_name=att['file_name'])
                if ingest_to_rag_api(local_att_path, att_metadata, token):
                    os.remove(local_att_path)

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest Zendesk Data into MariaDB AI RAG via API")
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit the number of tickets to ingest (subset)",
        default=None,
    )
    args = parser.parse_args()

    if not ZENDESK_SUBDOMAIN or not ZENDESK_TOKEN:
        print("Error: ZENDESK_SUBDOMAIN and ZENDESK_OAUTH_TOKEN environment variables must be set in .env")
        sys.exit(1)

    rag_token = get_rag_api_token()
    tickets = fetch_zendesk_tickets(limit=args.limit)
    
    if tickets:
        ingest_data(tickets, rag_token)
    else:
        print("No tickets found to ingest.")

    print("Ingestion complete.")
