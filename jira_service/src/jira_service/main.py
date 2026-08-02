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
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(jira_router)


# Both paths. The load balancer forwards /jira/* here without stripping the prefix, so a bare
# /health is only reachable from inside the VPC - which is how the target-group check sees it -
# while a deploy smoke check or a monitor coming through the load balancer can only reach
# /jira/health. Without this, /jira/health returned 404 and nothing outside the VPC could tell
# whether the service was up.
@app.get("/jira/health")
@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "jira-service"}
