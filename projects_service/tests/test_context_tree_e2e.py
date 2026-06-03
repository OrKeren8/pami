from datetime import datetime
from uuid import uuid4
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from projects_service.api.v1.context_tree import router as context_tree_router
from projects_service.dependencies import get_context_tree_service
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

    app.dependency_overrides[get_context_tree_service] = lambda: service
    return TestClient(app)


def test_context_tree_full_flow_with_weighted_links(monkeypatch):
    client = _make_test_client(monkeypatch)
    project_id = "proj-e2e"

    response_a = client.post(
        f"/context-tree/projects/{project_id}/nodes",
        json={
            "header": "Racing cars",
            "summary": "Cars for racing rentals",
            "topics": ["racing", "cars", "rentals"],
            "node_type": "conversation",
            "conversation_id": "conv-a",
        },
    )
    assert response_a.status_code == 200
    node_a_id = response_a.json()["id"]

    response_b = client.post(
        f"/context-tree/projects/{project_id}/nodes",
        json={
            "header": "Race runners",
            "summary": "Running competition",
            "topics": ["racing", "running"],
            "node_type": "conversation",
            "conversation_id": "conv-b",
        },
    )
    assert response_b.status_code == 200
    node_b_id = response_b.json()["id"]

    response_c = client.post(
        f"/context-tree/projects/{project_id}/nodes",
        json={
            "header": "Premium racing rentals",
            "summary": "High-end cars for racing rentals",
            "topics": ["racing", "cars", "rentals", "luxury"],
            "node_type": "conversation",
            "conversation_id": "conv-c",
        },
    )
    assert response_c.status_code == 200
    node_c_id = response_c.json()["id"]

    node_a = client.get(f"/context-tree/nodes/{node_a_id}")
    assert node_a.status_code == 200
    links_a = {
        link["sibling_id"]: set(link["shared_tags"])
        for link in node_a.json()["sibling_links"]
    }

    assert node_b_id in links_a
    assert node_c_id in links_a
    assert links_a[node_b_id] == {"racing"}
    assert links_a[node_c_id] == {"cars", "racing", "rentals"}

    listed = client.get(f"/context-tree/projects/{project_id}/nodes")
    assert listed.status_code == 200
    assert len(listed.json()) == 3

    updated = client.put(
        f"/context-tree/nodes/{node_b_id}",
        json={"topics": ["running", "fitness"]},
    )
    assert updated.status_code == 200

    node_a_after_update = client.get(f"/context-tree/nodes/{node_a_id}")
    assert node_a_after_update.status_code == 200
    links_after_update = {
        link["sibling_id"]: set(link["shared_tags"])
        for link in node_a_after_update.json()["sibling_links"]
    }
    assert node_b_id not in links_after_update
    assert node_c_id in links_after_update

    deleted = client.delete(f"/context-tree/nodes/{node_c_id}")
    assert deleted.status_code == 200

    node_a_after_delete = client.get(f"/context-tree/nodes/{node_a_id}")
    assert node_a_after_delete.status_code == 200
    links_after_delete = {
        link["sibling_id"] for link in node_a_after_delete.json()["sibling_links"]
    }
    assert node_c_id not in links_after_delete
