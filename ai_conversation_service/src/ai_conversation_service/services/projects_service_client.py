from typing import Dict, List, Optional

import httpx
from loguru import logger


class ProjectsServiceClient:
    """HTTP client for retrieving project metadata from projects service."""

    def __init__(self, base_url: str = ""):
        self.base_url = (base_url or "").strip().rstrip("/")
        self._logger = logger.bind(service="ProjectsServiceClient")

    def _project_urls(self, project_id: str) -> List[str]:
        """Build candidate project URLs from the configured base URL."""
        if not self.base_url:
            return []

        if self.base_url.endswith("/projects"):
            return [f"{self.base_url}/{project_id}"]

        return [f"{self.base_url}/projects/{project_id}"]

    async def get_project_metadata(self, project_id: str) -> Optional[Dict[str, str]]:
        """Fetch project name and summary/goal by project id."""
        if not project_id:
            return None

        urls = self._project_urls(project_id)
        if not urls:
            self._logger.debug("PROJECTS_API_URL is not configured")
            return None

        timeout = httpx.Timeout(3.0, connect=2.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            for url in urls:
                try:
                    response = await client.get(url)
                    if response.status_code != 200:
                        continue

                    payload = response.json() if response.content else {}
                    name = payload.get("name")
                    summary = payload.get("goal") or payload.get("summary")

                    result: Dict[str, str] = {}
                    if name:
                        result["project_name"] = str(name)
                    if summary:
                        result["project_summary"] = str(summary)

                    return result or None
                except Exception as exc:
                    self._logger.debug(
                        f"Could not fetch project metadata from {url}: {exc}"
                    )

        return None
