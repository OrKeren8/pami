from __future__ import annotations

import logging
from typing import Any

import requests
from fastapi import HTTPException
from requests.auth import HTTPBasicAuth

from jira_service.core.config import settings
from jira_service.schemas.jira_schemas import CreateIssueRequest
from jira_service.services.markdown_adf import markdown_to_adf

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

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        expected_status: int | None = None,
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

    def _description_to_adf(self, description: str) -> dict[str, Any]:
        """The ticket text as a document, not as one paragraph.

        Jira stores ADF, so wrapping the whole description in a single text node published a
        ticket that read as one block of prose with the raw `##`, `-` and `**` still in it -
        however carefully it had been structured in the editor.
        """
        return markdown_to_adf(description)

    def _adf_to_text(self, document: Any) -> str:
        """Flatten Atlassian Document Format back to plain text.

        Jira returns rich documents, while the editor and the chat both work in plain text.
        Walks the tree rather than assuming the shape this service writes, because a
        description or comment edited inside Jira can contain lists, links and panels.
        """
        if not document:
            return ""
        if isinstance(document, str):
            return document

        pieces: list[str] = []
        block_types = {"paragraph", "heading", "listItem", "blockquote", "codeBlock"}
        # Written back in the notation the editor uses, so an issue read out of Jira keeps the
        # shape it was published with instead of flattening to prose on the round trip.
        markers = {"bulletList": "- ", "orderedList": "- "}

        def walk(node: Any, marker: str = "") -> None:
            if isinstance(node, list):
                for item in node:
                    walk(item, marker)
                return
            if not isinstance(node, dict):
                return

            node_type = node.get("type")
            if node_type == "text":
                text = node.get("text") or ""
                marks = {mark.get("type") for mark in node.get("marks") or []}
                if "code" in marks:
                    text = f"`{text}`"
                if "strong" in marks:
                    text = f"**{text}**"
                elif "em" in marks:
                    text = f"*{text}*"
                pieces.append(text)
            elif node_type == "hardBreak":
                pieces.append("\n")
            elif node_type == "rule":
                pieces.append("---" + "\n")
            elif node_type == "heading":
                level = (node.get("attrs") or {}).get("level") or 1
                pieces.append("#" * int(level) + " ")
            elif node_type == "listItem":
                pieces.append(marker)
            elif node_type == "taskItem":
                state = (node.get("attrs") or {}).get("state")
                pieces.append("- [x] " if state == "DONE" else "- [ ] ")

            walk(node.get("content"), markers.get(node_type, marker))

            # Block nodes end a line, so paragraphs and list items do not run together.
            if node_type in block_types or node_type == "taskItem":
                pieces.append("\n")

        walk(document.get("content"))
        return "".join(pieces).strip()

    def test_connection(self) -> dict[str, Any]:
        # Identity first: Atlassian does not reject bad credentials on /project/search, it
        # silently degrades to an anonymous caller and answers 200 with an empty list - so a
        # revoked token read as "Connected, 0 projects" instead of as the failure it is.
        # /myself is the endpoint that actually authenticates.
        self._request("GET", "/myself")

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

    def list_projects(self) -> dict[str, Any]:
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

    def create_issue(self, request: CreateIssueRequest) -> dict[str, Any]:
        fields: dict[str, Any] = {
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

        if request.assignee_account_id:
            fields["assignee"] = {"id": request.assignee_account_id}

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

    def list_assignable_users(self, project_key: str) -> dict[str, Any]:
        """People who can be assigned work on this project.

        Scoped to the project rather than the whole site: /user/search returns every account
        including app users, and assigning someone who lacks permission on the project is
        rejected at create time with an error that does not explain why.
        """
        data = self._request(
            "GET",
            "/user/assignable/search",
            params={"project": project_key, "maxResults": 50},
        )

        users = [
            {
                "account_id": user.get("accountId"),
                "display_name": user.get("displayName") or "Unknown",
                # Usually absent: Jira hides it unless the account chooses to share it.
                "email": user.get("emailAddress"),
                "active": bool(user.get("active", True)),
            }
            for user in (data or [])
            if user.get("accountType", "atlassian") == "atlassian"
        ]

        return {"ok": True, "users": users}

    def list_issue_types(self, project_key: str) -> dict[str, Any]:
        """The issue types this project actually offers.

        A fixed Story/Bug/Task list would be a guess: a team-managed project can rename or
        remove any of them, and creating an issue with a type the project does not have fails.
        Sub-task types are excluded because they need a parent this editor does not collect.
        """
        data = self._request("GET", f"/project/{project_key}")

        types = [
            {
                "id": issue_type.get("id"),
                "name": issue_type.get("name"),
            }
            for issue_type in (data or {}).get("issueTypes", [])
            if not issue_type.get("subtask")
        ]
        return {"ok": True, "issue_types": types}

    def list_recent_issues(self, project_key: str, limit: int = 20) -> dict[str, Any]:
        """The project's most recently updated issues.

        Without this the only way into an existing issue is to type its key from memory, which
        is the kind of thing nobody can do and which makes the feature look broken rather than
        merely inconvenient.

        Tries /search/jql first and falls back to /search: Atlassian is migrating Jira Cloud
        from the second to the first, and which one a site answers depends on when it was
        provisioned.
        """
        jql = f'project = "{project_key}" ORDER BY updated DESC'
        params = {
            "jql": jql,
            "maxResults": max(1, min(limit, 50)),
            "fields": "summary,status,issuetype,updated",
        }

        try:
            data = self._request("GET", "/search/jql", params=params)
        except HTTPException as error:
            if error.status_code not in (400, 404, 410):
                raise
            logger.info("Falling back to the older /search endpoint for this site")
            data = self._request("GET", "/search", params=params)

        issues = [
            {
                "key": issue.get("key"),
                "summary": (issue.get("fields") or {}).get("summary"),
                "status": ((issue.get("fields") or {}).get("status") or {}).get("name"),
                "issue_type": ((issue.get("fields") or {}).get("issuetype") or {}).get(
                    "name"
                ),
                "updated": (issue.get("fields") or {}).get("updated"),
            }
            for issue in (data or {}).get("issues", [])
        ]
        return {"ok": True, "issues": issues}

    def get_issue(self, issue_key: str) -> dict[str, Any]:
        """One issue, flattened to the fields the UI shows."""
        data = self._request(
            "GET",
            f"/issue/{issue_key}",
            params={
                "fields": (
                    "summary,description,status,assignee,issuetype,priority,duedate,labels"
                )
            },
        )
        fields = (data or {}).get("fields", {})
        key = (data or {}).get("key")

        return {
            "ok": True,
            "issue_key": key,
            "issue_url": f"{self.base_url}/browse/{key}" if key else None,
            "summary": fields.get("summary"),
            "description": self._adf_to_text(fields.get("description")),
            "status": (fields.get("status") or {}).get("name"),
            "issue_type": (fields.get("issuetype") or {}).get("name"),
            "priority": (fields.get("priority") or {}).get("name"),
            "due_date": fields.get("duedate"),
            "labels": fields.get("labels") or [],
            "assignee": (fields.get("assignee") or {}).get("displayName"),
        }

    def list_comments(self, issue_key: str) -> dict[str, Any]:
        """The comment thread on an issue, oldest first."""
        data = self._request(
            "GET",
            f"/issue/{issue_key}/comment",
            params={"maxResults": 50, "orderBy": "created"},
        )

        comments = [
            {
                "id": comment.get("id"),
                "author": (comment.get("author") or {}).get("displayName"),
                "created": comment.get("created"),
                "body": self._adf_to_text(comment.get("body")),
            }
            for comment in (data or {}).get("comments", [])
        ]
        return {"ok": True, "issue_key": issue_key, "comments": comments}

    def add_comment(self, issue_key: str, body: str) -> dict[str, Any]:
        """Post a comment. Plain text in, Atlassian Document Format out."""
        if not body.strip():
            raise HTTPException(status_code=422, detail="A comment cannot be empty")

        data = self._request(
            "POST",
            f"/issue/{issue_key}/comment",
            json={"body": self._description_to_adf(body)},
            expected_status=201,
        )
        return {
            "ok": True,
            "issue_key": issue_key,
            "comment_id": (data or {}).get("id"),
        }


jira_api_service = JiraApiService()
