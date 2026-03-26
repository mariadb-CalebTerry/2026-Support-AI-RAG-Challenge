<#
.SYNOPSIS
    Creates IAP tunnels to multiple ports on the GCP VM simultaneously.

.DESCRIPTION
    Works around the Windows OpenSSH ProxyCommand bug by explicitly 
    starting IAP tunnels in the background on local ports.
    Tunnels both port 8000 (RAG API) and 8002 (MCP Server).
#>

$ErrorActionPreference = "Stop"

$ProjectId = "mariadb-rag-ai-challenge"
$VmName = "vm-ai-rag-challenge"
$Zone = "us-east1-b"

$Ports = @(
    @{ RemotePort = 8000; LocalPort = 8000; Service = "RAG API" },
    @{ RemotePort = 8002; LocalPort = 8002; Service = "MCP Server" }
)

Write-Host "Setting Google Cloud project to $ProjectId..." -ForegroundColor Cyan
gcloud config set project $ProjectId | Out-Null

# Kill any existing stray python tunnels for these ports
foreach ($port in $Ports) {
    $existingTunnels = Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "start-iap-tunnel.*$VmName.*$($port.RemotePort)" }
    if ($existingTunnels) {
        Write-Host "Cleaning up orphaned IAP tunnels for $($port.Service) (port $($port.RemotePort))..." -ForegroundColor Yellow
        $existingTunnels | Stop-Process -Force
    }
}

Write-Host "Starting IAP tunnels to $VmName..." -ForegroundColor Cyan
Write-Host "Ports to be tunneled:" -ForegroundColor Green
foreach ($port in $Ports) {
    Write-Host "  - $($port.Service): localhost:$($port.LocalPort) -> ${VmName}:$($port.RemotePort)" -ForegroundColor White
}
Write-Host "Press Ctrl+C to stop all tunnels" -ForegroundColor Yellow

$tunnelProcesses = @()

try {
    # Start all tunnel processes
    foreach ($port in $Ports) {
        Write-Host "Starting tunnel for $($port.Service) on port $($port.RemotePort)..." -ForegroundColor Cyan
        $tunnelProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c gcloud compute start-iap-tunnel $VmName $($port.RemotePort) --zone=$Zone --local-host-port=localhost:$($port.LocalPort)" -WindowStyle Hidden -PassThru
        $tunnelProcesses += $tunnelProcess
        Start-Sleep -Seconds 2  # Brief delay between starting tunnels
    }
    
    Write-Host "All tunnels started successfully!" -ForegroundColor Green
    Write-Host "Access services at:" -ForegroundColor Green
    foreach ($port in $Ports) {
        Write-Host "  - $($port.Service): http://localhost:$($port.LocalPort)" -ForegroundColor White
    }
    Write-Host "Press Ctrl+C to stop all tunnels..." -ForegroundColor Yellow
    
    # Wait for user to stop (Ctrl+C)
    while ($true) {
        Start-Sleep -Seconds 1
        
        # Check if any tunnel process has exited
        foreach ($process in $tunnelProcesses) {
            if ($process.HasExited) {
                Write-Host "Warning: Tunnel process exited unexpectedly. Restarting..." -ForegroundColor Yellow
                # Find which port this was for and restart it
                $portInfo = $Ports | Where-Object { $_.RemotePort -eq 8000 } | Select-Object -First 1
                if ($portInfo) {
                    $newProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c gcloud compute start-iap-tunnel $VmName $($portInfo.RemotePort) --zone=$Zone --local-host-port=localhost:$($portInfo.LocalPort)" -WindowStyle Hidden -PassThru
                    $tunnelProcesses = $tunnelProcesses -replace $process, $newProcess
                }
            }
        }
    }
}
catch {
    Write-Host "Error occurred: $_" -ForegroundColor Red
}
finally {
    Write-Host "Stopping all IAP tunnels..." -ForegroundColor Cyan
    foreach ($process in $tunnelProcesses) {
        if (-not $process.HasExited) {
            Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
        }
    }
    
    # Double check no child python processes are left hanging
    foreach ($port in $Ports) {
        Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "start-iap-tunnel.*$VmName.*$($port.RemotePort)" } | Stop-Process -Force -ErrorAction SilentlyContinue
    }
    
    Write-Host "All tunnels stopped." -ForegroundColor Green
}
