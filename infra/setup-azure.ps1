# =============================================================================
# Azure Infrastructure Setup for Proposal Generator POC
# =============================================================================
# Prerequisites: Azure CLI installed and logged in (run: az login)
# Usage: .\setup-azure.ps1 -Location "canadacentral" -SubscriptionId "your-sub-id"
#
# Create the resource group first if it does not exist:
#   az group create --name rg-proposal-poc --location canadacentral
#
# Replace default resource names with *globally unique* values in your subscription
# (storage account, search, OpenAI, etc. names must be unique across Azure).
# =============================================================================

param(
    [string]$Location = "canadacentral",
    [string]$SubscriptionId = "",
    [string]$ResourceGroup = "rg-proposal-poc",
    [string]$StorageAccount = "stproposalpoc",           # must be globally unique, lowercase, no hyphens
    [string]$SearchService = "search-proposal-poc",       # must be globally unique
    [string]$OpenAIAccount = "oai-proposal-poc",          # must be globally unique
    [string]$LanguageAccount = "lang-proposal-poc",       # must be globally unique
    [string]$AIFoundryHub = "hub-proposal-poc",
    [string]$AIFoundryProject = "proj-proposal-poc",
    [string]$SearchConnectionName = "search-connection"
)

$ErrorActionPreference = "Stop"

# Auto-detect subscription ID if not provided
if ($SubscriptionId -eq "") {
    $SubscriptionId = (az account show --query "id" -o tsv)
    Write-Host "Auto-detected Subscription ID: $SubscriptionId" -ForegroundColor Gray
}

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Proposal Generator POC - Azure Setup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# ---------------------------------------------------------------------------
# Step 0: Set subscription
# ---------------------------------------------------------------------------
if ($SubscriptionId -ne "") {
    Write-Host "`n[0/9] Setting subscription to $SubscriptionId..." -ForegroundColor Yellow
    az account set --subscription $SubscriptionId
}
Write-Host "[0/9] Current subscription:" -ForegroundColor Yellow
az account show --query "{Name:name, Id:id}" -o table

# ---------------------------------------------------------------------------
# Step 1: Resource Group (using existing)
# ---------------------------------------------------------------------------
Write-Host "`n[1/9] Using existing Resource Group: $ResourceGroup" -ForegroundColor Yellow
Write-Host "  -> Skipping creation." -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 2: Storage Account + Blob Container
# ---------------------------------------------------------------------------
Write-Host "`n[2/9] Creating Storage Account: $StorageAccount..." -ForegroundColor Yellow
az storage account create `
    --name $StorageAccount `
    --resource-group $ResourceGroup `
    --location $Location `
    --sku Standard_LRS `
    --kind StorageV2 `
    -o none

Write-Host "  Creating blob container: hubspot-uploads..." -ForegroundColor Yellow
$storageKey = (az storage account keys list --account-name $StorageAccount --resource-group $ResourceGroup --query "[0].value" -o tsv)
az storage container create `
    --name "hubspot-uploads" `
    --account-name $StorageAccount `
    --account-key $storageKey `
    -o none

Write-Host "  Creating blob container: generated-docs..." -ForegroundColor Yellow
az storage container create `
    --name "generated-docs" `
    --account-name $StorageAccount `
    --account-key $storageKey `
    -o none

$storageConnStr = (az storage account show-connection-string --name $StorageAccount --resource-group $ResourceGroup --query "connectionString" -o tsv)
Write-Host "  -> Done. Connection string saved." -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 3: Azure AI Search (Basic tier)
# ---------------------------------------------------------------------------
Write-Host "`n[3/9] Creating Azure AI Search: $SearchService (Basic tier)..." -ForegroundColor Yellow
az search service create `
    --name $SearchService `
    --resource-group $ResourceGroup `
    --location $Location `
    --sku basic `
    -o none

$searchAdminKey = (az search admin-key show --service-name $SearchService --resource-group $ResourceGroup --query "primaryKey" -o tsv)
$searchEndpoint = "https://$SearchService.search.windows.net"
Write-Host "  -> Done. Endpoint: $searchEndpoint" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 4: Azure OpenAI
# ---------------------------------------------------------------------------
Write-Host "`n[4/9] Creating Azure OpenAI account: $OpenAIAccount (in eastus2 for model availability)..." -ForegroundColor Yellow
az cognitiveservices account create `
    --name $OpenAIAccount `
    --resource-group $ResourceGroup `
    --location "eastus2" `
    --kind OpenAI `
    --sku S0 `
    --custom-domain $OpenAIAccount `
    -o none

Write-Host "  Deploying gpt-4o model..." -ForegroundColor Yellow
az cognitiveservices account deployment create `
    --name $OpenAIAccount `
    --resource-group $ResourceGroup `
    --deployment-name "gpt-4o" `
    --model-name "gpt-4o" `
    --model-version "2024-11-20" `
    --model-format OpenAI `
    --sku-name "GlobalStandard" `
    --sku-capacity 30 `
    -o none

