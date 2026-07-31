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

    # Embeddings. "openai" is far better at separating conversations inside one project:
    # measured on this project's data, asking about a fact stated in another conversation
    # ranked the answer 4th of 41 with the local 384-dimension model - below unrelated
    # chunks - and 1st of 106 with text-embedding-3-small. "local" keeps everything
    # in-process and free, and is the automatic fallback when the API is unavailable.
    embedding_provider: str = "openai"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_cache_dir: str = ""

    # Graph refresh
    reindex_message_threshold: int = 3
    # A conversation whose tail is below the threshold is flushed once it goes quiet, so the
    # last thing said is searchable without embedding on every single message.
    reindex_idle_flush_seconds: int = 25
    # Each conversation proposes only its closest few peers. Links mirror onto the peer
    # as well, so real node degree lands a little above this.
    sibling_top_k: int = 3

    # Debug search endpoint: returns snippets across a whole project from a
    # client-supplied project_id, so it stays off unless explicitly enabled.
    enable_retrieval_debug_api: bool = False

    # Retrieval budget
    # One search plus four reads. Enforced in the agent's tools, which refuse further calls
    # and let the model answer, rather than by a request limit that aborts the whole run.
    retrieval_max_tool_calls: int = 5
    retrieval_max_conversations: int = 5
    retrieval_max_injected_tokens: int = 4000
    # Per-hit ceiling so one long window cannot consume the whole token budget. Generous on
    # purpose: the budget above is what actually limits the total.
    retrieval_snippet_chars: int = 1200
    # Floor a search hit must clear before the UI claims the conversation was consulted.
    # 0.0 drops only genuine noise (stale vector widths score exactly 0.0, and graph
    # expansion can weight a hit below that). A real relevance cut-off is model-specific,
    # so raise this from measured data rather than by guessing.
    retrieval_consulted_min_score: float = 0.0

    # API root path (useful for tests and deployments). Leave empty string for no prefix.
    api_root: str = ""

    # Comma-separated browser origins allowed to call this service. An explicit list is
    # required rather than "*": with allow_credentials the wildcard is rejected by the
    # browser, so cookie/authorization requests would fail once auth exists.
    cors_allowed_origins: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "https://main.d3f2b6kjsfplgr.amplifyapp.com"
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]

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
