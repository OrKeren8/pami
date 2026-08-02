from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "PAMI Slack Service"
    app_version: str = "0.1.0"
    slack_bot_token: str = ""
    slack_signing_secret: str = ""
    mongodb_url: str = ""

    # Comma-separated. Writes from the browser preflight, so an origin missing here fails
    # with OPTIONS 400 and the request is never sent - which is how a stale Amplify URL left
    # every "send message" silently broken while reads kept working.
    cors_allowed_origins: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "https://main.d1cs950rhsdp99.amplifyapp.com"
    )

    @property
    def allowed_origins(self) -> list[str]:
        return [
            origin.strip()
            for origin in self.cors_allowed_origins.split(",")
            if origin.strip()
        ]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
