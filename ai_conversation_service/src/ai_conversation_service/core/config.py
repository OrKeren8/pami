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

    # Configure settings: load from .env and ignore extra env vars
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