Write-Host "  Deploying text-embedding-3-small model..." -ForegroundColor Yellow
az cognitiveservices account deployment create `
    --name $OpenAIAccount `
    --resource-group $ResourceGroup `
    --deployment-name "text-embedding-3-small" `
    --model-name "text-embedding-3-small" `
    --model-version "1" `
    --model-format OpenAI `
    --sku-name "Standard" `
    --sku-capacity 30 `
    -o none

$openaiEndpoint = (az cognitiveservices account show --name $OpenAIAccount --resource-group $ResourceGroup --query "properties.endpoint" -o tsv)
$openaiKey = (az cognitiveservices account keys list --name $OpenAIAccount --resource-group $ResourceGroup --query "key1" -o tsv)
Write-Host "  -> Done. Endpoint: $openaiEndpoint" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 5: Azure AI Language (Text Analytics for enrichment)
# ---------------------------------------------------------------------------
Write-Host "`n[5/9] Creating Azure AI Language: $LanguageAccount..." -ForegroundColor Yellow
az cognitiveservices account create `
    --name $LanguageAccount `
    --resource-group $ResourceGroup `
    --location $Location `
    --kind TextAnalytics `
    --sku S `
    --custom-domain $LanguageAccount `
    -o none

$languageEndpoint = (az cognitiveservices account show --name $LanguageAccount --resource-group $ResourceGroup --query "properties.endpoint" -o tsv)
$languageKey = (az cognitiveservices account keys list --name $LanguageAccount --resource-group $ResourceGroup --query "key1" -o tsv)
Write-Host "  -> Done. Endpoint: $languageEndpoint" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 6: Azure AI Foundry Hub + Project
# ---------------------------------------------------------------------------
Write-Host "`n[6/9] Creating AI Foundry Hub: $AIFoundryHub (in canadaeast for Agent Service support)..." -ForegroundColor Yellow
az ml workspace create `
    --name $AIFoundryHub `
    --resource-group $ResourceGroup `
    --location "canadaeast" `
    --kind hub `
    -o none

Write-Host "  Creating AI Foundry Project: $AIFoundryProject..." -ForegroundColor Yellow
$hubId = (az ml workspace show --name $AIFoundryHub --resource-group $ResourceGroup --query "id" -o tsv)
az ml workspace create `
    --name $AIFoundryProject `
    --resource-group $ResourceGroup `
    --location "canadaeast" `
    --kind project `
    --hub-id $hubId `
    -o none

Write-Host "  -> Done." -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 7: Connect OpenAI to AI Foundry
# ---------------------------------------------------------------------------
Write-Host "`n[7/9] Creating OpenAI connection in AI Foundry project..." -ForegroundColor Yellow

$aoaiConnYaml = @"
name: aoai-connection
type: azure_open_ai
azure_endpoint: $openaiEndpoint
api_key: $openaiKey
"@
$aoaiConnYaml | Out-File -FilePath ".\aoai-conn.yml" -Encoding utf8
az ml connection create `
    --resource-group $ResourceGroup `
    --workspace-name $AIFoundryProject `
    --file ".\aoai-conn.yml" `
    -o none
Remove-Item ".\aoai-conn.yml"
Write-Host "  -> Done." -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 8: Connect AI Search to AI Foundry (for agent RAG)
# ---------------------------------------------------------------------------
Write-Host "`n[8/9] Creating AI Search connection in AI Foundry project..." -ForegroundColor Yellow

