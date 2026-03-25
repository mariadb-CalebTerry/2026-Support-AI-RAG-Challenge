# MariaDB Support RAG AI Challenge - Docker Deployment Infrastructure

This repository contains the infrastructure provisioning and Docker deployment scripts required to set up the shared environment for the MariaDB Support RAG AI Challenge using MariaDB AI RAG 1.1 (Beta).

## 1. VM Provisioning (`provision_vm.ps1`)

This script uses the Google Cloud CLI (`gcloud`) to provision the central Virtual Machine (`vm-ai-rag-challenge`) that will host the Docker-based AI RAG stack. It deletes any existing VM and creates a new Ubuntu 22.04 LTS instance with Docker prerequisites.

**Usage:**

```powershell
.\provision_vm.ps1
```

## 2. Upload Files to VM (`upload_to_vm.ps1`)

This script securely uploads the pipeline scripts and credential files to the newly provisioned VM using an IAP tunnel.

**Usage:**

```powershell
.\upload_to_vm.ps1
```

## 3. Docker AI RAG Deployment (`setup_docker_ai_rag.sh`)

This script automates the complete Docker deployment of MariaDB AI RAG 1.1 (Beta) on Ubuntu. It installs Docker, downloads configurations, and starts the complete stack.

**What it does:**

- Installs Docker Engine and Docker Compose
- Downloads official Docker Compose configuration
- Creates required directories (uploaded_files, logs)
- Generates secure configuration with provided credentials
- Deploys the complete AI RAG stack
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

## 4. Zendesk Data Ingestion (`ingest_zendesk.py`)

This Python script connects to the Zendesk API to fetch tickets and their corresponding comments, inserting them into the Docker-deployed MariaDB database.

It supports a `--limit` parameter allowing you to restrict the ingestion to a subset of data (e.g., for testing or limiting the dataset size).

**Setup:**

1. Create a `.env` file in this directory:

```env
ZENDESK_SUBDOMAIN=your_subdomain
ZENDESK_OAUTH_TOKEN=your_read_only_oauth_token
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=mariadb_rag_password_2024
DB_NAME=kb_chunks
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the ingestion (example with a limit of 100 tickets):

```bash
python ingest_zendesk.py --limit 100
```

## Docker Stack Architecture

The deployment creates the following containers:

- **ai-nexus**: Main AI RAG application (FastAPI + Uvicorn)
- **mysql-db**: MariaDB 11 database with vector support
- **rag-redis**: Redis for background task queue
- **rag-celery-worker**: Background document processing
- **rag-docling-ray**: Advanced document extraction

## Access Points

After successful deployment:

- **RAG API Swagger UI**: http://\<vm-ip>:8000/docs
- **RAG API Health**: http://\<vm-ip>:8000/health
- **MCP Server**: http://\<vm-ip>:8002/mcp
- **MCP Health**: http://\<vm-ip>:8002/health

## Service Management

```bash
# Check service status
docker compose -f docker-compose.dockerhub-dev.yml ps

# View logs
docker compose -f docker-compose.dockerhub-dev.yml logs

# Stop services
docker compose -f docker-compose.dockerhub-dev.yml down

# Restart services
docker compose -f docker-compose.dockerhub-dev.yml restart
```

## Troubleshooting

Common issues and solutions are covered in the main project documentation. The Docker setup includes comprehensive health checks and error reporting.
