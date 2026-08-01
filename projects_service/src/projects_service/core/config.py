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

    # --- Authentication (AWS Cognito) ---
    cognito_region: str = "us-east-1"
    cognito_user_pool_id: str = ""
    cognito_client_id: str = ""
    # Off by default so this can ship before a user pool exists without taking the running
    # app offline: with it off, an unauthenticated request is treated as the local dev user
    # rather than rejected. Must be on in any real deployment.
    auth_required: bool = False
    unauthenticated_user_id: str = "local-dev-user"
    unauthenticated_user_email: str = "local@pami.dev"

    # Comma-separated. Checked against the email claim in a verified token, so it cannot be
    # spoofed by a request field. A Cognito group is the better long-term answer, but group
    # management needs IAM permissions a restricted lab account may not have.
    # Matched against the email on the verified Cognito account - orkeren8@gmail.com, with an
    # "n". It was written here with an "m", so the admin page would have refused the very
    # account it exists for.
    admin_emails: str = "orkeren8@gmail.com"
    admin_group: str = "admins"

    # Shared secret for calls from the other services, which have no user to act as. Empty
    # means "not configured": with auth_required off that still lets internal calls through,
    # so this can ship before the secret is distributed.
    service_key: str = ""

    @property
    def admin_email_list(self) -> set[str]:
        return {
            email.strip().lower()
            for email in self.admin_emails.split(",")
            if email.strip()
        }

    @field_validator("auth_required", mode="before")
    @classmethod
    def normalize_auth_required(cls, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

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
