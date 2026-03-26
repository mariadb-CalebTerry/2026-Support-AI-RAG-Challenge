# 2026 Support AI RAG Challenge

This project sets up a shared GCP VM environment hosting MariaDB AI RAG 1.1 (Beta) deployed with Docker Compose. It includes a complete RAG stack with MariaDB 11.8, Redis, and AI services for document ingestion and semantic search.

## Architecture

- **GCP VM**: `vm-ai-rag-challenge` in `us-east1-b` (n2-standard-4, Debian 12)
- **Storage**:
  - 64GB pd-ssd data disk mounted at `/data` (for MariaDB data, Redis data, and uploaded files)
  - 32GB pd-standard log disk mounted at `/logs` (for application logs)
- **Database**: MariaDB AI RAG 1.1 (Beta) with Docker Compose
- **Access**: IAP (Identity-Aware Proxy) SSH only via TCP port 22

## Current Status

✅ **Completed:**

- GCP VM provisioned with Debian 12
- Docker Engine installed
- All scripts and credentials uploaded to VM
- MariaDB Enterprise token available for authentication
- Dedicated disks (64GB data, 32GB logs) attached and ready
- Automated AI RAG container deployment script ready

## Manual Configuration Instructions

### 1. Connect to the VM

```powershell
.\pipeline\connect_vm.ps1
```

### 2. Run the Automated Setup Script

The `setup_docker_ai_rag.sh` script automates the process of configuring dedicated disks, installing Docker, and deploying the AI RAG stack:

```bash
cd /tmp/ai_rag_challenge_scripts/pipeline
bash setup_docker_ai_rag.sh
```

### 3. Verify Deployment

```bash
# Check container status
sudo docker compose -f /data/mariadb-rag-deployment/docker-compose.yml ps

# Check logs for any issues
sudo docker compose -f /data/mariadb-rag-deployment/docker-compose.yml logs
```

### 4. Test Health Endpoints

```bash
# Test RAG API health
curl http://localhost:8000/health

# Test MCP Server health
curl http://localhost:8002/health

# Test database connection
sudo docker exec rag-mariadb mariadb -u root -pmariadb_rag_password_2024 -e "SHOW DATABASES;"
```

### 5. Access Services

Get the external IP for external access:

```bash
curl -s ifconfig.me
```

Then access:

- **RAG API Swagger UI**: http://\<external-ip>:8000/docs
- **RAG API Health**: http://\<external-ip>:8000/health
- **MCP Server**: http://\<external-ip>:8002/mcp
- **MCP Health**: http://\<external-ip>:8002/health

## Troubleshooting

### Docker Login Issues

If you get authentication errors:

1. Verify the token is correct: `cat /tmp/ai_rag_challenge_scripts/mariadb_token.txt`
2. Try logging out and back in: `sudo docker logout && sudo docker login docker.mariadb.com -u token -p <token>`
3. Check if you need a different registry URL

### Disk Space Issues

If you encounter "no space left on device" errors:

1. **First, ensure disks are mounted:**

   ```bash
   df -h
   # You should see /data and /logs mounted
   ```

2. **If disks aren't mounted, run:**

   ```bash
   cd /tmp/ai_rag_challenge_scripts/pipeline
   bash configure_disks.sh
   ```

3. **Check Docker is using mounted disks:**
   ```bash
   # Docker data should be using /data partition
   docker system df
   ```

### Image Pull Issues

If images fail to pull:

1. Check available images: `sudo docker search mariadb-ai`
2. Try pulling individual images first: `sudo docker pull docker.mariadb.com/mariadb/mariadb-ai-dev:rag-api-runtime`
3. Use the basic stack if some images aren't accessible

### Service Startup Issues

If services don't start properly:

1. Check logs: `sudo docker compose logs <service-name>`
2. Verify configuration: `cat config.env`
3. Check license key is properly formatted
4. Ensure ports aren't already in use

### Configuration Issues

If the configuration file has issues:

