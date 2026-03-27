#!/bin/bash
# setup_docker_ai_rag.sh
# Script to deploy MariaDB AI RAG using Docker Compose on Ubuntu

set -e

echo "Starting MariaDB AI RAG Docker deployment..."

# Read credentials from files
MARIADB_TOKEN=$(cat /tmp/ai_rag_challenge_scripts/mariadb_token.txt)
GEMINI_API_KEY=$(cat /tmp/ai_rag_challenge_scripts/gemini_key.txt)
MARIADB_LICENSE_KEY=$(cat /tmp/ai_rag_challenge_scripts/rag_license.txt)
DOCKER_PAT=$(cat /tmp/ai_rag_challenge_scripts/docker_pat.txt)

echo "Updating system and installing prerequisites..."
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release apt-transport-https software-properties-common wget git

echo "Installing Docker Engine..."
# Add Docker's official GPG key:
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF

# Install Docker Engine
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "Starting and enabling Docker service..."
sudo systemctl start docker
sudo systemctl enable docker

echo "Configuring Docker to use mounted disks..."
# Stop Docker service
sudo systemctl stop docker

# Create Docker data directories on mounted disk
sudo mkdir -p /data/docker /data/containerd-data

# Configure Docker to use the new data directory
sudo tee /etc/docker/daemon.json > /dev/null << EOF
{
  "data-root": "/data/docker",
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

# Configure containerd to use the new data directory
sudo tee /etc/containerd/config.toml > /dev/null << EOF
version = 2
root = "/data/containerd-data"
EOF

# Move existing containerd data if it exists
if [ -d "/var/lib/containerd" ] && [ "$(ls -A /var/lib/containerd)" ]; then
    echo "Moving existing containerd data to mounted disk..."
    sudo mv /var/lib/containerd/* /data/containerd-data/ 2>/dev/null || true
fi

# Start Docker service with new configuration
sudo systemctl restart containerd
sudo systemctl start docker
sudo systemctl daemon-reload

echo "Docker and containerd configured to use mounted disks"

echo "Adding current user to docker group..."
sudo usermod -aG docker $USER

echo "Checking if dedicated disks are mounted..."
echo "Current mount status:"
df -h | grep -E "/data|/logs" || echo "No /data or /logs mounts found"

# Check if /data is mounted using df (more reliable than mountpoint)
if df -h | grep -q "/data"; then
    echo "Data disk is already mounted"
else
    echo "Data disk not mounted. Running disk configuration..."
    bash /tmp/ai_rag_challenge_scripts/src/configure_disks.sh
    echo "Disk configuration completed. Verifying mounts..."
    df -h | grep -q "/data" && echo "/data is now mounted" || echo "ERROR: /data still not mounted"
    df -h | grep -q "/logs" && echo "/logs is now mounted" || echo "ERROR: /logs still not mounted"
fi

echo "Creating deployment directory..."
sudo mkdir -p /data/mariadb-rag-deployment
cd /data/mariadb-rag-deployment

echo "Creating required directories..."
sudo mkdir -p /data/uploaded_files /data/redis /logs/rag
sudo chown -R $USER:$USER /data/uploaded_files /data/redis /logs/rag

echo "Downloading Docker Compose configuration..."
if [ ! -f "docker-compose.yml" ]; then
    sudo cp /tmp/ai_rag_challenge_scripts/src/docker-compose.yml docker-compose.yml
    sudo chown $USER:$USER docker-compose.yml
else
    echo "docker-compose.yml already exists, skipping download"
fi

echo "Generating secure keys..."
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET_KEY=$SECRET_KEY
MCP_AUTH_SECRET_KEY=$SECRET_KEY

echo "Creating configuration file with credentials..."
if [ ! -f "config.env" ]; then
    # Use the existing config.env as template
    sudo cp /tmp/ai_rag_challenge_scripts/src/config.env .env
    
    # Update with the actual credentials read earlier
    sudo sed -i "s/GEMINI_API_KEY=.*/GEMINI_API_KEY=$GEMINI_API_KEY/" .env
    sudo sed -i "s/MARIADB_LICENSE_KEY=.*/MARIADB_LICENSE_KEY=$MARIADB_LICENSE_KEY/" .env
    
    # Generate new secure keys and update them
    SECRET_KEY=$(openssl rand -hex 32)
    sudo sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SECRET_KEY/" .env
    sudo sed -i "s/JWT_SECRET_KEY=.*/JWT_SECRET_KEY=$SECRET_KEY/" .env
    sudo sed -i "s/MCP_AUTH_SECRET_KEY=.*/MCP_AUTH_SECRET_KEY=$SECRET_KEY/" .env
    
    sudo chown $USER:$USER .env
else
    echo ".env already exists, skipping creation"
fi

echo "Setting proper permissions..."
chmod 600 .env
sudo chmod 755 /data/uploaded_files /logs/rag

echo "Logging into Docker..."
echo "$DOCKER_PAT" | sudo docker login -u calebterrymdb --password-stdin

echo "Pulling Docker images..."
if docker compose -f docker-compose.yml --env-file .env pull; then
    echo "Docker images pulled successfully"
else
    echo "Warning: Some images may have failed to pull, continuing..."
fi

echo "Starting MariaDB AI RAG stack..."
if docker compose -f docker-compose.yml --env-file .env up -d; then
    echo "Docker stack started successfully"
else
    echo "Error: Failed to start Docker stack"
    exit 1
fi

echo "Waiting for services to be ready..."
sleep 30

echo "Checking service status..."
docker compose -f docker-compose.yml --env-file .env ps

echo "Waiting for database initialization..."
sleep 60

echo "Checking health endpoints..."
echo "Testing RAG API health..."
curl -s http://localhost:8000/health || echo "RAG API not ready yet"

echo "Testing MCP Server health..."
curl -s http://localhost:8002/health || echo "MCP Server not ready yet"

echo ""
echo "======================================================"
echo "MariaDB AI RAG Docker Deployment Complete!"
echo "======================================================"
echo "Access Points:"
echo "- RAG API Swagger UI: http://localhost:8000/docs"
echo "- RAG API Health: http://localhost:8000/health"
echo "- MCP Server: http://localhost:8002/mcp"
echo "- MCP Health: http://localhost:8002/health"
echo ""
echo "To check status: docker compose -f docker-compose.yml ps"
echo "To view logs: docker compose -f docker-compose.yml logs"
echo "To stop: docker compose -f docker-compose.yml down"
echo "======================================================"

# Get the external IP for external access
echo "Getting external IP..."
EXTERNAL_IP=$(curl -s ifconfig.me)
if [ -n "$EXTERNAL_IP" ]; then
    echo "External access will be available at:"
    echo "- RAG API: http://$EXTERNAL_IP:8000/docs"
    echo "- MCP Server: http://$EXTERNAL_IP:8002/mcp"
fi
