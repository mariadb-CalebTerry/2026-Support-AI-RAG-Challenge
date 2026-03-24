#!/bin/bash
# install_mariadb_native.sh
# Script to provision MariaDB Enterprise Server (with Vector support) and MariaDB AI RAG natively

set -e

echo "Updating system and installing prerequisites..."
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release apt-transport-https software-properties-common wget

# Check if MariaDB Enterprise Server is already installed
if dpkg -l | grep -q mariadb-server; then
    echo "MariaDB Server is already installed. Skipping repository setup and installation."
else
    echo "======================================================"
    echo "MariaDB Enterprise Repository Setup"
    echo "To install MariaDB Enterprise Server, you need your Customer Download Token."
    echo "You can find this in the MariaDB Customer Portal."
    echo "======================================================"

    read -sp "Enter your Customer Download Token: " MARIADB_TOKEN
    echo ""

    echo "Downloading MariaDB repository setup script..."
    curl -Os https://downloads.mariadb.com/MariaDB/mariadb_repo_setup

    echo "Running MariaDB repository setup for Enterprise Server 11.4..."
    sudo bash mariadb_repo_setup --token="$MARIADB_TOKEN" --mariadb-server-version="mariadb-11.4"

    echo "Installing MariaDB Enterprise Server..."
    sudo apt-get update
    sudo apt-get install -y mariadb-server
fi

echo "Configuring dedicated disks for MariaDB..."
# Format and mount data disk if not already mounted
if ! mountpoint -q /data; then
    echo "Formatting and mounting /data..."
    sudo mkdir -p /data
    # Use standard GCP device names
    sudo mkfs.ext4 -m 0 -F -E lazy_itable_init=0,lazy_journal_init=0,discard /dev/disk/by-id/google-data-disk
    sudo mount -o discard,defaults /dev/disk/by-id/google-data-disk /data
    echo "/dev/disk/by-id/google-data-disk /data ext4 discard,defaults 0 2" | sudo tee -a /etc/fstab
fi

# Format and mount log disk if not already mounted
if ! mountpoint -q /logs; then
    echo "Formatting and mounting /logs..."
    sudo mkdir -p /logs
    sudo mkfs.ext4 -m 0 -F -E lazy_itable_init=0,lazy_journal_init=0,discard /dev/disk/by-id/google-log-disk
    sudo mount -o discard,defaults /dev/disk/by-id/google-log-disk /logs
    echo "/dev/disk/by-id/google-log-disk /logs ext4 discard,defaults 0 2" | sudo tee -a /etc/fstab
fi

echo "Setting permissions for MariaDB directories..."
sudo mkdir -p /data/mariadb /logs/mariadb
sudo chown -R mysql:mysql /data/mariadb /logs/mariadb

echo "Configuring MariaDB with optimized server.cnf..."
# Stop MariaDB if it's running
sudo systemctl stop mariadb || true

# Backup the original 50-server.cnf
sudo cp /etc/mysql/mariadb.conf.d/50-server.cnf /etc/mysql/mariadb.conf.d/50-server.cnf.backup

# Replace with our optimized server.cnf
sudo cp /tmp/ai_rag_challenge_scripts/pipeline/server.cnf /etc/mysql/mariadb.conf.d/50-server.cnf

# Initialize the new data directory if it's empty
if [ -z "$(ls -A /data/mariadb)" ]; then
    echo "Initializing new MariaDB data directory..."
    sudo mariadb-install-db --user=mysql --datadir=/data/mariadb
fi

echo "Ensuring MariaDB service is running..."
sudo systemctl enable mariadb
sudo systemctl restart mariadb

# Setup RAG database and user idempotently
echo "Configuring database for AI RAG..."
sudo mariadb -e "CREATE DATABASE IF NOT EXISTS \`zendesk_rag\`;"
sudo mariadb -e "CREATE USER IF NOT EXISTS 'rag_user'@'localhost' IDENTIFIED BY 'ragpassword';"
sudo mariadb -e "GRANT ALL PRIVILEGES ON \`zendesk_rag\`.* TO 'rag_user'@'localhost';"
sudo mariadb -e "FLUSH PRIVILEGES;"

# Check if AI RAG is already installed
if dpkg -l | grep -q ai-rag; then
    echo "MariaDB AI RAG is already installed."
else
    echo "======================================================"
    echo "MariaDB AI RAG Installation"
    echo "Please download the MariaDB AI RAG .deb package from:"
    echo "https://mariadb.com/downloads/enterprise-tooling/ai-rag/"
    echo "and upload it to this server."
    echo "======================================================"
    
    read -p "Enter the path to the ai-rag .deb file (e.g., ./ai-rag-1.0.0.deb): " AIRAG_DEB_PATH
    
    if [ ! -f "$AIRAG_DEB_PATH" ]; then
        echo "Error: File $AIRAG_DEB_PATH not found."
        exit 1
    fi

    echo "Installing MariaDB AI RAG..."
    sudo dpkg -i "$AIRAG_DEB_PATH" || true
    
    echo "Installing any missing dependencies for AI RAG..."
    sudo apt-get install -f -y
fi

echo "======================================================"
echo "Installation complete!"
echo "MariaDB Enterprise Server is running natively."
echo "MariaDB AI RAG has been installed natively."
echo "======================================================"