1. Verify all credentials are loaded correctly
2. Check that the MariaDB license key is on a single line
3. Ensure all three security keys are identical
4. Verify Gemini API key format

## Available Credentials

The following credentials are available on the VM at `/tmp/ai_rag_challenge_scripts/`:

- **MariaDB Enterprise Token**: `mariadb_token.txt`
- **Gemini API Key**: `gemini_key.txt`
- **MariaDB License Key**: `rag_license.txt`
- **Docker PAT**: `docker_pat.txt`

## Pipeline Scripts

### Provisioning

- `provision_vm.ps1`: Creates Ubuntu VM with Docker, deletes existing VM, and configures IAP firewall rules
- `upload_to_vm.ps1`: Securely copies pipeline scripts and credentials to the VM
- `connect_vm.ps1`: Wrapper to securely SSH into the VM

### Docker Deployment

- `configure_disks.sh`: Formats and mounts dedicated disks for data and logs
- `setup_docker_ai_rag.sh`: Automated Docker setup script (configures disks, installs Docker, deploys RAG stack)
- `docker-compose.yml`: Updated Docker Compose configuration using mounted disks
- `config.env`: Environment configuration with credentials

### API-First Data Ingestion

- `ingest_zendesk.py`: Python script to fetch Zendesk tickets, generate rich metadata tags, download attachments, and stream them natively to the MariaDB AI RAG API (`/documents/ingest`). It uses a local SQLite database (`ingestion_state.db`) to guarantee idempotency.

### Enterprise Shared Platform Client

- `rag_platform_client.py`: Python script demonstrating a multi-tenant AI RAG workflow. It queries the unified MariaDB Vector store via the RAG API and dynamically injects metadata filters to serve four distinct personas.

## Disk Layout

The dedicated disks are organized as follows:

### /data (64GB pd-ssd)

- `/data/mariadb/` - MariaDB database files
- `/data/redis/` - Redis data files
- `/data/uploaded_files/` - Document uploads and attachments
- `/data/mariadb-rag-deployment/` - Docker deployment directory

### /logs (32GB pd-standard)

- `/logs/mariadb/` - MariaDB error/general logs
- `/logs/rag/` - Application logs (rag-api, celery-worker, mcp-server)

## Service Management

```bash
# Check service status
sudo docker compose ps

# View logs
sudo docker compose logs

# Stop services
sudo docker compose down

# Restart services
sudo docker compose restart

# Update configuration
# Edit config.env then:
sudo docker compose down && sudo docker compose up -d
```

## Next Steps After Deployment

### 1. Ingest Zendesk Data

First, populate the environment by running the ingestion script. This will pull tickets, format them, handle attachments, and push everything into the unified vector store.

```bash
cd /tmp/ai_rag_challenge_scripts/pipeline
python ingest_zendesk.py --limit 100
```

### 2. Run Persona-Based Queries

Once data is ingested, you can test the multi-tenant architecture using the provided client script. This script connects to the RAG API and filters results based on the chosen role.

```bash
cd /tmp/ai_rag_challenge_scripts/pipeline

# 1. Support Persona (Quick resolutions, error codes)
python rag_platform_client.py --persona support --query "How do I fix a connection timeout error?"

# 2. DPA Persona (Performance, optimization)
python rag_platform_client.py --persona dpa --query "Recommendations for memory optimization"

# 3. PS Persona (Customer scenarios, best practices)
python rag_platform_client.py --persona ps --query "Best practices for setting up Galera cluster"

# 4. SRE Persona (Outages, replication monitoring)
python rag_platform_client.py --persona sre --query "Troubleshooting replication lag and GTID errors"
```

## Key Features

- Docker-based deployment for consistency and scalability
- MariaDB AI RAG 1.1 (Beta) with native vector search
- Single unified vector store managed dynamically by the REST API
- `rag-docling-ray` integration for advanced OCR layout extraction of ticket attachments
- Idempotent API-first ingestion pipeline tracking state via local SQLite
- Role-based multi-tenant search filtering using rich JSON metadata tags
