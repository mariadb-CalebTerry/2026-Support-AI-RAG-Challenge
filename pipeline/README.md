# MariaDB Support RAG AI Challenge - Infrastructure & ELT Pipeline

This repository contains the infrastructure provisioning and data ingestion scripts required to set up the shared environment for the MariaDB Support RAG AI Challenge.

## 1. VM Provisioning (`provision_vm.ps1`)

This script uses the Google Cloud CLI (`gcloud`) to provision the central Virtual Machine (`elt-mcp-host`) that will host the database, AI RAG components, and ELT pipelines. It also configures Identity-Aware Proxy (IAP) firewall rules to allow secure SSH access for the challenge participants.

**Usage:**

```powershell
.\provision_vm.ps1
```

## 2. Upload Files to VM (`upload_to_vm.ps1`)

This script securely uploads the entire `pipeline` directory to the newly provisioned VM at `/tmp/ai_rag_challenge_scripts/pipeline` using an IAP tunnel.

**Usage:**

```powershell
.\upload_to_vm.ps1
```

## 3. Database & AI RAG Installation (`install_mariadb_native.sh`)

This script automates the native installation of MariaDB Enterprise Server (which provides `VECTOR` and `HNSW` support) and the MariaDB AI RAG components without using Docker.

**Prerequisites:**
Before running the script, you must manually download the MariaDB AI RAG `.deb` installation package from the [MariaDB Enterprise Tooling downloads page](https://mariadb.com/downloads/enterprise-tooling/ai-rag/) and transfer it to the provisioned VM (e.g., placing it in `/tmp/ai_rag_challenge_scripts/pipeline/`). The script will prompt you for the path to this file.

**Usage:**

1. Connect to the provisioned VM using the connection wrapper script (this handles IAP tunnels reliably on Windows):
   ```powershell
   .\connect_vm.ps1
   ```
2. Navigate to the uploaded directory: `cd /tmp/ai_rag_challenge_scripts/pipeline`
3. Run the script:

```bash
bash install_mariadb_native.sh
```

## 4. Zendesk Data Ingestion (`ingest_zendesk.py`)

This Python script connects to the Zendesk API to fetch tickets and their corresponding comments, inserting them into the relational MariaDB tables.

It supports a `--limit` parameter allowing you to restrict the ingestion to a subset of data (e.g., for testing or limiting the dataset size).

**Setup:**

1. Create a `.env` file in this directory:

```env
ZENDESK_SUBDOMAIN=your_subdomain
ZENDESK_OAUTH_TOKEN=your_read_only_oauth_token
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=rag_user
DB_PASSWORD=ragpassword
DB_NAME=zendesk_rag
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Run the ingestion (example with a limit of 100 tickets):

```bash
python ingest_zendesk.py --limit 100
```
