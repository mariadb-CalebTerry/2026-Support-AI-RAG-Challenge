# MariaDB Support AI RAG Challenge

This repository contains the full ELT pipeline, Docker deployment scripts, and operational guides to provision a shared GCP VM hosting **MariaDB AI RAG 1.1 (Beta)**. It is specifically designed to ingest and query real Zendesk support data (Tickets, Organizations, Users, and Attachments) to assist MariaDB's Support & Services organization.

## 🚀 Quick Start for Support & Services

If you are a member of the MariaDB Support & Services team looking to connect your IDE to this environment to query historical support tickets, please read the onboarding guide:

👉 **[Support & Services Onboarding Guide](docs/SUPPORT_SERVICES_ONBOARDING.md)**

---

## Architecture Overview

- **GCP VM**: `vm-ai-rag-challenge` in `us-east1-b` (n2-standard-4, Ubuntu 22.04)
- **Storage**:
  - 64GB pd-ssd data disk mounted at `/data` (for MariaDB vector storage, Redis, and Docling Ray)
  - 32GB pd-standard log disk mounted at `/logs`
- **Database**: MariaDB 11.8 with native vector support
- **AI Models**:
  - Embedding: `text-embedding-004`
  - Generation: `gemini-2.5-flash`
- **Access**: Secure IAP (Identity-Aware Proxy) SSH tunnels only (no public IPs)

## Feature Highlights

- **Targeted Data Ingestion**: The `ingest_zendesk.py` ELT script smartly searches Zendesk for 1000 high-value tickets containing attachments. It then specifically extracts and ingests only the Organizations and Users associated with those tickets, preventing vector database bloat and strictly maintaining context relevance.
- **Advanced Attachment Parsing**: Support tickets often contain complex diagnostic files (`my.cnf`, error logs, zip files). The backend Docling-Ray service intelligently parses these files, chunks them semantically, and embeds them into MariaDB.
- **Idempotency**: The ingestion pipeline utilizes a local SQLite database (`ingestion_state.db`) to track processed entities, allowing it to gracefully resume in the event of API rate limits or token expirations.
- **MCP Native**: The environment exposes an MCP Server (port 8002) allowing modern AI IDEs to directly query the RAG pipeline.

## Repository Layout

```
.
├── docs/
│   └── SUPPORT_SERVICES_ONBOARDING.md  # Guide for connecting IDEs to the RAG MCP
├── src/
│   ├── config.env                      # Configuration overrides (API keys, models)
│   ├── configure_disks.sh              # Formats GCP disks for Docker
│   ├── connect_vm.ps1                  # IAP SSH wrapper
│   ├── docker-compose.yml              # MariaDB AI RAG 1.1 deployment stack
│   ├── ingest_zendesk.py               # The main ELT data ingestion script
│   ├── provision_vm.ps1                # Idempotent GCP VM creation script
│   ├── rag_platform_client.py          # Demo script for multi-tenant RAG querying
│   ├── setup_docker_ai_rag.sh          # VM bootstrapping script
│   ├── start_tunnels.ps1               # Forward remote ports 8000 and 8002 locally
│   └── upload_to_vm.ps1                # Syncs local pipeline scripts to the VM
└── README.md
```

## Administrative Operations

### Deploying the Stack from Scratch

If you need to stand up this environment from scratch:

1. Create a `src/config.env` file using the necessary MariaDB tokens and Gemini API keys.
2. Run `.\src\provision_vm.ps1` to create the GCP infrastructure.
3. Run `.\src\upload_to_vm.ps1` to copy the setup scripts over.
4. SSH into the box using `.\src\connect_vm.ps1`.
5. Run `bash /tmp/ai_rag_challenge_scripts/src/setup_docker_ai_rag.sh` to install Docker and start the AI RAG stack.

### Running the Data Ingestion

The Zendesk pipeline requires `ZENDESK_SUBDOMAIN` and `ZENDESK_OAUTH_TOKEN` in `config.env`.

Ensure the local IAP tunnels are running (`start_tunnels.ps1`), then execute:

```bash
cd pipeline
pip install python-dotenv requests requests-toolbelt
python ingest_zendesk.py --limit 1000
```

This script runs locally and streams the data directly through the tunnel to the remote Docling-Ray ingest API.
