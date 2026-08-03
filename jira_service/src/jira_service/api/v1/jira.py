from fastapi import APIRouter

from jira_service.schemas.jira_schemas import AddCommentRequest, CreateIssueRequest
from jira_service.services.jira_api_service import jira_api_service

router = APIRouter(prefix="/jira", tags=["jira"])


@router.post("/connection-check")
def test_jira_connection():
    return jira_api_service.test_connection()


@router.get("/list-projects")
def list_projects():
    return jira_api_service.list_projects()


@router.get("/projects/{project_key}/users")
def list_assignable_users(project_key: str):
    """Who can be assigned work on this project."""
    return jira_api_service.list_assignable_users(project_key)


@router.get("/projects/{project_key}/issue-types")
def list_issue_types(project_key: str):
    """The issue types this project offers, rather than a guessed fixed list."""
    return jira_api_service.list_issue_types(project_key)


@router.get("/projects/{project_key}/issues")
def list_recent_issues(project_key: str, limit: int = 20):
    """Recently updated issues, so an existing issue can be picked instead of typed."""
    return jira_api_service.list_recent_issues(project_key, limit)


@router.post("/issues")
def create_issue(request: CreateIssueRequest):
    return jira_api_service.create_issue(request)


@router.get("/issues/{issue_key}")
def get_issue(issue_key: str):
    return jira_api_service.get_issue(issue_key)


@router.get("/issues/{issue_key}/comments")
def list_comments(issue_key: str):
    return jira_api_service.list_comments(issue_key)


@router.post("/issues/{issue_key}/comments")
def add_comment(issue_key: str, request: AddCommentRequest):
    return jira_api_service.add_comment(issue_key, request.body)
