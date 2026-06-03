from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from projects_service.data.context_tree_repository import ContextTreeRepository
from projects_service.models.context_tree import SiblingLink
from projects_service.schemas.context_tree_schemas import (
    ContextTreeNodeResponse,
    CreateContextTreeNodeRequest,
    UpdateContextTreeNodeRequest,
)
from projects_service.services.context_tree_service import ContextTreeService


def _build_node(
    node_id: str,
    project_id: str,
    topics: list[str] | None = None,
    sibling_links: list[SiblingLink] | None = None,
    conversation_id: str | None = None,
):
    node = MagicMock()
    node.id = node_id
    node.project_id = project_id
    node.header = f"Node {node_id}"
    node.summary = f"Summary {node_id}"
    node.topics = topics or []
    node.sibling_links = sibling_links or []
    node.node_type = "goal"
    node.color = "#2196f3"
    node.conversation_id = conversation_id
    node.created_at = datetime.utcnow()
    node.updated_at = datetime.utcnow()
    node.save = AsyncMock(return_value=None)
    return node


class TestContextTreeService:
    @pytest.fixture
    def mock_repository(self):
        return MagicMock(spec=ContextTreeRepository)

    @pytest.fixture
    def service(self, mock_repository):
        return ContextTreeService(mock_repository)

    @pytest.mark.asyncio
    async def test_get_node_found(self, service, mock_repository):
        node = _build_node(
            node_id="node-1",
            project_id="project-1",
            topics=["racing", "cars"],
            sibling_links=[
                SiblingLink(sibling_id="node-2", shared_tags=["racing"]),
            ],
        )
        mock_repository.get_by_id = AsyncMock(return_value=node)

        result = await service.get_node("node-1")

        assert isinstance(result, ContextTreeNodeResponse)
        assert result.id == "node-1"
        assert result.project_id == "project-1"
        assert len(result.sibling_links) == 1
        assert result.sibling_links[0].sibling_id == "node-2"
        assert result.sibling_links[0].shared_tags == ["racing"]

    @pytest.mark.asyncio
    async def test_get_node_not_found(self, service, mock_repository):
        mock_repository.get_by_id = AsyncMock(return_value=None)

        result = await service.get_node("missing")

        assert result is None

    @pytest.mark.asyncio
    @patch("projects_service.services.context_tree_service.ContextTreeNode")
    async def test_create_node_with_provided_conversation_id(
        self,
        mock_context_node_class,
        service,
        mock_repository,
    ):
        project_id = "project-1"
        created_node = _build_node(
            node_id="node-1",
            project_id=project_id,
            topics=["racing", "cars"],
        )

        mock_context_node_class.return_value = created_node
        mock_repository.create = AsyncMock(return_value=created_node)
        mock_repository.list_by_project = AsyncMock(return_value=[created_node])
        mock_repository.get_by_id = AsyncMock(return_value=created_node)

        service._create_ai_conversation = AsyncMock(
            side_effect=AssertionError("_create_ai_conversation should not be called")
        )
        service._ai_organize_node = AsyncMock(return_value=None)

        request = CreateContextTreeNodeRequest(
            header="Cars",
            summary="About racing cars",
            topics=["racing", "cars"],
            node_type="conversation",
            conversation_id="conv-1",
        )

        result = await service.create_node(project_id, request)

        assert isinstance(result, ContextTreeNodeResponse)
        assert result.id == "node-1"
        assert result.conversation_id == "conv-1"
        service._create_ai_conversation.assert_not_called()
        service._ai_organize_node.assert_called()

    @pytest.mark.asyncio
    async def test_recompute_weighted_links_is_symmetric(
        self, service, mock_repository
    ):
        project_id = "project-1"
        node_a = _build_node("a", project_id, topics=["racing", "cars", "speed"])
        node_b = _build_node("b", project_id, topics=["racing", "running"])
        node_c = _build_node("c", project_id, topics=["racing", "cars", "luxury"])

        mock_repository.list_by_project = AsyncMock(
            return_value=[node_a, node_b, node_c]
        )

        await service._recompute_weighted_links_for_node(project_id, "a")

        a_map = service._get_link_map(node_a)
        b_map = service._get_link_map(node_b)
        c_map = service._get_link_map(node_c)

        assert a_map["b"] == {"racing"}
        assert a_map["c"] == {"racing", "cars"}
        assert b_map["a"] == {"racing"}
        assert c_map["a"] == {"racing", "cars"}

    @pytest.mark.asyncio
    async def test_update_node_recomputes_links_from_topics(
        self, service, mock_repository
    ):
        project_id = "project-1"
        node_id = "a"

        existing = _build_node(node_id, project_id, topics=["racing", "cars"])
        updated = _build_node(node_id, project_id, topics=["running", "fitness"])
        peer = _build_node("b", project_id, topics=["running", "hydration"])

        mock_repository.get_by_id = AsyncMock(side_effect=[existing, updated])
        mock_repository.update = AsyncMock(return_value=updated)
        mock_repository.list_by_project = AsyncMock(return_value=[updated, peer])

        result = await service.update_node(
            node_id,
            UpdateContextTreeNodeRequest(topics=["running", "fitness"]),
        )

        assert isinstance(result, ContextTreeNodeResponse)
        assert result.id == node_id

        updated_map = service._get_link_map(updated)
        peer_map = service._get_link_map(peer)
        assert updated_map["b"] == {"running"}
        assert peer_map["a"] == {"running"}

    @pytest.mark.asyncio
    async def test_delete_node_removes_reciprocal_links(self, service, mock_repository):
        project_id = "project-1"
        node = _build_node(
            "a",
            project_id,
            topics=["cars"],
            sibling_links=[SiblingLink(sibling_id="b", shared_tags=["cars"])],
            conversation_id="conv-1",
        )
        peer = _build_node(
            "b",
            project_id,
            topics=["cars"],
            sibling_links=[SiblingLink(sibling_id="a", shared_tags=["cars"])],
        )

        mock_repository.get_by_id = AsyncMock(return_value=node)
        mock_repository.list_by_project = AsyncMock(return_value=[node, peer])
        mock_repository.delete = AsyncMock(return_value=True)

        service._delete_ai_conversation = AsyncMock(return_value=True)

        deleted = await service.delete_node("a")

        assert deleted is True
        assert "a" not in service._get_link_map(peer)
        service._delete_ai_conversation.assert_called_once_with("conv-1")
        mock_repository.delete.assert_called_once_with("a")

    def test_normalize_topics_deduplicates_and_normalizes_case(self, service):
        topics = ["Racing", " racing ", "Cars", "cars", ""]

        normalized = service._normalize_topics(topics)

        assert normalized == ["racing", "cars"]

    def test_get_link_map_ignores_invalid_or_empty_links(self, service):
        node = _build_node(
            "n1",
            "p1",
            sibling_links=[
                SiblingLink(sibling_id="n2", shared_tags=[]),
                SiblingLink(sibling_id="", shared_tags=["cars"]),
                SiblingLink(sibling_id="n3", shared_tags=["cars", "cars"]),
            ],
        )

        link_map = service._get_link_map(node)

        assert "n2" not in link_map
        assert "" not in link_map
        assert link_map["n3"] == {"cars"}

    @pytest.mark.asyncio
    async def test_recompute_prunes_stale_links_with_no_shared_tags(
        self, service, mock_repository
    ):
        project_id = "project-1"
        node_a = _build_node(
            "a",
            project_id,
            topics=["cars"],
            sibling_links=[SiblingLink(sibling_id="b", shared_tags=["cars"])],
        )
        node_b = _build_node(
            "b",
            project_id,
            topics=["running"],
            sibling_links=[SiblingLink(sibling_id="a", shared_tags=["cars"])],
        )

        mock_repository.list_by_project = AsyncMock(return_value=[node_a, node_b])

        await service._recompute_weighted_links_for_node(project_id, "a")

        assert service._get_link_map(node_a) == {}
        assert service._get_link_map(node_b) == {}

    @pytest.mark.asyncio
    async def test_update_node_not_found_returns_none(self, service, mock_repository):
        mock_repository.get_by_id = AsyncMock(return_value=None)

        result = await service.update_node(
            "missing",
            UpdateContextTreeNodeRequest(topics=["cars"]),
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_node_not_found_returns_false(self, service, mock_repository):
        mock_repository.get_by_id = AsyncMock(return_value=None)

        deleted = await service.delete_node("missing")

        assert deleted is False
