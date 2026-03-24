import os
import requests
import mariadb
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

ZENDESK_SUBDOMAIN = os.getenv("ZENDESK_SUBDOMAIN")
ZENDESK_TOKEN = os.getenv("ZENDESK_OAUTH_TOKEN")
DB_USER = os.getenv("DB_USER", "rag_user")
DB_PASSWORD = os.getenv("DB_PASSWORD", "ragpassword")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = int(os.getenv("DB_PORT", 3306))
DB_NAME = os.getenv("DB_NAME", "zendesk_rag")


def get_db_connection():
    try:
        conn = mariadb.connect(
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
        )
        return conn
    except mariadb.Error as e:
        print(f"Error connecting to MariaDB: {e}")
        sys.exit(1)


def setup_database(cursor):
    """Create necessary tables if they don't exist."""
    print("Setting up database tables...")
    cursor.execute("CREATE DATABASE IF NOT EXISTS `zendesk_rag`")
    cursor.execute("USE `zendesk_rag`")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS tickets (
            id BIGINT PRIMARY KEY,
            subject VARCHAR(255),
            description TEXT,
            status VARCHAR(50),
            created_at DATETIME,
            updated_at DATETIME,
            requester_id BIGINT,
            assignee_id BIGINT,
            tags TEXT
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ticket_comments (
            id BIGINT PRIMARY KEY,
            ticket_id BIGINT,
            body TEXT,
            author_id BIGINT,
            created_at DATETIME,
            FOREIGN KEY (ticket_id) REFERENCES tickets(id) ON DELETE CASCADE
        )
    """
    )


def fetch_zendesk_tickets(limit=None):
    """Fetch tickets from Zendesk API. If limit is provided, restricts the subset."""
    print(f"Fetching tickets from Zendesk (Limit: {limit if limit else 'None'})...")
    url = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/tickets.json"
    headers = {
        "Authorization": f"Bearer {ZENDESK_TOKEN}",
        "Content-Type": "application/json",
    }

    tickets = []
    while url:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"Failed to fetch tickets: {response.status_code} - {response.text}")
            break

        data = response.json()
        tickets.extend(data.get("tickets", []))

        if limit and len(tickets) >= limit:
            tickets = tickets[:limit]
            break

        url = data.get("next_page")

    return tickets


def fetch_ticket_comments(ticket_id):
    """Fetch comments for a specific ticket."""
    url = f"https://{ZENDESK_SUBDOMAIN}.zendesk.com/api/v2/tickets/{ticket_id}/comments.json"
    headers = {
        "Authorization": f"Bearer {ZENDESK_TOKEN}",
        "Content-Type": "application/json",
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json().get("comments", [])
    return []


def ingest_data(conn, tickets):
    """Insert tickets and comments into MariaDB."""
    cursor = conn.cursor()

    print(f"Ingesting {len(tickets)} tickets into MariaDB...")

    for ticket in tickets:
        # Convert tags list to comma-separated string
        tags = ",".join(ticket.get("tags", []))

        # Insert Ticket
        try:
            cursor.execute(
                """
                INSERT INTO tickets (id, subject, description, status, created_at, updated_at, requester_id, assignee_id, tags)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON DUPLICATE KEY UPDATE 
                subject=VALUES(subject), description=VALUES(description), status=VALUES(status), 
                updated_at=VALUES(updated_at), tags=VALUES(tags)
            """,
                (
                    ticket["id"],
                    ticket.get("subject", ""),
                    ticket.get("description", ""),
                    ticket.get("status", ""),
                    ticket.get("created_at", "").replace("T", " ").replace("Z", ""),
                    ticket.get("updated_at", "").replace("T", " ").replace("Z", ""),
                    ticket.get("requester_id"),
                    ticket.get("assignee_id"),
                    tags,
                ),
            )

            # Fetch and Insert Comments
            comments = fetch_ticket_comments(ticket["id"])
            for comment in comments:
                cursor.execute(
                    """
                    INSERT INTO ticket_comments (id, ticket_id, body, author_id, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON DUPLICATE KEY UPDATE body=VALUES(body)
                """,
                    (
                        comment["id"],
                        ticket["id"],
                        comment.get("body", ""),
                        comment.get("author_id"),
                        comment.get("created_at", "")
                        .replace("T", " ")
                        .replace("Z", ""),
                    ),
                )

            conn.commit()
            print(f"Successfully ingested ticket #{ticket['id']}")

        except mariadb.Error as e:
            print(f"Error inserting ticket {ticket['id']}: {e}")
            conn.rollback()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Ingest Zendesk Data into MariaDB")
    parser.add_argument(
        "--limit",
        type=int,
        help="Limit the number of tickets to ingest (subset)",
        default=None,
    )
    args = parser.parse_args()

    if not ZENDESK_SUBDOMAIN or not ZENDESK_TOKEN:
        print(
            "Error: ZENDESK_SUBDOMAIN and ZENDESK_OAUTH_TOKEN environment variables must be set in .env"
        )
        sys.exit(1)

    conn = get_db_connection()
    cursor = conn.cursor()

    setup_database(cursor)

    tickets = fetch_zendesk_tickets(limit=args.limit)
    if tickets:
        ingest_data(conn, tickets)
    else:
        print("No tickets found to ingest.")

    conn.close()
    print("Ingestion complete.")
