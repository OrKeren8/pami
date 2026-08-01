from datetime import datetime
from uuid import uuid4
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi import HTTPException
from fastapi.testclient import TestClient

from projects_service.api.v1.context_tree import router as context_tree_router
from projects_service.dependencies import get_context_tree_service
from projects_service.core.access import node_for_member, project_for_member
from projects_service.services.context_tree_service import ContextTreeService
import projects_service.services.context_tree_service as context_tree_service_module


class InMemoryContextTreeRepository:
    def __init__(self):
        self.nodes = {}

    async def create(self, node):
        node_id = str(getattr(node, "id", "") or uuid4())
        node.id = node_id
        self.nodes[node_id] = node
        return node

    async def get_by_id(self, node_id: str):
        return self.nodes.get(str(node_id))

    async def list_by_project(self, project_id: str):
        return [
            node
            for node in self.nodes.values()
            if str(getattr(node, "project_id", "")) == str(project_id)
        ]

    async def update(self, node_id: str, update_data: dict):
        node = self.nodes.get(str(node_id))
        if not node:
            return None
        for key, val in update_data.items():
            setattr(node, key, val)
        return node

    async def delete(self, node_id: str):
        return self.nodes.pop(str(node_id), None) is not None


class FakeContextTreeNode:
    def __init__(self, **kwargs):
        self.id = kwargs.pop("id", str(uuid4()))
        self.sibling_links = kwargs.pop("sibling_links", [])
        self.topics = kwargs.pop("topics", [])
        self.created_at = kwargs.pop("created_at", datetime.utcnow())
        self.updated_at = kwargs.pop("updated_at", datetime.utcnow())
        for key, val in kwargs.items():
            setattr(self, key, val)

    async def save(self):
        return None


def _make_test_client(monkeypatch):
    app = FastAPI()
    app.include_router(context_tree_router)

    monkeypatch.setattr(
        context_tree_service_module,
        "ContextTreeNode",
        FakeContextTreeNode,
    )

    repository = InMemoryContextTreeRepository()
    service = ContextTreeService(repository)
    service._ai_organize_node = AsyncMock(return_value=None)
    service._delete_ai_conversation = AsyncMock(return_value=True)

    app.dependency_overrides[get_context_tree_service] = lambda: service

    # These routes now resolve the project (and, for node routes, the node's project) to check
    # membership. This suite is about the node/scoring behaviour, so the access checks are
    # stubbed out here and covered on their own in test_project_access_e2e.py.
    app.dependency_overrides[project_for_member] = lambda: FakeProject()
    app.dependency_overrides[node_for_member] = _node_from_path(repository)
    return TestClient(app)


class FakeProject:
    """Stands in for the project an access check would have loaded."""

    def __init__(self, project_id: str = "project-under-test"):
        self.id = project_id


def _node_from_path(repository):
    """Resolve the node the way the real dependency does, minus the membership check."""

    async def resolve(node_id: str):
        node = await repository.get_by_id(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        return node

    return resolve


def _create_node(client, project_id: str, header: str, conversation_id: str) -> str:
    response = client.post(
        f"/context-tree/projects/{project_id}/nodes",
        json={
            "header": header,
            "summary": f"Summary text for {header} used in correlation scoring tests.",
            "topics": ["testing"],
            "node_type": "conversation",
            "conversation_id": conversation_id,
        },
    )
    assert response.status_code == 200
    return response.json()["id"]


def _links(client, node_id: str) -> dict:
    response = client.get(f"/context-tree/nodes/{node_id}")
    assert response.status_code == 200
    return {
        link["sibling_id"]: link["correlation_score"]
        for link in response.json()["sibling_links"]
    }


def _put_scores(client, node_id: str, scores: dict):
    return client.put(
        f"/context-tree/nodes/{node_id}/sibling-scores",
        json={
            "scores": [
                {"sibling_id": sibling_id, "correlation_score": score}
                for sibling_id, score in scores.items()
            ],
            "source": "embedding",
        },
    )


def test_create_list_get_and_delete_nodes(monkeypatch):
    client = _make_test_client(monkeypatch)
    project_id = "proj-crud"

    node_a = _create_node(client, project_id, "Racing cars", "conv-a")
    node_b = _create_node(client, project_id, "Race runners", "conv-b")

    listed = client.get(f"/context-tree/projects/{project_id}/nodes")
    assert listed.status_code == 200
    assert len(listed.json()) == 2

    assert _put_scores(client, node_a, {node_b: 70}).status_code == 200
    assert _links(client, node_b) == {node_a: 70}

    assert client.delete(f"/context-tree/nodes/{node_b}").status_code == 200
    assert _links(client, node_a) == {}


def test_sibling_scores_overwrite_prune_and_retain(monkeypatch):
    client = _make_test_client(monkeypatch)
    project_id = "proj-scores"

    node_a = _create_node(client, project_id, "Racing cars", "conv-a")
    node_b = _create_node(client, project_id, "Race runners", "conv-b")
    node_c = _create_node(client, project_id, "Premium rentals", "conv-c")

    assert _links(client, node_a) == {}

    response = _put_scores(client, node_a, {node_c: 80, node_b: 10})
    assert response.status_code == 200
    assert _links(client, node_a) == {node_c: 80}
    assert _links(client, node_c) == {node_a: 80}
    assert _links(client, node_b) == {}

    assert _put_scores(client, node_b, {node_c: 45}).status_code == 200
    assert _links(client, node_b) == {node_c: 45}
    assert _links(client, node_c) == {node_a: 80, node_b: 45}

    assert _put_scores(client, node_a, {node_b: 90}).status_code == 200
    links_a = _links(client, node_a)
    assert links_a[node_b] == 90
    assert links_a[node_c] == 80

    assert _put_scores(client, node_a, {node_c: 10}).status_code == 200
    links_a_after_prune = _links(client, node_a)
    assert node_c not in links_a_after_prune
    assert links_a_after_prune[node_b] == 90
    assert node_a not in _links(client, node_c)
    assert _links(client, node_c)[node_b] == 45


def test_sibling_scores_are_idempotent(monkeypatch):
    client = _make_test_client(monkeypatch)
    project_id = "proj-idempotent"

    node_a = _create_node(client, project_id, "Racing cars", "conv-a")
    node_b = _create_node(client, project_id, "Race runners", "conv-b")

    assert _put_scores(client, node_a, {node_b: 55}).status_code == 200
    first = _links(client, node_a)

    assert _put_scores(client, node_a, {node_b: 55}).status_code == 200
    assert _links(client, node_a) == first
    assert _links(client, node_b) == {node_a: 55}


def test_sibling_scores_reject_unknown_sibling(monkeypatch):
    client = _make_test_client(monkeypatch)
    node_a = _create_node(client, "proj-unknown", "Racing cars", "conv-a")

    response = _put_scores(client, node_a, {"does-not-exist": 60})
    assert response.status_code == 422
    assert "does-not-exist" in response.json()["detail"]


def test_sibling_scores_unknown_node_returns_404(monkeypatch):
    client = _make_test_client(monkeypatch)
    response = _put_scores(client, "missing-node", {})
    assert response.status_code == 404


def test_sibling_scores_reject_out_of_range_score(monkeypatch):
    client = _make_test_client(monkeypatch)
    node_a = _create_node(client, "proj-range", "Racing cars", "conv-a")

    response = _put_scores(client, node_a, {node_a: 150})
    assert response.status_code == 422
