from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from jira_service.api.v1.jira import router as jira_router
from jira_service.core.config import settings


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://main.d7y709mdw2yii.amplifyapp.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jira_router)


@app.get("/health")
def health_check():
    return {"status": "healthy"}