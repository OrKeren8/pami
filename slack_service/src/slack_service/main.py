from fastapi import FastAPI

from slack_service.api.v1.slack import router as slack_router
from slack_service.core.config import settings


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.include_router(slack_router)


@app.get("/health")
def health_check():
    return {"status": "healthy"}