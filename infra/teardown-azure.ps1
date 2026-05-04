# =============================================================================
# Azure Infrastructure Teardown for Proposal Generator POC
# =============================================================================
# Deletes all resources created by setup-azure.ps1.
# The Resource Group itself is NOT deleted (it was pre-existing).
#
# Prerequisites: Azure CLI installed and logged in (run: az login)
# Usage: .\teardown-azure.ps1 -Location "canadacentral" -SubscriptionId "your-sub-id"
# =============================================================================

param(
    [string]$SubscriptionId = "",
    [string]$ResourceGroup = "rg-proposal-poc",
    [string]$StorageAccount = "stproposalpoc",
    [string]$SearchService = "search-proposal-poc",
    [string]$OpenAIAccount = "oai-proposal-poc",
    [string]$LanguageAccount = "lang-proposal-poc",
    [string]$AIFoundryHub = "hub-proposal-poc",
    [string]$AIFoundryProject = "proj-proposal-poc",
    [string]$SearchConnectionName = "search-connection",
    [string]$OpenAIConnectionName = "aoai-connection"
)

$ErrorActionPreference = "Stop"

if ($SubscriptionId -eq "") {
    $SubscriptionId = (az account show --query "id" -o tsv)
    Write-Host "Auto-detected Subscription ID: $SubscriptionId" -ForegroundColor Gray
}

Write-Host "============================================" -ForegroundColor Red
Write-Host " Proposal Generator POC - Azure TEARDOWN" -ForegroundColor Red
Write-Host "============================================" -ForegroundColor Red
Write-Host ""
Write-Host "This will DELETE the following resources in RG '$ResourceGroup':" -ForegroundColor Yellow
Write-Host "  - AI Foundry connections (aoai-connection, $SearchConnectionName)"
Write-Host "  - AI Foundry Project:  $AIFoundryProject"
Write-Host "  - AI Foundry Hub:      $AIFoundryHub"
Write-Host "  - Azure AI Language:   $LanguageAccount"
Write-Host "  - Azure OpenAI:        $OpenAIAccount (+ model deployments)"
Write-Host "  - Azure AI Search:     $SearchService"
Write-Host "  - Storage Account:     $StorageAccount (+ all blob data)"
Write-Host ""
Write-Host "The Resource Group itself will NOT be deleted." -ForegroundColor Cyan
Write-Host ""

$confirm = Read-Host "Type 'yes' to confirm deletion"
if ($confirm -ne "yes") {
    Write-Host "Aborted. No resources were deleted." -ForegroundColor Green
    exit 0
}

# ---------------------------------------------------------------------------
# Step 0: Set subscription
# ---------------------------------------------------------------------------
if ($SubscriptionId -ne "") {
    Write-Host "`n[0/7] Setting subscription..." -ForegroundColor Yellow
    az account set --subscription $SubscriptionId
}

# ---------------------------------------------------------------------------
# Step 1: Delete AI Foundry connections
# ---------------------------------------------------------------------------
Write-Host "`n[1/7] Deleting AI Foundry connections..." -ForegroundColor Yellow

Write-Host "  Deleting OpenAI connection: $OpenAIConnectionName..." -ForegroundColor Yellow
try {
    az ml connection delete `
        --name $OpenAIConnectionName `
        --resource-group $ResourceGroup `
        --workspace-name $AIFoundryProject `
        --yes `
        -o none
    Write-Host "  -> Deleted." -ForegroundColor Green
} catch {
    Write-Host "  -> Skipped (not found or already deleted)." -ForegroundColor DarkYellow
}

Write-Host "  Deleting Search connection: $SearchConnectionName..." -ForegroundColor Yellow
try {
    az ml connection delete `
        --name $SearchConnectionName `
        --resource-group $ResourceGroup `
        --workspace-name $AIFoundryProject `
        --yes `
        -o none
    Write-Host "  -> Deleted." -ForegroundColor Green
} catch {
    Write-Host "  -> Skipped (not found or already deleted)." -ForegroundColor DarkYellow
}

