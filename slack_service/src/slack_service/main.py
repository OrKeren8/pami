from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from slack_service.api.v1.slack import router as slack_router
from slack_service.core.config import settings


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    root_path="/slack",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(slack_router)


@app.get("/health")
def health_check():
    return {"status": "healthy"}
