from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from projects_service.data.context_tree_repository import ContextTreeRepository
from projects_service.models.context_tree import SiblingLink
from projects_service.schemas.context_tree_schemas import (
    ContextTreeNodeResponse,
    CreateContextTreeNodeRequest,
    NearPeerPayload,
    SiblingScorePayload,
    UpdateContextTreeNodeRequest,
)
from projects_service.services.context_tree_service import ContextTreeService


def _build_node(
    node_id: str,
    project_id: str,
    topics: list[str] | None = None,
    sibling_links: list[SiblingLink] | None = None,
    conversation_id: str | None = None,
    summary: str | None = None,
):
    node = MagicMock()
    node.id = node_id
    node.project_id = project_id
    node.header = f"Node {node_id}"
    node.summary = summary or (
        "This is a detailed summary sentence for testing node correlation behavior."
    )
    node.topics = topics or []
    node.sibling_links = sibling_links or []
    node.node_type = "goal"
    node.color = "#2196f3"
    node.conversation_id = conversation_id
    node.near_peers = []
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
                SiblingLink(sibling_id="node-2", correlation_score=64),
            ],
        )
        mock_repository.get_by_id = AsyncMock(return_value=node)

        result = await service.get_node("node-1")

        assert isinstance(result, ContextTreeNodeResponse)
        assert result.id == "node-1"
        assert result.project_id == "project-1"
        assert len(result.sibling_links) == 1
        assert result.sibling_links[0].sibling_id == "node-2"
        assert result.sibling_links[0].correlation_score == 64

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
    async def test_recompute_ai_scored_links_is_symmetric(
        self, service, mock_repository
    ):
        project_id = "project-1"
        node_a = _build_node(
            "a",
            project_id,
            summary=(
                "Racing car rental platform with performance vehicle booking and premium track package management."
            ),
        )
        node_b = _build_node(
            "b",
            project_id,
            summary=(
                "Running fitness coaching plans for marathon training and hydration strategy tracking."
            ),
        )
        node_c = _build_node(
            "c",
            project_id,
            summary=(
                "Premium racing car rental service with performance vehicle booking and track package management."
            ),
        )

        mock_repository.list_by_project = AsyncMock(
            return_value=[node_a, node_b, node_c]
        )

        await service._recompute_weighted_links_for_node(
            project_id,
            "a",
            include_peer_scores={"c": 78, "b": 22},
        )

        a_map = service._get_link_map(node_a)
        b_map = service._get_link_map(node_b)
        c_map = service._get_link_map(node_c)

        assert "c" in a_map
        assert a_map["c"] == 78
        assert c_map["a"] == 78
        assert "b" not in a_map
        assert "a" not in b_map

    @pytest.mark.asyncio
    async def test_update_node_keeps_ai_score_links_only(
        self, service, mock_repository
    ):
        project_id = "project-1"
        node_id = "a"

        existing = _build_node(
            node_id,
            project_id,
            summary=(
                "Racing vehicle marketplace with booking workflow, car catalog, and speed package options."
            ),
        )
        updated = _build_node(
            node_id,
            project_id,
            sibling_links=[SiblingLink(sibling_id="b", correlation_score=74)],
            summary=(
                "Running fitness coaching plans with hydration reminders and marathon schedule management."
            ),
        )
        peer = _build_node(
            "b",
            project_id,
            summary=(
                "Running fitness and hydration coaching for marathon athletes with personalized schedules."
            ),
        )

        mock_repository.get_by_id = AsyncMock(side_effect=[existing, updated])
        mock_repository.update = AsyncMock(return_value=updated)
        mock_repository.list_by_project = AsyncMock(return_value=[updated, peer])

        result = await service.update_node(
            node_id,
            UpdateContextTreeNodeRequest(
                summary=(
                    "Running fitness coaching plans with hydration reminders and marathon schedule management."
                )
            ),
        )

        assert isinstance(result, ContextTreeNodeResponse)
        assert result.id == node_id

        updated_map = service._get_link_map(updated)
        peer_map = service._get_link_map(peer)
        assert updated_map["b"] == 74
        assert peer_map["a"] == 74

    @pytest.mark.asyncio
    async def test_delete_node_removes_reciprocal_links(self, service, mock_repository):
        project_id = "project-1"
        node = _build_node(
            "a",
            project_id,
            topics=["cars"],
            sibling_links=[SiblingLink(sibling_id="b", correlation_score=55)],
            conversation_id="conv-1",
        )
        peer = _build_node(
            "b",
            project_id,
            topics=["cars"],
            sibling_links=[SiblingLink(sibling_id="a", correlation_score=55)],
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

    def test_get_link_map_ignores_invalid_or_low_score_links(self, service):
        node = _build_node(
            "n1",
            "p1",
            sibling_links=[
                SiblingLink(sibling_id="n2", correlation_score=0),
                SiblingLink(sibling_id="", correlation_score=85),
                SiblingLink(sibling_id="n3", correlation_score=72),
            ],
        )

        link_map = service._get_link_map(node)

        assert "n2" not in link_map
        assert "" not in link_map
        assert link_map["n3"] == 72

    @pytest.mark.asyncio
    async def test_recompute_prunes_links_scored_below_threshold(
        self, service, mock_repository
    ):
        project_id = "project-1"
        node_a = _build_node(
            "a",
            project_id,
            sibling_links=[SiblingLink(sibling_id="b", correlation_score=55)],
            summary="tiny",
        )
        node_b = _build_node(
            "b",
            project_id,
            sibling_links=[SiblingLink(sibling_id="a", correlation_score=55)],
            summary="short",
        )

        mock_repository.list_by_project = AsyncMock(return_value=[node_a, node_b])

        await service._recompute_weighted_links_for_node(project_id, "a", {"b": 10})

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

    @pytest.mark.asyncio
    async def test_near_peers_are_recorded_without_becoming_links(
        self, service, mock_repository
    ):
        """A node with nothing close enough stays unlinked, but says what it was nearest to.

        The AI service reports the closest peers that failed the similarity floor. Turning
        them into links would assert a relationship the numbers do not support, so they are
        stored separately and only the zero scores reach sibling_links.
        """
        node = _build_node(node_id="node-1", project_id="project-1")
        peer = _build_node(node_id="node-2", project_id="project-1")
        mock_repository.get_by_id = AsyncMock(return_value=node)
        mock_repository.list_by_project = AsyncMock(return_value=[node, peer])
        mock_repository.update = AsyncMock(return_value=None)

        result = await service.apply_sibling_scores(
            "node-1",
            [SiblingScorePayload(sibling_id="node-2", correlation_score=0)],
            "embedding",
            [NearPeerPayload(sibling_id="node-2", similarity=0.394)],
        )

        assert result is not None
        assert result.sibling_links == []
        written = [call.args[1] for call in mock_repository.update.call_args_list]
        near = next(
            fields["near_peers"] for fields in written if "near_peers" in fields
        )
        assert near == [{"sibling_id": "node-2", "similarity": 0.394}]

    @pytest.mark.asyncio
    async def test_near_peers_are_cleared_once_real_links_exist(
        self, service, mock_repository
    ):
        """Written on every push, so a node does not keep advertising stale near peers."""
        node = _build_node(node_id="node-1", project_id="project-1")
        peer = _build_node(node_id="node-2", project_id="project-1")
        mock_repository.get_by_id = AsyncMock(return_value=node)
        mock_repository.list_by_project = AsyncMock(return_value=[node, peer])
        mock_repository.update = AsyncMock(return_value=None)

        await service.apply_sibling_scores(
            "node-1",
            [SiblingScorePayload(sibling_id="node-2", correlation_score=95)],
            "embedding",
            [],
        )

        written = [call.args[1] for call in mock_repository.update.call_args_list]
        near = next(
            fields["near_peers"] for fields in written if "near_peers" in fields
        )
        assert near == []
