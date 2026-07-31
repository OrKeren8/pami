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
