from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from slack_service.api.v1.slack import router as slack_router
from slack_service.core.config import settings

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(slack_router)


# Both paths: the ALB forwards /slack/* here without stripping the prefix, so a bare /health
# is only reachable from inside the VPC (which is how the target-group check sees it) while
# anything outside can only reach /slack/health.
@app.get("/slack/health")
@app.get("/health")
def health_check():
    return {"status": "healthy"}