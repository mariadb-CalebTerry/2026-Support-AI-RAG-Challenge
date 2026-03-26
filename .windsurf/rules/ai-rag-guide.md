---
trigger: always_on
---

# 2026 Support AI RAG Challenge

This project sets up a shared GCP VM environment hosting MariaDB AI RAG 1.1 (Beta) with Docker Compose, alongside AI RAG components. It includes an ELT pipeline to ingest Zendesk ticket data into the MariaDB vector database.

## Critical Rules

1. Always use the MariaDB version of tools instead of MySQL, when possible. Example: `mariadb-admin` instead of `mysqladmin`, `mariadb-binlog` instead of `mysqlbinlog`, etc.
2. Always update the `README.md` in a given project if some changes are made that differ from documentation.
3. Always follow KISS, DRY, and YAGNI principles.
4. **Windows OpenSSH Bug Workaround:** When provisioning GCP VMs or running `gcloud compute ssh/scp` commands on Windows, native OpenSSH will fail with `CreateProcessW failed error:5` / `posix_spawnp: Input/output error` due to issues passing the ProxyCommand to the bundled Python executable. Workaround this by explicitly starting the IAP tunnel (`gcloud compute start-iap-tunnel`) in the background on a local port, performing standard `ssh` or `scp` to `localhost:<port>`, and then killing the tunnel process.
5. VM connections must use the wrapper script (`connect_vm.ps1`) rather than raw `gcloud compute ssh` to avoid the Windows OpenSSH ProxyCommand bug.
6. When mounting dedicated data disks for MariaDB on Google Cloud, use the predictable paths under `/dev/disk/by-id/google-<device-name>` (e.g. `/dev/disk/by-id/google-data-disk`) rather than `/dev/sdb` as device ordering is not guaranteed.
7. Ensure script operations (like VM creation, directory creation, data loading, database setup) are completely idempotent so they can be run multiple times safely.

## Environment Details

### VM Specification

- **Name:** `vm-ai-rag-challenge`
- **Zone:** `us-east1-b`
- **Machine Type:** `n2-standard-4` (4 vCPUs, 16GB Memory)
- **OS:** Ubuntu 22.04
- **Access:** IAP (Identity-Aware Proxy) SSH only via TCP port 22

### Attached Disks

- **Boot:** Default (10GB)
- **Data:** 64GB pd-ssd mounted at `/data` (MariaDB data, Redis data, uploads)
- **Logs:** 32GB pd-standard mounted at `/logs` (Application logs)

## Tech Stack

- PowerShell (Provisioning, Automation)
- Bash (Installation scripts)
- Python 3 (ELT Pipeline)
- MariaDB AI RAG 1.1 (Beta) with Docker Compose
- MariaDB 11.8 with native vector support
- Docker Engine & Docker Compose
- Google Cloud Platform (GCP)

## Key Files

- `pipeline/provision_vm.ps1`: Idempotent script to create the GCP VM, attached disks, and IAP firewall rules.
- `pipeline/upload_to_vm.ps1`: Securely copies the pipeline scripts to the VM, working around Windows SCP bugs.
- `pipeline/connect_vm.ps1`: Wrapper to securely SSH into the VM, bypassing Windows ProxyCommand bugs.
- `pipeline/configure_disks.sh`: Formats and mounts dedicated disks for data and logs.
- `pipeline/setup_docker_ai_rag.sh`: Installs Docker and deploys MariaDB AI RAG stack.
- `pipeline/docker-compose.yml`: Docker Compose configuration using mounted disks.
- `pipeline/ingest_zendesk.py`: Idempotent Python script to fetch, chunk, embed, and insert Zendesk tickets into MariaDB via API.
