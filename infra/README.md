# Azure Infrastructure Setup -- Step-by-Step Guide

## Prerequisites

1. **Azure CLI** installed ([Install guide](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli-windows))
2. **Azure ML CLI extension** (for AI Foundry):
   ```powershell
   az extension add --name ml
   ```
3. **Azure subscription** with permissions to create resources
4. **Python 3.10+** (for the backend, which creates Foundry agents at runtime)

## How Agents Work in This Architecture

Unlike a simple OpenAI wrapper, this POC creates **real agents in Azure AI Foundry** at runtime:

```
Upload JSON --> Blob Storage --> AI Search Index (chunked, tagged with session_id)
                                        |
Generate Section --> Create Foundry Agent (with AzureAISearchTool filtered to session_id)
                         |
                    Agent runs: searches index natively, generates content
                         |
                    Response returned via thread --> Agent cleaned up
```

Each agent is registered in AI Foundry with an `AzureAISearchTool` whose OData filter is set to `session_id eq '<id>'`. This ensures **native RAG isolation per upload** -- agents can only see data from their own session.

---

## Option A: Run the Script (Recommended)

```powershell
# 1. Open PowerShell and log in to Azure
az login

# 2. Navigate to the infra folder
cd infra

# 3. Run the setup script (adjust params as needed)
.\setup-azure.ps1 `
    -Location "canadacentral" `
    -SubscriptionId "YOUR_SUBSCRIPTION_ID" `
    -StorageAccount "stproposalpoc123"   # must be globally unique
```

The script creates all resources, sets up connections in AI Foundry, and writes a `.env` file to `backend/.env` automatically.

---

## Option B: Manual Step-by-Step

### Step 1: Login and Set Subscription

```powershell
az login
az account set --subscription "YOUR_SUBSCRIPTION_ID"
```

### Step 2: Create Resource Group

```powershell
az group create --name rg-proposal-poc --location canadacentral
```

### Step 3: Create Storage Account + Containers

```powershell
az storage account create `
    --name stproposalpoc `
    --resource-group rg-proposal-poc `
    --location canadacentral `
    --sku Standard_LRS `
    --kind StorageV2

$key = (az storage account keys list --account-name stproposalpoc --resource-group rg-proposal-poc --query "[0].value" -o tsv)

az storage container create --name hubspot-uploads --account-name stproposalpoc --account-key $key
az storage container create --name generated-docs --account-name stproposalpoc --account-key $key

# Save the connection string for .env
az storage account show-connection-string --name stproposalpoc --resource-group rg-proposal-poc --query "connectionString" -o tsv
```

### Step 4: Create Azure AI Search

```powershell
az search service create `
    --name search-proposal-poc `
    --resource-group rg-proposal-poc `
    --location canadacentral `
    --sku basic

# Save the admin key for .env
az search admin-key show --service-name search-proposal-poc --resource-group rg-proposal-poc --query "primaryKey" -o tsv
```

Endpoint: `https://search-proposal-poc.search.windows.net`

### Step 5: Create Azure OpenAI + Deploy Model

```powershell
az cognitiveservices account create `
    --name oai-proposal-poc `
    --resource-group rg-proposal-poc `
    --location canadacentral `
    --kind OpenAI `
    --sku S0 `
    --custom-domain oai-proposal-poc

az cognitiveservices account deployment create `
    --name oai-proposal-poc `
    --resource-group rg-proposal-poc `
    --deployment-name gpt-4o `
    --model-name gpt-4o `
    --model-version "2024-11-20" `
    --model-format OpenAI `
    --sku-name Standard `
    --sku-capacity 30

# Save endpoint and key for .env
az cognitiveservices account show --name oai-proposal-poc --resource-group rg-proposal-poc --query "properties.endpoint" -o tsv
az cognitiveservices account keys list --name oai-proposal-poc --resource-group rg-proposal-poc --query "key1" -o tsv
```

### Step 6: Create Azure AI Language (Text Analytics)

This resource powers the enrichment pipeline -- key phrase extraction, entity recognition, and sentiment analysis during indexing.

```powershell
az cognitiveservices account create `
    --name lang-proposal-poc `
    --resource-group rg-proposal-poc `
    --location canadacentral `
    --kind TextAnalytics `
    --sku S `
    --custom-domain lang-proposal-poc

# Save endpoint and key for .env
az cognitiveservices account show --name lang-proposal-poc --resource-group rg-proposal-poc --query "properties.endpoint" -o tsv
az cognitiveservices account keys list --name lang-proposal-poc --resource-group rg-proposal-poc --query "key1" -o tsv
```

### Step 7: Create AI Foundry Hub + Project

