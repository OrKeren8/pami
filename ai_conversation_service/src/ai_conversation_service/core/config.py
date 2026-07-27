from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "ai-conversation-service"
    debug: bool = True
    log_level: str = "INFO"

    # OpenAI Configuration
    openai_api_key: str = ""
    openai_model: str = "gpt-4.1-mini"  # Academic/research model provided by professor
    openai_organization: str = ""  # Optional: Organization ID for multi-org accounts
    openai_project: str = ""  # Optional: Project ID for project-specific usage

    # AWS Configuration for S3 storage
    # Leave empty to use ECS task IAM role (recommended for production)
    # Only set these for local development with AWS Learner Lab credentials
    aws_region: str = "us-east-1"
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_session_token: str = ""
    aws_s3_bucket_name: str = ""

    # Projects service integration
    # Example: http://localhost:8000 or https://<gateway-host>
    projects_api_url: str = ""

    # MongoDB - conversation chunk / vector index (transcripts stay in S3)
    mongodb_url: str = "mongodb://localhost:27017"
    database_name: str = "pami"

    # Embeddings - runs in-process; the OpenAI key has no embedding access
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_cache_dir: str = ""

    # Graph refresh
    reindex_message_threshold: int = 3
    sibling_top_k: int = 8

    # Debug search endpoint: returns snippets across a whole project from a
    # client-supplied project_id, so it stays off unless explicitly enabled.
    enable_retrieval_debug_api: bool = False

    # Retrieval budget
    retrieval_max_tool_calls: int = 3
    retrieval_max_conversations: int = 5
    retrieval_max_injected_tokens: int = 4000

    # API root path (useful for tests and deployments). Leave empty string for no prefix.
    api_root: str = ""

    @field_validator("debug", mode="before")
    @classmethod
    def normalize_debug(cls, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return True
        text = str(value).strip().lower()
        if text in {"1", "true", "yes", "on", "debug"}:
            return True
        if text in {"0", "false", "no", "off", "warn", "warning", "info", "error"}:
            return False
        return True

    # Configure settings: load from .env and ignore extra env vars
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
