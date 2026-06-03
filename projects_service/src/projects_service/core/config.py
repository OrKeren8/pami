from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    mongodb_url: str = "mongodb://localhost:27017"
    database_name: str = "pami"
    service_name: str = "projects-service"
    debug: bool = True
    log_level: str = "INFO"
    ai_service_url: str = "http://localhost:8001"  # AI conversation service URL

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
