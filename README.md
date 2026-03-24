# 2026 Support AI RAG Challenge

This project sets up a shared GCP VM environment hosting MariaDB Enterprise Server with native VECTOR and HNSW support, alongside AI RAG components. It includes an ELT pipeline to ingest Zendesk ticket data into the MariaDB vector database.

## Architecture

- **GCP VM**: `vm-ai-rag-challenge` in `us-east1-b` (n2-standard-4, Debian 12)
- **Storage**: 
  - 64GB pd-ssd data disk mounted at `/data`
  - 32GB pd-standard log disk mounted at `/logs`
- **Database**: MariaDB Enterprise Server 11.4 with AI RAG package
- **Access**: IAP (Identity-Aware Proxy) SSH only via TCP port 22

## Pipeline Scripts

### Provisioning
- `provision_vm.ps1`: Idempotent script to create the GCP VM, attached disks, and IAP firewall rules
- `upload_to_vm.ps1`: Securely copies the pipeline scripts to the VM
- `connect_vm.ps1`: Wrapper to securely SSH into the VM

### Installation
- `install_mariadb_native.sh`: Installs MariaDB natively, mounts disks, configures optimized settings, and sets up RAG database
- `server.cnf`: Optimized MariaDB configuration for AI RAG workloads

### Data Ingestion
- `ingest_zendesk.py`: Idempotent Python script to fetch, chunk, embed, and insert Zendesk tickets into MariaDB

## Usage

1. Provision the VM:
   ```powershell
   .\pipeline\provision_vm.ps1
   ```

2. Upload scripts to VM:
   ```powershell
   .\pipeline\upload_to_vm.ps1
   ```

3. Connect to VM:
   ```powershell
   .\pipeline\connect_vm.ps1
   ```

4. Install MariaDB and AI RAG:
   ```bash
   cd /tmp/ai_rag_challenge_scripts/pipeline
   bash install_mariadb_native.sh
   ```

5. Ingest Zendesk data:
   ```bash
   python ingest_zendesk.py
   ```

## MariaDB Configuration

The `server.cnf` file includes optimizations for:
- **InnoDB Performance**: 2GB buffer pool, O_DIRECT flush method, optimized I/O threads
- **AI RAG**: HNSW vector index settings (cache size, distance functions, search parameters)
- **Dedicated Storage**: Custom data and log directories on separate disks
- **Security**: Disabled local infile, secure character sets

## Key Features

- Idempotent operations (safe to run multiple times)
- Dedicated data and log disks for optimal performance
- Vector search with HNSW algorithm for semantic similarity
- Automated Zendesk ticket ingestion with chunking and embedding
- Windows-compatible PowerShell scripts with GCP IAP tunnel workarounds
