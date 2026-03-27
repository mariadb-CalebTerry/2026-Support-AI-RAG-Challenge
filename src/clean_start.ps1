<#
.SYNOPSIS
    Resets the Docker environment and wipes data directories on the GCP VM.

.DESCRIPTION
    This script connects to the VM over an Identity-Aware Proxy (IAP) tunnel,
    stops all running Docker containers, removes all Docker images, containers, 
    volumes, and networks to provide a clean slate. It also wipes the contents
    of /data/mariadb-rag-deployment/*.
#>

$ErrorActionPreference = "Stop"

# Configuration
$ProjectId = "mariadb-rag-ai-challenge"
$VmName = "vm-ai-rag-challenge"
$Zone = "us-east1-b"

Write-Host "Setting Google Cloud project to $ProjectId..." -ForegroundColor Cyan
gcloud config set project $ProjectId

Write-Host "Starting IAP tunnel to VM '$VmName'..." -ForegroundColor Cyan
$tunnelProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c gcloud compute start-iap-tunnel $VmName 22 --zone=$Zone --local-host-port=localhost:2222" -WindowStyle Hidden -PassThru

# Wait a moment for the tunnel to establish
Start-Sleep -Seconds 5

# Determine SSH username
$accountEmail = gcloud config get-value core/account
$sshUser = ($accountEmail -split "@")[0] -replace "[^a-zA-Z0-9_]", "_"
$sshKeyPath = "$env:USERPROFILE\.ssh\google_compute_engine"

$remoteCommand = @"
    echo ""
    echo "======================================================"
    echo "Starting Clean Slate Process..."
    echo "======================================================"
    echo ""
    
    if command -v docker &> /dev/null; then
        echo "Stopping all Docker containers..."
        sudo docker ps -aq | xargs -r sudo docker stop
        
        echo "Removing all Docker containers, images, volumes, and networks..."
        sudo docker system prune -a -f --volumes
    else
        echo "Docker is not installed. Skipping Docker cleanup."
    fi
    
    echo "Wiping /data/mariadb/* ..."
    sudo rm -rf /data/mariadb/*
    
    echo ""
    echo "======================================================"
    echo "Clean Start Process Complete!"
    echo "======================================================"
"@

try {
    Write-Host "Executing cleanup commands on the VM..." -ForegroundColor Cyan
    ssh -i "$sshKeyPath" -o StrictHostKeyChecking=accept-new -p 2222 "$sshUser@localhost" $remoteCommand
}
finally {
    Write-Host "Closing IAP tunnel..." -ForegroundColor Cyan
    if (-not $tunnelProcess.HasExited) {
        Stop-Process -Id $tunnelProcess.Id -Force -ErrorAction SilentlyContinue
    }
    Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "start-iap-tunnel.*$VmName" } | Stop-Process -Force -ErrorAction SilentlyContinue
}

Write-Host "Local cleanup script finished." -ForegroundColor Green
