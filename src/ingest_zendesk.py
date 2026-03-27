import os
import requests
import sys
import json
import time
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from requests_toolbelt import MultipartEncoder

# Load environment variables
load_dotenv("config.env")

# Configure global session with connection pooling
session = requests.Session()
adapter = HTTPAdapter(pool_connections=20, pool_maxsize=20)
session.mount('http://', adapter)
session.mount('https://', adapter)

ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN")
ZENDESK_TOKEN = os.getenv("ZENDESK_OAUTH_TOKEN")
RAG_API_URL = os.getenv("RAG_API_URL", "http://localhost:8000")
RAG_API_USER = os.getenv("RAG_API_USER", "admin")
RAG_API_PASSWORD = os.getenv(
    "RAG_API_PASSWORD", os.getenv("DB_PASSWORD", "mariadb_rag_password_2024")
)

TEMP_DIR = "/tmp/zendesk_attachments"
if os.name == "nt":
    TEMP_DIR = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "zendesk_attachments")

os.makedirs(TEMP_DIR, exist_ok=True)

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ingestion_state.db")

_token_cache = None
_token_lock = threading.Lock()
_db_lock = threading.Lock()


def setup_sqlite_db():
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS processed_items (item_id TEXT PRIMARY KEY, processed_at TIMESTAMP)"
    )
    conn.commit()
    return conn


def is_processed(conn, item_id):
    with _db_lock:
        c = conn.cursor()
        c.execute("SELECT 1 FROM processed_items WHERE item_id = ?", (item_id,))
        return c.fetchone() is not None


def mark_processed(conn, item_id):
    with _db_lock:
        c = conn.cursor()
        c.execute(
            "INSERT INTO processed_items (item_id, processed_at) VALUES (?, ?)",
            (item_id, datetime.now()),
        )
        conn.commit()


def get_rag_api_token(force_refresh=False, current_token=None):
    global _token_cache
    with _token_lock:
        if _token_cache and not force_refresh:
            return _token_cache

        # Race condition protection: If another thread refreshed while we waited for lock
        if force_refresh and current_token and _token_cache and _token_cache != current_token:
            return _token_cache

        print(f"Authenticating with RAG API at {RAG_API_URL}...")
        try:
            response = session.post(
                f"{RAG_API_URL}/token",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                data={"username": RAG_API_USER, "password": RAG_API_PASSWORD},
            )
            response.raise_for_status()
            _token_cache = response.json().get("access_token")
            return _token_cache
        except requests.exceptions.RequestException as e:
            print(f"Error authenticating with RAG API: {e}")
            if force_refresh:
                return None
            sys.exit(1)


def generate_org_metadata(org):
    return {
        "org_id": org.get("id"),
        "name": org.get("name"),
        "source": "zendesk",
        "type": "organization",
    }


def generate_user_metadata(user):
    return {
        "user_id": user.get("id"),
        "name": user.get("name"),
        "email": user.get("email"),
        "role": user.get("role"),
        "source": "zendesk",
        "type": "user",
    }


def generate_metadata(ticket, is_attachment=False, attachment_name=None):
    subject = ticket.get("subject", "").lower() if ticket.get("subject") else ""
    description = (
        ticket.get("description", "").lower() if ticket.get("description") else ""
    )
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
        "source": "zendesk",
    }

    if attachment_name:
        metadata["attachment_name"] = attachment_name

    return metadata


def fetch_zendesk_organizations(org_ids):
    if not org_ids:
        return []

    print(f"Fetching {len(org_ids)} associated organizations from Zendesk...")

    # Zendesk show_many takes max 100 IDs at a time
    chunk_size = 100
    organizations = []

    for i in range(0, len(org_ids), chunk_size):
        chunk = org_ids[i : i + chunk_size]
        ids_str = ",".join(map(str, chunk))
        url = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/organizations/show_many.json?ids={ids_str}"

        headers = {
            "Authorization": f"Bearer {ZENDESK_TOKEN}",
            "Content-Type": "application/json",
        }

        try:
            response = session.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            organizations.extend(data.get("organizations", []))
        except requests.exceptions.RequestException as e:
            if (
                hasattr(e, "response")
                and e.response is not None
                and e.response.status_code == 429
            ):
                retry_after = int(e.response.headers.get("Retry-After", 60))
                print(f"Rate limited. Waiting for {retry_after} seconds...")
                time.sleep(retry_after)
                # We would normally retry here, but keeping it simple for now
            else:
                print(f"Failed to fetch organization chunk: {e}")

    return organizations


