#!/bin/bash
# setup_docker_ai_rag.sh
# Script to deploy MariaDB AI RAG using Docker Compose on Ubuntu

set -e

echo "Starting MariaDB AI RAG Docker deployment..."

# Read credentials from files
MARIADB_TOKEN=$(cat /tmp/ai_rag_challenge_scripts/mariadb_token.txt)
GEMINI_API_KEY=$(cat /tmp/ai_rag_challenge_scripts/gemini_key.txt)
MARIADB_LICENSE_KEY=$(cat /tmp/ai_rag_challenge_scripts/rag_license.txt)

echo "Updating system and installing prerequisites..."
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release apt-transport-https software-properties-common wget git

echo "Installing Docker Engine..."
# Add Docker's official GPG key
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up the repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker Engine
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "Starting and enabling Docker service..."
sudo systemctl start docker
sudo systemctl enable docker

echo "Adding current user to docker group..."
sudo usermod -aG docker $USER

echo "Creating deployment directory..."
mkdir -p /home/$USER/mariadb-rag-deployment
cd /home/$USER/mariadb-rag-deployment

echo "Creating required directories..."
mkdir -p uploaded_files logs

echo "Downloading Docker Compose configuration..."
curl -fsSL https://raw.githubusercontent.com/mariadb-corporation/mariadb-docs/refs/heads/main/tools/docker-compose.dockerhub-dev.yml -o docker-compose.dockerhub-dev.yml

echo "Generating secure keys..."
SECRET_KEY=$(openssl rand -hex 32)
JWT_SECRET_KEY=$SECRET_KEY
MCP_AUTH_SECRET_KEY=$SECRET_KEY

echo "Creating configuration file with credentials..."
cat > config.env.secure << EOF
# ===== DATABASE CONFIGURATION =====
DB_HOST=mysql-db
DB_PORT=3306
DB_USER=root
DB_PASSWORD=mariadb_rag_password_2024
DB_NAME=kb_chunks

# ===== MARIADB LICENSE KEY (MANDATORY) =====
MARIADB_LICENSE_KEY=$MARIADB_LICENSE_KEY

# ===== API KEYS =====
GEMINI_API_KEY=$GEMINI_API_KEY

# ===== SECURITY KEYS (MUST BE IDENTICAL) =====
SECRET_KEY=$SECRET_KEY
JWT_SECRET_KEY=$JWT_SECRET_KEY
MCP_AUTH_SECRET_KEY=$MCP_AUTH_SECRET_KEY

# ===== SERVER CONFIGURATION =====
APP_HOST=rag-api
APP_PORT=8000
MCP_HOST=rag-api
MCP_PORT=8002

# ===== EMBEDDING & LLM =====
EMBEDDING_PROVIDER=gemini
embedding_model=text-embedding-004
LLM_PROVIDER=gemini
LLM_MODEL=gemini-2.0-flash

# ===== TABLE NAMES =====
DOCUMENTS_TABLE=documents_DEMO_gemini
VDB_TABLE=vdb_tbl_DEMO_gemini

# ===== MCP CONFIGURATION =====
MCP_ENABLE_AUTH=true
MCP_ENABLE_VECTOR_TOOLS=true
MCP_ENABLE_DATABASE_TOOLS=true
MCP_ENABLE_RAG_TOOLS=true
MCP_READ_ONLY=false
MCP_LOG_LEVEL=INFO

# ===== PROCESSING =====
CHUNK_SIZE=512
CHUNK_OVERLAP=128
DOCUMENT_PROCESSING_BATCH_SIZE=5
EMBEDDING_BATCH_SIZE=32

# ===== RERANKING =====
RERANKING_ENABLED=true
RERANKING_MODEL_TYPE=flashrank
RERANKING_MODEL_NAME=ms-marco-MiniLM-L-12-v2

# ===== DOCKER INTERNAL HOSTNAMES (CRITICAL) =====
MCP_MARIADB_HOST=rag-api
EOF

echo "Setting proper permissions..."
chmod 600 config.env.secure
chmod 755 uploaded_files logs

echo "Pulling Docker images..."
docker compose -f docker-compose.dockerhub-dev.yml --env-file config.env.secure pull

echo "Starting MariaDB AI RAG stack..."
docker compose -f docker-compose.dockerhub-dev.yml --env-file config.env.secure up -d

echo "Waiting for services to be ready..."
sleep 30

echo "Checking service status..."
docker compose -f docker-compose.dockerhub-dev.yml --env-file config.env.secure ps

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
echo "To check status: docker compose -f docker-compose.dockerhub-dev.yml ps"
echo "To view logs: docker compose -f docker-compose.dockerhub-dev.yml logs"
echo "To stop: docker compose -f docker-compose.dockerhub-dev.yml down"
echo "======================================================"

# Get the external IP for external access
echo "Getting external IP..."
EXTERNAL_IP=$(curl -s ifconfig.me)
if [ -n "$EXTERNAL_IP" ]; then
    echo "External access will be available at:"
    echo "- RAG API: http://$EXTERNAL_IP:8000/docs"
    echo "- MCP Server: http://$EXTERNAL_IP:8002/mcp"
fi
