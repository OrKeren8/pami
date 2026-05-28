from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongodb_url: str = "mongodb://localhost:27017"
    database_name: str = "pami"
    service_name: str = "projects-service"
    debug: bool = True
    log_level: str = "INFO"
    ai_service_url: str = "http://localhost:8001"  # AI conversation service URL

    # Configure settings: load from .env and ignore extra env vars
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