```powershell
az extension add --name ml

az ml workspace create `
    --name hub-proposal-poc `
    --resource-group rg-proposal-poc `
    --location canadacentral `
    --kind hub

$hubId = (az ml workspace show --name hub-proposal-poc --resource-group rg-proposal-poc --query "id" -o tsv)

az ml workspace create `
    --name proj-proposal-poc `
    --resource-group rg-proposal-poc `
    --location canadacentral `
    --kind project `
    --hub-id $hubId
```

### Step 8: Create OpenAI Connection in AI Foundry

Create a file `aoai-conn.yml`:
```yaml
name: aoai-connection
type: azure_open_ai
url: <your-openai-endpoint>
api_key: <your-openai-key>
```

```powershell
az ml connection create `
    --resource-group rg-proposal-poc `
    --workspace-name proj-proposal-poc `
    --file aoai-conn.yml
```

### Step 9: Create AI Search Connection in AI Foundry

**This is critical** -- it allows the Foundry agents to natively query your search index for RAG.

Create a file `search-conn.yml`:
```yaml
name: search-connection
type: azure_ai_search
url: https://search-proposal-poc.search.windows.net
api_key: <your-search-admin-key>
```

```powershell
az ml connection create `
    --resource-group rg-proposal-poc `
    --workspace-name proj-proposal-poc `
    --file search-conn.yml
```

You can verify the connection was created:
```powershell
az ml connection list --resource-group rg-proposal-poc --workspace-name proj-proposal-poc -o table
```

You should see both `aoai-connection` and `search-connection` listed.

### Step 10: Get the Project Connection String

The backend uses `AIProjectClient.from_connection_string()` which needs a connection string in the format: `<endpoint>;<subscription_id>;<resource_group>;<project_name>`

```powershell
# Get the discovery URL to extract the endpoint
$discoveryUrl = (az ml workspace show --name proj-proposal-poc --resource-group rg-proposal-poc --query "discovery_url" -o tsv)
Write-Host "Discovery URL: $discoveryUrl"

# The endpoint is the host portion, e.g. https://canadacentral.api.azureml.ms
# Your connection string will be:
# https://canadacentral.api.azureml.ms;YOUR_SUB_ID;rg-proposal-poc;proj-proposal-poc
```

### Step 11: Create the `.env` File

Create `backend/.env` with all the values you collected:

```env
# Azure Storage
AZURE_STORAGE_CONNECTION_STRING=<from step 3>
AZURE_STORAGE_ACCOUNT_NAME=stproposalpoc
BLOB_CONTAINER_UPLOADS=hubspot-uploads
BLOB_CONTAINER_DOCS=generated-docs

# Azure AI Search (used for indexing chunks)
AZURE_SEARCH_ENDPOINT=https://search-proposal-poc.search.windows.net
AZURE_SEARCH_ADMIN_KEY=<from step 4>
AZURE_SEARCH_INDEX_NAME=proposal-chunks

# Azure AI Language (Text Analytics -- enrichment during indexing)
AZURE_LANGUAGE_ENDPOINT=<from step 6>
AZURE_LANGUAGE_KEY=<from step 6>

# Azure AI Foundry (all agents run here -- section generation + tone adjustment)
AZURE_AI_PROJECT_CONNECTION_STRING=<from step 10>
AZURE_AI_SEARCH_CONNECTION_NAME=search-connection
AZURE_AI_MODEL_DEPLOYMENT=gpt-4o

# App
CORS_ORIGINS=http://localhost:5173,http://localhost:3000
```

### Important: Authentication for Foundry Agents

The backend uses `DefaultAzureCredential` to authenticate with AI Foundry. Make sure you are logged in:

```powershell
az login
```

The account you log in with must have **Cognitive Services OpenAI Contributor** role on the OpenAI resource and **Contributor** on the AI Foundry project. To assign these:

```powershell
# Get your user object ID
$userId = (az ad signed-in-user show --query id -o tsv)

# Assign role on the OpenAI resource
$openaiId = (az cognitiveservices account show --name oai-proposal-poc --resource-group rg-proposal-poc --query id -o tsv)
az role assignment create --assignee $userId --role "Cognitive Services OpenAI Contributor" --scope $openaiId

# Assign role on the AI Foundry project
$projectId = (az ml workspace show --name proj-proposal-poc --resource-group rg-proposal-poc --query id -o tsv)
az role assignment create --assignee $userId --role "Contributor" --scope $projectId
```

---

## Teardown

To delete all resources when done with the POC:

```powershell
az group delete --name rg-proposal-poc --yes --no-wait
```

This deletes the resource group and everything inside it.
