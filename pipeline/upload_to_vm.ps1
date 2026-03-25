<#
.SYNOPSIS
    Uploads the installation and ingestion scripts to the provisioned GCP VM.

.DESCRIPTION
    This script uses gcloud compute scp to securely transfer the pipeline 
    directory over an Identity-Aware Proxy (IAP) tunnel to the target VM 
    into the /tmp/ai_rag_challenge_scripts directory.
#>

$ErrorActionPreference = "Stop"

# Configuration
$ProjectId = "mariadb-rag-ai-challenge"
$VmName = "vm-ai-rag-challenge"
$Zone = "us-east1-b"
$RemoteDir = "/tmp/ai_rag_challenge_scripts"
$LocalPipelineDir = "C:\Projects\MariaDB\2026 Support AI RAG Challenge\pipeline"
$LocalCredentialDir = "C:\Projects\MariaDB\2026 Support AI RAG Challenge"

Write-Host "Setting Google Cloud project to $ProjectId..." -ForegroundColor Cyan
gcloud config set project $ProjectId

Write-Host "Creating target directory $RemoteDir on VM '$VmName'..." -ForegroundColor Cyan
$tunnelProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c gcloud compute start-iap-tunnel $VmName 22 --zone=$Zone --local-host-port=localhost:2222" -WindowStyle Hidden -PassThru

# Wait a moment for the tunnel to establish
Start-Sleep -Seconds 5

# Determine SSH username
$accountEmail = gcloud config get-value core/account
$sshUser = ($accountEmail -split "@")[0] -replace "[^a-zA-Z0-9_]", "_"
$sshKeyPath = "$env:USERPROFILE\.ssh\google_compute_engine"

try {
    Write-Host "Creating remote directory..." -ForegroundColor Cyan
    ssh -i "$sshKeyPath" -o StrictHostKeyChecking=no -p 2222 "$sshUser@localhost" "mkdir -p $RemoteDir"

    Write-Host "Uploading pipeline files to the VM..." -ForegroundColor Cyan
    # Create a temporary directory excluding unwanted folders
    $tempDir = "$env:TEMP\ai_rag_upload_$(Get-Random)"
    New-Item -ItemType Directory -Path $tempDir -Force | Out-Null
    
    try {
        # Copy pipeline files excluding unwanted directories
        Write-Host "Preparing files for upload (excluding __pycache__, logs, uploaded_files)..." -ForegroundColor Cyan
        Get-ChildItem -Path $LocalPipelineDir | Where-Object { 
            $_.Name -notin @("__pycache__", "logs", "uploaded_files") -and 
            !$_.Name.StartsWith("__pycache__") 
        } | ForEach-Object {
            $targetPath = Join-Path $tempDir $_.Name
            if ($_.PSIsContainer) {
                # Recursively copy directory excluding __pycache__
                robocopy $_.FullName $targetPath /E /XD "__pycache__" /NFL /NDL /NJH /NJS
            }
            else {
                Copy-Item -Path $_.FullName -Destination $targetPath -Recurse -Force
            }
        }
        
        # Upload the cleaned directory
        scp -i "$sshKeyPath" -o StrictHostKeyChecking=no -P 2222 -r "$tempDir\*" "$sshUser@localhost`:$RemoteDir/pipeline"
    }
    finally {
        # Clean up temporary directory
        if (Test-Path $tempDir) {
            Remove-Item -Path $tempDir -Recurse -Force
        }
    }

    Write-Host "Uploading credential files..." -ForegroundColor Cyan
    scp -i "$sshKeyPath" -o StrictHostKeyChecking=no -P 2222 "$LocalCredentialDir\mariadb_token.txt" "$sshUser@localhost`:$RemoteDir/"
    scp -i "$sshKeyPath" -o StrictHostKeyChecking=no -P 2222 "$LocalCredentialDir\gemini_key.txt" "$sshUser@localhost`:$RemoteDir/"
    scp -i "$sshKeyPath" -o StrictHostKeyChecking=no -P 2222 "$LocalCredentialDir\rag_license.txt" "$sshUser@localhost`:$RemoteDir/"
}
finally {
    if (-not $tunnelProcess.HasExited) {
        Stop-Process -Id $tunnelProcess.Id -Force -ErrorAction SilentlyContinue
    }
    Get-Process -Name "python" -ErrorAction SilentlyContinue | Where-Object { $_.CommandLine -match "start-iap-tunnel.*$VmName" } | Stop-Process -Force -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "Upload Complete!" -ForegroundColor Green
Write-Host "Your files are located on the VM at: $RemoteDir/pipeline" -ForegroundColor White
Write-Host "Credentials are located on the VM at: $RemoteDir/" -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Connect to the VM:" -ForegroundColor White
Write-Host "   .\connect_vm.ps1" -ForegroundColor Cyan
Write-Host "2. Navigate to the uploaded directory:" -ForegroundColor White
Write-Host "   cd $RemoteDir/pipeline" -ForegroundColor Cyan
Write-Host "3. Run the Docker setup script:" -ForegroundColor White
Write-Host "   bash setup_docker_ai_rag.sh" -ForegroundColor Cyan
Write-Host "======================================================" -ForegroundColor Green
