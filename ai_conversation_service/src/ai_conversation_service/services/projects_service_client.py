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

    async def push_sibling_scores(
        self, node_id: str, scores: Dict[str, int], source: str = "embedding"
    ) -> bool:
        """Send freshly computed sibling scores for a node; safe to retry."""
        if not self.base_url or not node_id:
            return False

        url = f"{self.base_url}/context-tree/nodes/{node_id}/sibling-scores"
        payload = {
            "scores": [
                {"sibling_id": sibling_id, "correlation_score": score}
                for sibling_id, score in scores.items()
            ],
            "source": source,
        }
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(10.0)) as client:
                response = await client.put(url, json=payload)
            if response.status_code != 200:
                self._logger.error(
                    f"Sibling score push for node {node_id} returned "
                    f"{response.status_code}"
                )
                return False
            return True
        except Exception as exc:
            self._logger.error(
                f"Could not push sibling scores for node {node_id}: "
                f"{type(exc).__name__}"
            )
            return False

    async def get_sibling_node_ids(self, node_id: str) -> List[str]:
        """Node ids linked to the given node, used for 1-hop graph expansion."""
        if not self.base_url or not node_id:
            return []

        url = f"{self.base_url}/context-tree/nodes/{node_id}"
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
                response = await client.get(url)
            if response.status_code != 200:
                return []
            links = (response.json() or {}).get("sibling_links") or []
            return [str(link["sibling_id"]) for link in links if link.get("sibling_id")]
        except Exception as exc:
            self._logger.debug(
                f"Could not read sibling links for node {node_id}: {type(exc).__name__}"
            )
            return []

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
