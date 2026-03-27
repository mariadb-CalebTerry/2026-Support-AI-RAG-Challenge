<#
.SYNOPSIS
    Connects to the GCP VM via an IAP tunnel inline without using PuTTY.

.DESCRIPTION
    The native gcloud compute ssh command on Windows often fails with 
    "CreateProcessW failed error:5" due to how OpenSSH handles ProxyCommand 
    with the bundled Python executable. 
    
    This script works around that issue by explicitly starting the IAP 
    tunnel in the background on a local port, launching a standard inline 
    SSH session to that port, and then cleaning up the tunnel when you exit.
#>

$ErrorActionPreference = "Stop"

$ProjectId = "mariadb-rag-ai-challenge"
$VmName = "vm-ai-rag-challenge"
$Zone = "us-east1-b"
$LocalPort = 2222

Write-Host "Setting Google Cloud project to $ProjectId..." -ForegroundColor Cyan
gcloud config set project $ProjectId | Out-Null

# Kill any existing stray python tunnels on this port
$existingTunnels = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "start-iap-tunnel.*$VmName" }
if ($existingTunnels) {
    Write-Host "Cleaning up orphaned IAP tunnels..." -ForegroundColor Yellow
    $existingTunnels | Stop-Process -Force
}

Write-Host "Starting IAP tunnel to $VmName on localhost:$LocalPort..." -ForegroundColor Cyan
$tunnelProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c gcloud compute start-iap-tunnel $VmName 22 --zone=$Zone --local-host-port=localhost:$LocalPort" -WindowStyle Hidden -PassThru

# Wait a moment for the tunnel to establish
Start-Sleep -Seconds 3

# Determine SSH username (matches gcloud logic)
$accountEmail = gcloud config get-value core/account
$sshUser = ($accountEmail -split "@")[0] -replace "[^a-zA-Z0-9_]", "_"

Write-Host "Connecting via SSH as $sshUser..." -ForegroundColor Green
$sshKeyPath = "$env:USERPROFILE\.ssh\google_compute_engine"

try {
    # Run the native inline SSH command
    ssh -i "$sshKeyPath" -o StrictHostKeyChecking=no -p $LocalPort "$sshUser@localhost"
}
finally {
    Write-Host "SSH session ended. Cleaning up IAP tunnel..." -ForegroundColor Cyan
    if (-not $tunnelProcess.HasExited) {
        Stop-Process -Id $tunnelProcess.Id -Force -ErrorAction SilentlyContinue
    }
    
    # Double check no child python processes are left hanging
    Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "start-iap-tunnel.*$VmName" } | Stop-Process -Force -ErrorAction SilentlyContinue
}
