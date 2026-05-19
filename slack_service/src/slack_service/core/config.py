from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PAMI Slack Service"
    app_version: str = "0.1.0"
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    mongodb_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
