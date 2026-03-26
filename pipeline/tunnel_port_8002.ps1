<#
.SYNOPSIS
    Creates an IAP tunnel to port 8002 on the GCP VM.

.DESCRIPTION
    Works around the Windows OpenSSH ProxyCommand bug by explicitly 
    starting the IAP tunnel in the background on a local port.
#>

$ErrorActionPreference = "Stop"

$ProjectId = "mariadb-rag-ai-challenge"
$VmName = "vm-ai-rag-challenge"
$Zone = "us-east1-b"
$RemotePort = 8002
$LocalPort = 8002

Write-Host "Setting Google Cloud project to $ProjectId..." -ForegroundColor Cyan
gcloud config set project $ProjectId | Out-Null

# Kill any existing stray python tunnels on this port
$existingTunnels = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "start-iap-tunnel.*$VmName.*$RemotePort" }
if ($existingTunnels) {
    Write-Host "Cleaning up orphaned IAP tunnels..." -ForegroundColor Yellow
    $existingTunnels | Stop-Process -Force
}

Write-Host "Starting IAP tunnel to $VmName port $RemotePort on localhost:$LocalPort..." -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the tunnel" -ForegroundColor Yellow

try {
    # Start the tunnel process
    $tunnelProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c gcloud compute start-iap-tunnel $VmName $RemotePort --zone=$Zone --local-host-port=localhost:$LocalPort" -WindowStyle Normal -PassThru
    
    # Wait for the process to exit (user will need to press Ctrl+C)
    $tunnelProcess.WaitForExit()
}
finally {
    Write-Host "Cleaning up IAP tunnel..." -ForegroundColor Cyan
    if (-not $tunnelProcess.HasExited) {
        Stop-Process -Id $tunnelProcess.Id -Force -ErrorAction SilentlyContinue
    }
    
    # Double check no child python processes are left hanging
    Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "start-iap-tunnel.*$VmName.*$RemotePort" } | Stop-Process -Force -ErrorAction SilentlyContinue
}
