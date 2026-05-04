from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Azure Storage
    azure_storage_connection_string: str = ""
    azure_storage_account_name: str = ""
    blob_container_uploads: str = "hubspot-uploads"
    blob_container_docs: str = "generated-docs"

    # Azure AI Search (used for indexing chunks)
    azure_search_endpoint: str = ""
    azure_search_admin_key: str = ""
    azure_search_index_name: str = "proposal-chunks"

    # Azure AI Language (Text Analytics -- enrichment during indexing)
    azure_language_endpoint: str = ""
    azure_language_key: str = ""

    # Azure OpenAI (embeddings + used by search vectorizer)
    azure_openai_endpoint: str = ""
    azure_openai_key: str = ""
    azure_openai_embedding_deployment: str = "text-embedding-3-small"
    azure_openai_chat_deployment: str = "gpt-4o"

    # Azure AI Foundry -- all agents (section + tone) run here
    azure_ai_project_connection_string: str = ""
    azure_ai_search_connection_name: str = "search-connection"
    azure_ai_model_deployment: str = "gpt-4o"
    azure_ai_polish_model_deployment: str = "gpt-4o"

    # App
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
