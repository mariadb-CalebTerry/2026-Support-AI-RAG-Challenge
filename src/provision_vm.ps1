<#
.SYNOPSIS
    Provisions a Google Cloud VM and configures Identity-Aware Proxy (IAP) access.

.DESCRIPTION
    This script automates the creation of the `elt-mcp-host` VM in the `mariadb-rag-ai-challenge`
    GCP project. It sets the required image, machine type, and tags, and creates a firewall rule
    allowing SSH access exclusively via IAP.
#>

$ErrorActionPreference = "Stop"

# Configuration
$ProjectId = "mariadb-rag-ai-challenge"
$VmName = "vm-ai-rag-challenge"
$Zone = "us-east1-b"
$MachineType = "n2-standard-4"
$ImageFamily = "ubuntu-2204-lts"
$ImageProject = "ubuntu-os-cloud"

Write-Host "Setting Google Cloud project to $ProjectId..." -ForegroundColor Cyan
gcloud config set project $ProjectId

Write-Host "Deleting existing VM instance '$VmName' if it exists..." -ForegroundColor Cyan
$vmExists = gcloud compute instances list --filter="name=$VmName" --format="value(name)"
if ($vmExists) {
    Write-Host "Found existing VM '$VmName'. Deleting..." -ForegroundColor Yellow
    gcloud compute instances delete $VmName --zone=$Zone --quiet
    Write-Host "Existing VM deleted." -ForegroundColor Green
}
else {
    Write-Host "No existing VM '$VmName' found. Continuing..." -ForegroundColor Yellow
}

Write-Host "Provisioning VM instance '$VmName' with dedicated data and log disks..." -ForegroundColor Cyan
gcloud compute instances create $VmName `
    --machine-type=$MachineType `
    --zone=$Zone `
    --image-family=$ImageFamily `
    --image-project=$ImageProject `
    --tags="iap" `
    --create-disk="name=$VmName-data,size=64GB,type=pd-ssd,auto-delete=yes,device-name=data-disk" `
    --create-disk="name=$VmName-logs,size=32GB,type=pd-standard,auto-delete=yes,device-name=log-disk"

Write-Host "Creating firewall rule to allow SSH and RAG services via IAP..." -ForegroundColor Cyan
# Check if firewall rule already exists to prevent errors on re-runs
$fwRuleExists = gcloud compute firewall-rules list --filter="name=allow-ssh-from-iap" --format="value(name)"
if (-not $fwRuleExists) {
    gcloud compute firewall-rules create allow-ssh-from-iap `
        --direction=INGRESS `
        --action=allow `
        --rules=tcp:22,tcp:8000,tcp:8002 `
        --source-ranges=35.235.240.0/20 `
        --target-tags="iap"
}
else {
    Write-Host "Firewall rule 'allow-ssh-from-iap' already exists. Updating to include RAG ports..." -ForegroundColor Yellow
    gcloud compute firewall-rules update allow-ssh-from-iap `
        --allow tcp:22 --allow tcp:8000 --allow tcp:8002 `
        --source-ranges=35.235.240.0/20 `
        --target-tags="iap"
}

Write-Host ""
Write-Host "======================================================" -ForegroundColor Green
Write-Host "VM Provisioning Complete!" -ForegroundColor Green
Write-Host "You can now connect to your VM using:" -ForegroundColor Yellow
Write-Host "gcloud compute ssh $VmName --zone=$Zone --tunnel-through-iap" -ForegroundColor White
Write-Host "======================================================" -ForegroundColor Green
