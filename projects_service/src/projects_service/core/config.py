from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    mongodb_url: str = "mongodb://localhost:27017"
    database_name: str = "pami"
    service_name: str = "projects-service"
    debug: bool = True
    log_level: str = "INFO"
    ai_service_url: str = "http://localhost:8001"  # AI conversation service URL

    class Config:
        env_file = ".env"


settings = Settings()