$searchConnYaml = @"
name: $SearchConnectionName
type: azure_ai_search
endpoint: $searchEndpoint
api_key: $searchAdminKey
"@
$searchConnYaml | Out-File -FilePath ".\search-conn.yml" -Encoding utf8
az ml connection create `
    --resource-group $ResourceGroup `
    --workspace-name $AIFoundryProject `
    --file ".\search-conn.yml" `
    -o none
Remove-Item ".\search-conn.yml"
Write-Host "  -> Done. Connection name: $SearchConnectionName" -ForegroundColor Green

# ---------------------------------------------------------------------------
# Step 9: Build connection string + write .env
# ---------------------------------------------------------------------------
Write-Host "`n[9/9] Writing .env file..." -ForegroundColor Yellow

# AI Foundry project connection string: <endpoint>;<subscription>;<rg>;<project>
$projectEndpoint = (az ml workspace show --name $AIFoundryProject --resource-group $ResourceGroup --query "discovery_url" -o tsv)
# Extract the host from discovery_url (e.g. https://canadacentral.api.azureml.ms/...)
# The SDK expects just the hostname without the https:// prefix
if ($projectEndpoint -match "^https://([^/]+)") {
    $hostUrl = $Matches[1]
}
else {
    $hostUrl = $projectEndpoint
}
$projectConnStr = "$hostUrl;$SubscriptionId;$ResourceGroup;$AIFoundryProject"

$envContent = @"
# Azure Storage
AZURE_STORAGE_CONNECTION_STRING=$storageConnStr
AZURE_STORAGE_ACCOUNT_NAME=$StorageAccount
BLOB_CONTAINER_UPLOADS=hubspot-uploads
BLOB_CONTAINER_DOCS=generated-docs

# Azure AI Search (used for indexing chunks)
AZURE_SEARCH_ENDPOINT=$searchEndpoint
AZURE_SEARCH_ADMIN_KEY=$searchAdminKey
AZURE_SEARCH_INDEX_NAME=proposal-chunks

# Azure AI Language (Text Analytics -- enrichment during indexing)
AZURE_LANGUAGE_ENDPOINT=$languageEndpoint
AZURE_LANGUAGE_KEY=$languageKey

# Azure OpenAI (embeddings + used by search vectorizer)
AZURE_OPENAI_ENDPOINT=$openaiEndpoint
AZURE_OPENAI_KEY=$openaiKey
AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small

# Azure AI Foundry (all agents run here -- section generation + tone adjustment)
AZURE_AI_PROJECT_CONNECTION_STRING=$projectConnStr
AZURE_AI_SEARCH_CONNECTION_NAME=$SearchConnectionName
AZURE_AI_MODEL_DEPLOYMENT=gpt-4o

# App
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
"@

$envContent | Out-File -FilePath "..\backend\.env" -Encoding utf8
Write-Host "  -> .env written to backend\.env" -ForegroundColor Green

Write-Host "`n============================================" -ForegroundColor Cyan
Write-Host " Setup Complete!" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Resources created:" -ForegroundColor White
Write-Host "  Resource Group:    $ResourceGroup"
Write-Host "  Storage Account:   $StorageAccount (containers: hubspot-uploads, generated-docs)"
Write-Host "  AI Search:         $SearchService ($searchEndpoint)"
Write-Host "  OpenAI:            $OpenAIAccount (models: gpt-4o, text-embedding-3-small)"
Write-Host "  AI Language:       $LanguageAccount ($languageEndpoint)"
Write-Host "  AI Foundry Hub:    $AIFoundryHub"
Write-Host "  AI Foundry Project:$AIFoundryProject"
Write-Host "  Search Connection: $SearchConnectionName (in Foundry)"
Write-Host ""
Write-Host "AI agents are created dynamically at runtime (per session)." -ForegroundColor White
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. az login   (make sure you're logged in for DefaultAzureCredential)"
Write-Host "  2. cd ..\backend && pip install -r requirements.txt"
Write-Host "  3. uvicorn app.main:app --reload"
Write-Host "  4. cd ..\frontend && npm install && npm run dev"
