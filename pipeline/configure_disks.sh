#!/bin/bash
# configure_disks.sh
# Script to configure dedicated disks for MariaDB data and logs

set -e

echo "Configuring dedicated disks for MariaDB..."

# Format and mount data disk if not already mounted
if ! mountpoint -q /data; then
    echo "Formatting and mounting /data..."
    sudo mkdir -p /data
    # Use standard GCP device names
    sudo mkfs.ext4 -m 0 -F -E lazy_itable_init=0,lazy_journal_init=0,discard /dev/disk/by-id/google-data-disk
    sudo mount -o discard,defaults /dev/disk/by-id/google-data-disk /data
    if ! grep -q "/data" /etc/fstab; then
        echo "/dev/disk/by-id/google-data-disk /data ext4 discard,defaults 0 2" | sudo tee -a /etc/fstab
    fi
fi

# Format and mount log disk if not already mounted
if ! mountpoint -q /logs; then
    echo "Formatting and mounting /logs..."
    sudo mkdir -p /logs
    sudo mkfs.ext4 -m 0 -F -E lazy_itable_init=0,lazy_journal_init=0,discard /dev/disk/by-id/google-log-disk
    sudo mount -o discard,defaults /dev/disk/by-id/google-log-disk /logs
    if ! grep -q "/logs" /etc/fstab; then
        echo "/dev/disk/by-id/google-log-disk /logs ext4 discard,defaults 0 2" | sudo tee -a /etc/fstab
    fi
fi

echo "Setting permissions for MariaDB directories..."
sudo mkdir -p /data/mariadb /logs/mariadb
sudo chown -R mysql:mysql /data/mariadb /logs/mariadb

echo "Creating additional directories for Docker deployment..."
sudo mkdir -p /data/uploaded_files /data/redis /logs/rag
sudo chown -R $USER:$USER /data/uploaded_files /data/redis /logs/rag

echo "======================================================"
echo "Disk configuration complete!"
echo "Data disk mounted at /data"
echo "Logs disk mounted at /logs"
echo "MariaDB directories created and permissions set"
echo "======================================================
