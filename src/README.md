# MariaDB Support RAG AI Challenge - Docker Deployment Infrastructure

This repository contains the infrastructure provisioning and Docker deployment scripts required to set up the shared environment for the MariaDB Support RAG AI Challenge using MariaDB AI RAG 1.1 (Beta).

## 1. VM Provisioning (`provision_vm.ps1`)

This script uses the Google Cloud CLI (`gcloud`) to provision the central Virtual Machine (`vm-ai-rag-challenge`) that will host the Docker-based AI RAG stack. It deletes any existing VM and creates a new Debian 12 instance with Docker prerequisites and dedicated data disks.

**Usage:**

```powershell
.\provision_vm.ps1
```

## 2. Configure Disks (`configure_disks.sh`)

This script formats and mounts the dedicated disks that were attached during VM provisioning. This is critical for providing sufficient space for Docker images and data.

**What it does:**

- Formats and mounts 64GB data disk at `/data`
- Formats and mounts 32GB log disk at `/logs`
- Creates required directories for MariaDB, Redis, and application data
- Sets proper permissions for all directories

**Usage:**

```bash
cd /tmp/ai_rag_challenge_scripts/pipeline
bash configure_disks.sh
```

## 3. Upload Files to VM (`upload_to_vm.ps1`)

This script securely uploads the pipeline scripts and credential files to the newly provisioned VM using an IAP tunnel.

**Usage:**

```powershell
.\upload_to_vm.ps1
```

## 4. Docker AI RAG Deployment (`setup_docker_ai_rag.sh`)

This script automates the complete Docker deployment of MariaDB AI RAG 1.1 (Beta) on Ubuntu. It installs Docker, downloads configurations, and starts the complete stack.

**What it does:**

- Installs Docker Engine and Docker Compose
- Downloads official Docker Compose configuration
- Creates required directories on mounted disks
- Generates secure configuration with provided credentials
- Deploys the complete AI RAG stack using dedicated disks
- Performs health checks and verification

**Usage:**

1. Connect to the provisioned VM using the connection wrapper script:
   ```powershell
   .\connect_vm.ps1
   ```
2. Navigate to the uploaded directory: `cd /tmp/ai_rag_challenge_scripts/pipeline`
3. Run the Docker setup script:

```bash
bash setup_docker_ai_rag.sh
```

## 5. Zendesk Data Ingestion (`ingest_zendesk.py`)

This Python script connects to the Zendesk API to fetch tickets and their corresponding comments, and ingests them into the Docker-deployed MariaDB AI RAG platform.

**Key Features (API-First RAG Integration):**

- **Rich Metadata Generation:** Automatically tags tickets with categories like `technical_area`, `ticket_type`, and `complexity` based on content analysis.
- **Attachment Handling:** Downloads Zendesk attachments and pushes them to the MariaDB AI RAG API.
- **Docling-Ray Integration:** Relies on the `rag-docling-ray` specialist container to natively parse complex PDFs, logs, and tables from the uploaded attachments.
- **Unified Vector Store:** All data is ingested via the REST API (`/documents/ingest`) and stored in a single, dynamically managed vector table.

**Setup:**

1. Create a `.env` file in this directory based on `config.env.template`:

```env
ZENDESK_SUBDOMAIN=your_subdomain
ZENDESK_OAUTH_TOKEN=your_read_only_oauth_token
RAG_API_URL=http://localhost:8000
RAG_API_USER=admin
RAG_API_PASSWORD=mariadb_rag_password_2024
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the ingestion (example with a limit of 100 tickets):

```bash
python ingest_zendesk.py --limit 100
```

## 6. Enterprise Shared Platform Client (`rag_platform_client.py`)

This client demonstrates the multi-tenant architecture of our shared AI RAG platform. By leveraging the unified vector store and rich metadata ingested in step 4, this client allows different personas to query the exact same dataset using dynamic metadata filters tailored to their role.

**Available Personas:**

- `support`: Focuses on quick error code lookups and solved basic issues.
- `dpa`: Database Performance Analyst, focusing on performance optimization techniques and benchmarks.
- `ps`: Professional Services Consultant, focusing on customer scenarios, how-to guides, and best practices.
- `sre`: Site Reliability Engineer, focusing on advanced outage recovery, replication, and monitoring.

**Usage Examples:**

```bash
# Example for a Support Engineer
python rag_platform_client.py --persona support --query "How do I fix a connection timeout error?"

# Example for a Database Performance Analyst (DPA)
python rag_platform_client.py --persona dpa --query "Recommendations for memory optimization"

# Example for a Professional Services Consultant (PS)
python rag_platform_client.py --persona ps --query "Best practices for setting up Galera cluster"

# Example for a Site Reliability Engineer (SRE)
python rag_platform_client.py --persona sre --query "Troubleshooting replication lag and GTID errors"
```

## Docker Stack Architecture

The deployment creates the following containers with data stored on dedicated disks:

- **rag-api**: Main AI RAG application (FastAPI + Uvicorn) providing the REST endpoints for ingestion and orchestration. Logs stored in `/logs/rag/`.
- **rag-mariadb**: MariaDB 11.8 database with native vector support. Data stored in `/data/mariadb/`.
- **rag-redis**: Redis for the background task queue. Data stored in `/data/redis/`.
- **rag-celery-worker**: Background document processing, chunking, and embedding. Logs stored in `/logs/rag/`.
- **rag-docling-ray**: Advanced document extraction (critical for parsing uploaded Zendesk attachments). Processes files from `/data/uploaded_files/`.
- **rag-mcp-server**: MariaDB Enterprise MCP Server acting as the interface between AI assistants and the data ecosystem. Logs stored in `/logs/rag/`.

## Access Points

After successful deployment:

- **RAG API Swagger UI**: http://\<vm-ip>:8000/docs
- **RAG API Health**: http://\<vm-ip>:8000/health
- **MCP Server**: http://\<vm-ip>:8002/mcp
- **MCP Health**: http://\<vm-ip>:8002/health

## Service Management

```bash
# Check service status
docker compose -f docker-compose.yml ps

# View logs
docker compose -f docker-compose.yml logs

# Stop services
docker compose -f docker-compose.yml down

# Restart services
docker compose -f docker-compose.yml restart
```

## Troubleshooting

Common issues and solutions are covered in the main project documentation. The Docker setup includes comprehensive health checks and error reporting.
