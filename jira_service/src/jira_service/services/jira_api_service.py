import logging
from typing import Any, Dict, Optional

import requests
from fastapi import HTTPException
from requests.auth import HTTPBasicAuth

from jira_service.core.config import settings
from jira_service.schemas.jira_schemas import CreateIssueRequest


logger = logging.getLogger(__name__)


class JiraApiService:
    def __init__(self) -> None:
        self.base_url = settings.jira_base_url.rstrip("/")
        self.username = settings.jira_username
        self.api_token = settings.jira_api_token

    def _ensure_configured(self) -> None:
        missing = []
        if not self.base_url:
            missing.append("JIRA_BASE_URL")
        if not self.username:
            missing.append("JIRA_USERNAME")
        if not self.api_token:
            missing.append("JIRA_API_TOKEN")

        if missing:
            raise HTTPException(
                status_code=500,
                detail=f"Missing Jira environment variables: {', '.join(missing)}",
            )

    def _api_url(self, path: str) -> str:
        return f"{self.base_url}/rest/api/3{path}"

    def _auth(self) -> HTTPBasicAuth:
        return HTTPBasicAuth(self.username, self.api_token)

    def _headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        expected_status: Optional[int] = None,
    ) -> Any:
        self._ensure_configured()

        try:
            response = requests.request(
                method=method,
                url=self._api_url(path),
                params=params,
                json=json,
                auth=self._auth(),
                headers=self._headers(),
                timeout=15,
            )
        except requests.RequestException as exc:
            logger.exception("Jira request failed")
            raise HTTPException(
                status_code=502,
                detail=f"Failed to reach Jira: {exc}",
            ) from exc

        if expected_status is not None and response.status_code != expected_status:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.text,
            )

        if expected_status is None and response.status_code >= 400:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.text,
            )

        if response.status_code == 204 or not response.text:
            return None

        return response.json()

    def _description_to_adf(self, description: str) -> Dict[str, Any]:
        return {
            "type": "doc",
            "version": 1,
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": description,
                        }
                    ],
                }
            ],
        }

    def test_connection(self) -> Dict[str, Any]:
        data = self._request(
            "GET",
            "/project/search",
            params={"maxResults": 1},
        )

        return {
            "ok": True,
            "message": "Jira connection is healthy.",
            "total_projects": data.get("total", 0) if isinstance(data, dict) else 0,
        }

    def list_projects(self) -> Dict[str, Any]:
        data = self._request(
            "GET",
            "/project/search",
            params={"maxResults": 50},
        )

        values = data.get("values", []) if isinstance(data, dict) else []

        projects = [
            {
                "id": project.get("id"),
                "key": project.get("key"),
                "name": project.get("name"),
                "project_type_key": project.get("projectTypeKey"),
                "simplified": project.get("simplified"),
            }
            for project in values
        ]

        return {
            "ok": True,
            "projects": projects,
        }

    def create_issue(self, request: CreateIssueRequest) -> Dict[str, Any]:
        fields: Dict[str, Any] = {
            "project": {"key": request.project_key},
            "issuetype": {"name": request.issue_type},
            "summary": request.summary,
        }

        if request.description:
            fields["description"] = self._description_to_adf(request.description)

        if request.priority:
            fields["priority"] = {"name": request.priority}

        if request.due_date:
            fields["duedate"] = request.due_date

        if request.labels:
            fields["labels"] = request.labels

        data = self._request(
            "POST",
            "/issue",
            json={"fields": fields},
            expected_status=201,
        )

        issue_key = data.get("key") if isinstance(data, dict) else None

        return {
            "ok": True,
            "issue_key": issue_key,
            "issue_id": data.get("id") if isinstance(data, dict) else None,
            "issue_url": f"{self.base_url}/browse/{issue_key}" if issue_key else None,
        }


jira_api_service = JiraApiService()