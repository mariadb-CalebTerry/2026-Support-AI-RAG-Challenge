#!/usr/bin/env bash
#
# Creates IAP tunnels to multiple ports on the GCP VM simultaneously.
#
# Works around SSH ProxyCommand issues by explicitly starting IAP tunnels
# in the background on local ports.
# Tunnels both port 8000 (RAG API) and 8002 (MCP Server).

set -euo pipefail

PROJECT_ID="mariadb-rag-ai-challenge"
VM_NAME="vm-ai-rag-challenge"
ZONE="us-east1-b"

declare -A SERVICES
SERVICES[8000]="RAG API"
SERVICES[8002]="MCP Server"

PORTS=(8000 8002)

declare -A TUNNEL_PIDS

cleanup() {
    echo ""
    echo "Stopping all IAP tunnels..."
    for port in "${PORTS[@]}"; do
        if [[ -n "${TUNNEL_PIDS[$port]:-}" ]] && kill -0 "${TUNNEL_PIDS[$port]}" 2>/dev/null; then
            kill "${TUNNEL_PIDS[$port]}" 2>/dev/null || true
        fi
    done
    # Kill any lingering gcloud iap-tunnel processes for these ports
    for port in "${PORTS[@]}"; do
        pkill -f "start-iap-tunnel.*${VM_NAME}.*${port}" 2>/dev/null || true
    done
    echo "All tunnels stopped."
    exit 0
}

trap cleanup INT TERM

start_tunnel() {
    local port=$1
    gcloud compute start-iap-tunnel "$VM_NAME" "$port" \
        --zone="$ZONE" \
        --local-host-port="localhost:${port}" \
        --project="$PROJECT_ID" \
        > /dev/null 2>&1 &
    echo $!
}

echo "Setting Google Cloud project to ${PROJECT_ID}..."
gcloud config set project "$PROJECT_ID" > /dev/null

# Kill any existing stray iap-tunnel processes for these ports
for port in "${PORTS[@]}"; do
    if pkill -f "start-iap-tunnel.*${VM_NAME}.*${port}" 2>/dev/null; then
        echo "Cleaned up orphaned IAP tunnels for ${SERVICES[$port]} (port ${port})."
    fi
done

echo "Starting IAP tunnels to ${VM_NAME}..."
echo "Ports to be tunneled:"
for port in "${PORTS[@]}"; do
    echo "  - ${SERVICES[$port]}: localhost:${port} -> ${VM_NAME}:${port}"
done
echo "Press Ctrl+C to stop all tunnels"

# Start all tunnel processes
for port in "${PORTS[@]}"; do
    echo "Starting tunnel for ${SERVICES[$port]} on port ${port}..."
    TUNNEL_PIDS[$port]=$(start_tunnel "$port")
    sleep 2  # Brief delay between starting tunnels
done

echo "All tunnels started successfully!"
echo "Access services at:"
for port in "${PORTS[@]}"; do
    echo "  - ${SERVICES[$port]}: http://localhost:${port}"
done
echo "Press Ctrl+C to stop all tunnels..."

# Monitor tunnels and restart if they exit unexpectedly
while true; do
    sleep 1
    for port in "${PORTS[@]}"; do
        pid="${TUNNEL_PIDS[$port]:-}"
        if [[ -n "$pid" ]] && ! kill -0 "$pid" 2>/dev/null; then
            echo "Warning: Tunnel for ${SERVICES[$port]} (port ${port}) exited unexpectedly. Restarting in 3 seconds..."
            pkill -f "start-iap-tunnel.*${VM_NAME}.*${port}" 2>/dev/null || true
            sleep 3
            TUNNEL_PIDS[$port]=$(start_tunnel "$port")
        fi
    done
done