def fetch_zendesk_users(user_ids):
    if not user_ids:
        return []

    print(f"Fetching {len(user_ids)} associated users from Zendesk...")

    # Zendesk show_many takes max 100 IDs at a time
    chunk_size = 100
    users = []

    for i in range(0, len(user_ids), chunk_size):
        chunk = user_ids[i : i + chunk_size]
        ids_str = ",".join(map(str, chunk))
        url = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/users/show_many.json?ids={ids_str}"

        headers = {
            "Authorization": f"Bearer {ZENDESK_TOKEN}",
            "Content-Type": "application/json",
        }

        try:
            response = session.get(url, headers=headers)
            response.raise_for_status()
            data = response.json()
            users.extend(data.get("users", []))
        except requests.exceptions.RequestException as e:
            if (
                hasattr(e, "response")
                and e.response is not None
                and e.response.status_code == 429
            ):
                retry_after = int(e.response.headers.get("Retry-After", 60))
                print(f"Rate limited. Waiting for {retry_after} seconds...")
                time.sleep(retry_after)
            else:
                print(f"Failed to fetch user chunk: {e}")

    return users


def fetch_zendesk_tickets(limit=1000):
    print(f"Fetching up to {limit} tickets with attachments from Zendesk...")
    # Use Search API to filter specifically for tickets with attachments
    url = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/search.json?query=type:ticket has_attachment:true"
    headers = {
        "Authorization": f"Bearer {ZENDESK_TOKEN}",
        "Content-Type": "application/json",
    }

    tickets = []
    while url:
        try:
            response = session.get(url, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            if (
                hasattr(e, "response")
                and e.response is not None
                and e.response.status_code == 429
            ):
                retry_after = int(e.response.headers.get("Retry-After", 60))
                print(f"Rate limited. Waiting for {retry_after} seconds...")
                time.sleep(retry_after)
                continue
            else:
                print(f"Failed to fetch tickets: {e}")
                break

        data = response.json()
        # Search API returns results array instead of tickets array
        tickets.extend(data.get("results", []))

        if len(tickets) >= limit:
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

    max_retries = 5
    for attempt in range(max_retries):
        try:
            response = session.get(url, headers=headers)
            response.raise_for_status()
            return response.json().get("comments", [])
        except requests.exceptions.RequestException as e:
            if (
                hasattr(e, "response")
                and e.response is not None
                and e.response.status_code == 429
            ):
                retry_after = int(e.response.headers.get("Retry-After", 60))
                print(f"Rate limited getting comments for {ticket_id}. Waiting for {retry_after} seconds...")
                time.sleep(retry_after)
                continue
            print(f"Failed to fetch comments for ticket {ticket_id}: {e}")
            return []
            
    print(f"Max retries reached fetching comments for ticket {ticket_id}")
    return []


import re


def sanitize_filename(filename):
    """Remove invalid characters for Windows/Linux filesystems."""
    # Replace any character that isn't alphanumeric, dash, underscore, or period with an underscore
    return re.sub(r"[^\w\-\.]", "_", filename)


def download_attachment(url, filename):
    print(f"  Downloading attachment: {filename}...")
    safe_filename = sanitize_filename(filename)
    local_path = os.path.join(TEMP_DIR, safe_filename)
    try:
        response = session.get(url, stream=True)
        response.raise_for_status()
        with open(local_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return local_path
    except requests.exceptions.RequestException as e:
        print(f"Failed to download attachment {safe_filename}: {e}")
        return None


def ingest_to_rag_api(file_path, metadata):
    token = get_rag_api_token()
    try:
        with open(file_path, "rb") as f:
            headers = {
                "Authorization": f"Bearer {token}",
            }
            files = {
                "files": (os.path.basename(file_path), f, "application/octet-stream")
            }
            data = {"metadata": json.dumps(metadata)}

            response = session.post(
                f"{RAG_API_URL}/documents/ingest",
                headers=headers,
                files=files,
                data=data,
            )

            # If token expired, get a new one and retry once
            if response.status_code == 401:
                print(
                    "Token expired or invalid. Attempting to refresh token and retry..."
                )
                token = get_rag_api_token(force_refresh=True, current_token=token)
                if not token:
                    return False
                headers["Authorization"] = f"Bearer {token}"

                # Need to seek back to start of file for the retry
                f.seek(0)
                response = session.post(
                    f"{RAG_API_URL}/documents/ingest",
                    headers=headers,
                    files=files,
                    data=data,
                )

            response.raise_for_status()
            print(f"Successfully queued {os.path.basename(file_path)} for ingestion")
            return True
    except requests.exceptions.RequestException as e:
        print(f"Failed to ingest {os.path.basename(file_path)}: {e}")
        if hasattr(e, "response") and e.response is not None:
            print(f"Response: {e.response.text}")
        return False


def ingest_data(organizations, users, tickets):
    print(
        f"Processing and ingesting {len(organizations)} orgs, {len(users)} users, and {len(tickets)} tickets into RAG API..."
    )
    conn = setup_sqlite_db()

    max_workers = 10  # Process up to 10 items concurrently

    def process_org(org):
        org_id = org["id"]
        org_item_id = f"org_{org_id}"

        if not is_processed(conn, org_item_id):
            summary_md = f"# Organization: {org.get('name', 'Unknown')}\n\n"
            summary_md += f"**ID:** {org_id}\n"
            summary_md += f"**Created:** {org.get('created_at')}\n"
            if org.get("details"):
                summary_md += f"**Details:** {org.get('details')}\n"
            if org.get("notes"):
                summary_md += f"**Notes:** {org.get('notes')}\n"

            summary_filename = f"org_{org_id}_summary.md"
            summary_path = os.path.join(TEMP_DIR, summary_filename)
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(summary_md)

            metadata = generate_org_metadata(org)
            if ingest_to_rag_api(summary_path, metadata):
                mark_processed(conn, org_item_id)
                os.remove(summary_path)
        else:
            print(f"  Organization {org_id} already processed. Skipping.")

    def process_user(user):
        user_id = user["id"]
        user_item_id = f"user_{user_id}"

        if not is_processed(conn, user_item_id):
            summary_md = f"# User: {user.get('name', 'Unknown')}\n\n"
            summary_md += f"**ID:** {user_id}\n"
            summary_md += f"**Email:** {user.get('email', 'N/A')}\n"
            summary_md += f"**Role:** {user.get('role', 'N/A')}\n"
            if user.get("organization_id"):
                summary_md += f"**Organization ID:** {user.get('organization_id')}\n"
            summary_md += f"**Created:** {user.get('created_at')}\n"
            if user.get("details"):
                summary_md += f"**Details:** {user.get('details')}\n"
            if user.get("notes"):
                summary_md += f"**Notes:** {user.get('notes')}\n"

            summary_filename = f"user_{user_id}_summary.md"
            summary_path = os.path.join(TEMP_DIR, summary_filename)
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(summary_md)

            metadata = generate_user_metadata(user)
            if ingest_to_rag_api(summary_path, metadata):
                mark_processed(conn, user_item_id)
                os.remove(summary_path)
        else:
            print(f"  User {user_id} already processed. Skipping.")

    def process_ticket(ticket):
        ticket_id = ticket["id"]
        ticket_item_id = f"ticket_{ticket_id}"

        print(f"Processing ticket #{ticket_id}...")

        # 1. Fetch comments and build summary
        comments = fetch_ticket_comments(ticket_id)

        attachments = []
        for comment in comments:
            if comment.get("attachments"):
                attachments.extend(comment["attachments"])

        if not is_processed(conn, ticket_item_id):
            summary_md = (
                f"# Ticket #{ticket_id}: {ticket.get('subject', 'No Subject')}\n\n"
            )
            summary_md += f"**Status:** {ticket.get('status', 'unknown')}\n"
            summary_md += f"**Created:** {ticket.get('created_at')}\n\n"
            summary_md += f"## Description\n{ticket.get('description', '')}\n\n"
            summary_md += "## Comments\n"

            for comment in comments:
                summary_md += f"### Comment by {comment.get('author_id')} at {comment.get('created_at')}\n"
                summary_md += f"{comment.get('body', '')}\n\n"

            # Save summary to temp file
            summary_filename = f"ticket_{ticket_id}_summary.md"
            summary_path = os.path.join(TEMP_DIR, summary_filename)
            with open(summary_path, "w", encoding="utf-8") as f:
                f.write(summary_md)

            # Generate metadata and ingest summary
            metadata = generate_metadata(ticket, is_attachment=False)
            if ingest_to_rag_api(summary_path, metadata):
                mark_processed(conn, ticket_item_id)
                os.remove(summary_path)
        else:
            print(f"  Summary for Ticket #{ticket_id} already processed. Skipping.")

        # 2. Process attachments
        for att in attachments:
            att_id = att["id"]
            att_item_id = f"att_{att_id}"

            if not is_processed(conn, att_item_id):
                att_filename = f"ticket_{ticket_id}_{att['file_name']}"
                att_url = att["content_url"]

                print(f"  Downloading attachment: {att_filename}...")
                local_att_path = download_attachment(att_url, att_filename)

                if local_att_path:
                    att_metadata = generate_metadata(
                        ticket, is_attachment=True, attachment_name=att["file_name"]
                    )
                    if ingest_to_rag_api(local_att_path, att_metadata):
                        mark_processed(conn, att_item_id)
                        os.remove(local_att_path)
            else:
                print(
                    f"  Attachment {att['file_name']} (ID: {att_id}) already processed. Skipping."
                )

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        print("Processing Organizations...")
        org_futures = [executor.submit(process_org, org) for org in organizations]
        for future in as_completed(org_futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error processing organization: {e}")

        print("Processing Users...")
        user_futures = [executor.submit(process_user, user) for user in users]
        for future in as_completed(user_futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error processing user: {e}")

        print("Processing Tickets...")
        ticket_futures = [executor.submit(process_ticket, ticket) for ticket in tickets]
        for future in as_completed(ticket_futures):
            try:
                future.result()
            except Exception as e:
                print(f"Error processing ticket: {e}")

    conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Ingest Zendesk Data into MariaDB AI RAG via API"
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit the number of tickets to ingest (subset)",
        default=1000,
    )
    args = parser.parse_args()

    if not ZENDESK_SUBDOMAIN or not ZENDESK_TOKEN:
        print(
            "Error: ZENDESK_SUBDOMAIN and ZENDESK_OAUTH_TOKEN environment variables must be set in .env"
        )
        sys.exit(1)

    rag_token = get_rag_api_token()

    # 1. Fetch the target tickets first
    tickets = fetch_zendesk_tickets(limit=args.limit)

    if not tickets:
        print("No tickets found to ingest.")
        sys.exit(0)

    # 2. Extract unique org and user IDs
    org_ids = set()
    user_ids = set()

    for ticket in tickets:
        if ticket.get("organization_id"):
            org_ids.add(ticket["organization_id"])
        if ticket.get("requester_id"):
            user_ids.add(ticket["requester_id"])

    # 3. Fetch only associated organizations and users
    organizations = fetch_zendesk_organizations(list(org_ids))
    users = fetch_zendesk_users(list(user_ids))

    if organizations or users or tickets:
        ingest_data(organizations, users, tickets)
    else:
        print("No data found to ingest.")

    print("Ingestion complete.")
