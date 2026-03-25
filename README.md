# 2026 Support AI RAG Challenge

This project sets up a shared GCP VM environment hosting MariaDB AI RAG 1.1 (Beta) deployed with Docker Compose. It includes a complete RAG stack with MariaDB 11, Redis, and AI services for document ingestion and semantic search.

## Architecture

- **GCP VM**: `vm-ai-rag-challenge` in `us-east1-b` (n2-standard-4, Ubuntu 22.04 LTS)
- **Storage**:
  - 64GB pd-ssd data disk mounted at `/data`
  - 32GB pd-standard log disk mounted at `/logs`
- **Database**: MariaDB AI RAG 1.1 (Beta) with Docker Compose
- **Access**: IAP (Identity-Aware Proxy) SSH only via TCP port 22

## Current Status

✅ **Completed:**

- GCP VM provisioned with Ubuntu 22.04 LTS
- Docker Engine installed
- All scripts and credentials uploaded to VM
- MariaDB Enterprise token available for authentication

⚠️ **Manual Steps Required:**

- Docker login to MariaDB registry
- Complete AI RAG container deployment
- Service verification and testing

## Manual Configuration Instructions

### 1. Connect to the VM

```powershell
.\pipeline\connect_vm.ps1
```

### 2. Navigate to Deployment Directory

```bash
cd /home/caleb_terry/mariadb-rag-deployment
```

### 3. Login to MariaDB Docker Registry

Use the MariaDB Enterprise token to authenticate:

```bash
sudo docker login docker.mariadb.com -u token -p 87e2f31b-c33e-4b10-82e6-3a6b64600319
```

### 4. Verify Configuration Files

Check that the configuration files exist and have correct permissions:

```bash
# List files
ls -la

# Verify config file
cat config.env.secure

# Check permissions (should be 600)
ls -l config.env.secure
```

### 5. Deploy the AI RAG Stack

#### Option A: Full Stack (if all images are accessible)

```bash
sudo docker compose -f docker-compose.dockerhub-dev.yml --env-file config.env.secure up -d
```

#### Option B: Basic Stack (if some images aren't accessible)

```bash
# Start with basic services first
sudo docker compose -f docker-compose.basic.yml up -d

# Then try adding AI RAG services
sudo docker compose -f docker-compose.fixed.yml --env-file config.env.secure up -d
```

### 6. Verify Deployment

```bash
# Check container status
sudo docker compose ps

# Check logs for any issues
sudo docker compose logs

# Verify specific services
sudo docker compose logs rag-api
sudo docker compose logs mysql-db
```

### 7. Test Health Endpoints

```bash
# Test RAG API health
curl http://localhost:8000/health

# Test MCP Server health
curl http://localhost:8002/health

# Test database connection
sudo docker exec rag-mariadb mysql -u root -pmariadb_rag_password_2024 -e "SHOW DATABASES;"
```

### 8. Access Services

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

### Image Pull Issues

If images fail to pull:

1. Check available images: `sudo docker search mariadb-ai`
2. Try pulling individual images first: `sudo docker pull docker.mariadb.com/mariadb/mariadb-ai-dev:rag-api-runtime`
3. Use the basic stack if some images aren't accessible

### Service Startup Issues

If services don't start properly:

1. Check logs: `sudo docker compose logs <service-name>`
2. Verify configuration: `cat config.env.secure`
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

## Pipeline Scripts

### Provisioning

- `provision_vm.ps1`: Creates Ubuntu VM with Docker, deletes existing VM, and configures IAP firewall rules
- `upload_to_vm.ps1`: Securely copies pipeline scripts and credentials to the VM
- `connect_vm.ps1`: Wrapper to securely SSH into the VM

### Docker Deployment

- `setup_docker_ai_rag.sh`: Automated Docker setup script (requires manual completion)
- `docker-compose.dockerhub-dev.yml`: Official Docker Compose configuration
- `config.env.secure`: Environment configuration with credentials

### API-First Data Ingestion

- `ingest_zendesk.py`: Python script to fetch Zendesk tickets, generate rich metadata tags, download attachments, and stream them natively to the MariaDB AI RAG API (`/documents/ingest`). It uses a local SQLite database (`ingestion_state.db`) to guarantee idempotency.

### Enterprise Shared Platform Client

- `rag_platform_client.py`: Python script demonstrating a multi-tenant AI RAG workflow. It queries the unified MariaDB Vector store via the RAG API and dynamically injects metadata filters to serve four distinct personas.

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
# Edit config.env.secure then:
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
