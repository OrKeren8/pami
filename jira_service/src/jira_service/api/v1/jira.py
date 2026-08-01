from fastapi import APIRouter

from jira_service.schemas.jira_schemas import CreateIssueRequest
from jira_service.services.jira_api_service import jira_api_service

router = APIRouter(prefix="/jira", tags=["jira"])


@router.post("/connection-check")
def test_jira_connection():
    return jira_api_service.test_connection()


@router.get("/list-projects")
def list_projects():
    return jira_api_service.list_projects()


@router.post("/issues")
def create_issue(request: CreateIssueRequest):
    return jira_api_service.create_issue(request)