# ---------------------------------------------------------------------------
# Step 2: Delete AI Foundry Project
# ---------------------------------------------------------------------------
Write-Host "`n[2/7] Deleting AI Foundry Project: $AIFoundryProject..." -ForegroundColor Yellow
try {
    az ml workspace delete `
        --name $AIFoundryProject `
        --resource-group $ResourceGroup `
        --yes `
        --no-wait `
        -o none
    Write-Host "  -> Delete initiated." -ForegroundColor Green
} catch {
    Write-Host "  -> Skipped (not found or already deleted)." -ForegroundColor DarkYellow
}

# ---------------------------------------------------------------------------
# Step 3: Delete AI Foundry Hub
# ---------------------------------------------------------------------------
Write-Host "`n[3/7] Deleting AI Foundry Hub: $AIFoundryHub..." -ForegroundColor Yellow
Write-Host "  Waiting for project deletion to propagate..." -ForegroundColor Gray
Start-Sleep -Seconds 30
try {
    az ml workspace delete `
        --name $AIFoundryHub `
        --resource-group $ResourceGroup `
        --yes `
        --permanently-delete `
        --all-resources `
        -o none
    Write-Host "  -> Deleted." -ForegroundColor Green
} catch {
    Write-Host "  -> Skipped (not found or already deleted). You may need to purge manually." -ForegroundColor DarkYellow
}

# ---------------------------------------------------------------------------
# Step 4: Delete Azure AI Language
# ---------------------------------------------------------------------------
Write-Host "`n[4/7] Deleting Azure AI Language: $LanguageAccount..." -ForegroundColor Yellow
try {
    az cognitiveservices account delete `
        --name $LanguageAccount `
        --resource-group $ResourceGroup `
        -o none
    Write-Host "  -> Deleted." -ForegroundColor Green
} catch {
    Write-Host "  -> Skipped delete (not found or already deleted)." -ForegroundColor DarkYellow
}

Write-Host "  Purging soft-deleted resource..." -ForegroundColor Yellow
try {
    az cognitiveservices account purge `
        --name $LanguageAccount `
        --resource-group $ResourceGroup `
        --location "canadacentral" `
        -o none
    Write-Host "  -> Purged." -ForegroundColor Green
} catch {
    Write-Host "  -> Purge skipped (nothing to purge or already purged)." -ForegroundColor DarkYellow
}

# ---------------------------------------------------------------------------
# Step 5: Delete Azure OpenAI (deployments are deleted with the account)
# ---------------------------------------------------------------------------
Write-Host "`n[5/7] Deleting Azure OpenAI: $OpenAIAccount..." -ForegroundColor Yellow
try {
    az cognitiveservices account delete `
        --name $OpenAIAccount `
        --resource-group $ResourceGroup `
        -o none
    Write-Host "  -> Deleted." -ForegroundColor Green
} catch {
    Write-Host "  -> Skipped delete (not found or already deleted)." -ForegroundColor DarkYellow
}

Write-Host "  Purging soft-deleted resource..." -ForegroundColor Yellow
try {
    az cognitiveservices account purge `
        --name $OpenAIAccount `
        --resource-group $ResourceGroup `
        --location "eastus2" `
        -o none
    Write-Host "  -> Purged." -ForegroundColor Green
} catch {
    Write-Host "  -> Purge skipped (nothing to purge or already purged)." -ForegroundColor DarkYellow
}

# ---------------------------------------------------------------------------
# Step 6: Delete Azure AI Search
# ---------------------------------------------------------------------------
Write-Host "`n[6/7] Deleting Azure AI Search: $SearchService..." -ForegroundColor Yellow
try {
    az search service delete `
        --name $SearchService `
        --resource-group $ResourceGroup `
        --yes `
        -o none
    Write-Host "  -> Deleted." -ForegroundColor Green
} catch {
    Write-Host "  -> Skipped (not found or already deleted)." -ForegroundColor DarkYellow
}

# ---------------------------------------------------------------------------
# Step 7: Delete Storage Account (removes all containers + data)
# ---------------------------------------------------------------------------
Write-Host "`n[7/7] Deleting Storage Account: $StorageAccount..." -ForegroundColor Yellow
try {
    az storage account delete `
        --name $StorageAccount `
        --resource-group $ResourceGroup `
        --yes `
        -o none
    Write-Host "  -> Deleted." -ForegroundColor Green
} catch {
    Write-Host "  -> Skipped (not found or already deleted)." -ForegroundColor DarkYellow
}

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host " Teardown Complete!" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "All POC resources have been deleted." -ForegroundColor Green
Write-Host "Resource Group '$ResourceGroup' was kept." -ForegroundColor Cyan
Write-Host ""
Write-Host "Note: If any Cognitive Services resources are soft-deleted," -ForegroundColor Yellow
Write-Host "the script attempted to purge them. To verify, run:" -ForegroundColor Yellow
Write-Host "  az cognitiveservices account list-deleted -o table" -ForegroundColor White
Write-Host ""
