import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

from projects_service.models.context_tree import ContextTreeNode
from projects_service.services.context_tree_service import ContextTreeService
from projects_service.schemas.context_tree_schemas import (
    CreateContextTreeNodeRequest,
    UpdateContextTreeNodeRequest,
    ContextTreeNodeResponse,
)
from projects_service.data.context_tree_repository import ContextTreeRepository


class TestContextTreeService:
    @pytest.fixture
    def mock_repository(self):
        return MagicMock(spec=ContextTreeRepository)

    @pytest.fixture
    def service(self, mock_repository):
        return ContextTreeService(mock_repository)

    @pytest.mark.asyncio
    @patch("projects_service.services.context_tree_service.ContextTreeNode")
    async def test_create_node(self, mock_node_class, service, mock_repository):
        """Test creating a context tree node."""
        project_id = "507f1f77bcf86cd799439011"
        request = CreateContextTreeNodeRequest(
            # node_id is auto-generated, not provided
            parent_id="parent-node",
            children_ids=["child-1", "child-2"],
            text="Test node",
            node_type="goal",
        )

        # Mock the node instance
        mock_node_instance = MagicMock()
        mock_node_class.return_value = mock_node_instance

        # Mock the created node from repository
        created_node = MagicMock()
        created_node.id = "550e8400-e29b-41d4-a716-446655440000"  # UUID format - always auto-generated
        created_node.parent_id = "parent-node"
        created_node.children_ids = ["child-1", "child-2"]
        created_node.text = "Test node"
        created_node.project_id = project_id
        created_node.node_type = "goal"
        created_node.created_at = datetime.utcnow()
        created_node.updated_at = datetime.utcnow()

        mock_repository.create = AsyncMock(return_value=created_node)

        result = await service.create_node(project_id, request)

        assert isinstance(result, ContextTreeNodeResponse)
        assert result.id == "550e8400-e29b-41d4-a716-446655440000"
        assert result.parent_id == "parent-node"
        assert result.children_ids == ["child-1", "child-2"]
        assert result.text == "Test node"
        assert result.node_type == "goal"
        assert result.project_id == project_id

        # Verify repository was called
        mock_repository.create.assert_called_once()
        mock_node_class.assert_called_once()

    @pytest.mark.asyncio
    @patch("projects_service.services.context_tree_service.ContextTreeNode")
    async def test_create_node_updates_parent_children(
        self, mock_node_class, service, mock_repository
    ):
        """Test that creating a node with a parent updates the parent's children list."""
        project_id = "507f1f77bcf86cd799439011"
        parent_node_id = "parent-uuid-123"

        # Mock existing parent node
        parent_node = MagicMock()
        parent_node.id = parent_node_id
        parent_node.parent_id = None
        parent_node.children_ids = ["existing-child-1"]  # Already has one child
        parent_node.text = "Parent Node"
        parent_node.project_id = project_id
        parent_node.node_type = "goal"
        parent_node.created_at = datetime.utcnow()
        parent_node.updated_at = datetime.utcnow()

        # Mock the child node creation
        child_request = CreateContextTreeNodeRequest(
            parent_id=parent_node_id,  # References the parent
            children_ids=[],
            text="Child Node",
            node_type="task",
        )

        # Mock the node instance for child
        child_node_instance = MagicMock()
        child_node_instance.id = str(uuid.uuid4())  # Mock generated UUID
        child_node_instance.parent_id = child_request.parent_id
        child_node_instance.children_ids = child_request.children_ids
        child_node_instance.text = child_request.text
        child_node_instance.project_id = project_id
        child_node_instance.node_type = child_request.node_type
        child_node_instance.created_at = datetime.utcnow()
        child_node_instance.updated_at = datetime.utcnow()
        mock_node_class.return_value = child_node_instance

        # Mock repository calls
        mock_repository.create = AsyncMock(side_effect=lambda node: node)  # Return the node that was created
        mock_repository.get_by_id = AsyncMock(return_value=parent_node)
        mock_repository.update = AsyncMock(return_value=parent_node)

        # Execute the create operation
        result = await service.create_node(project_id, child_request)

        # Verify the child was created correctly
        assert isinstance(result, ContextTreeNodeResponse)
        assert result.parent_id == parent_node_id
        assert result.text == "Child Node"
        # Assert that the id is a valid UUID
        assert uuid.UUID(result.id).version == 4

        # Verify the parent was updated to include the child
        mock_repository.update.assert_called_once()
        # The parent's children_ids should now include the new child
        updated_parent = mock_repository.update.call_args[0][0]
        assert (
            result.id in updated_parent.children_ids
        )  # Use the actual generated id
        assert (
            "existing-child-1" in updated_parent.children_ids
        )  # Should keep existing children

    @pytest.mark.asyncio
    async def test_get_node_found(self, service, mock_repository):
        """Test getting a node when found."""
        node_id = "node-1"

        node = MagicMock()
        node.id = node_id
        node.parent_id = "parent-node"
        node.children_ids = ["child-1"]
        node.text = "Test node"
        node.project_id = "507f1f77bcf86cd799439011"
        node.node_type = "goal"
        node.created_at = datetime.utcnow()
        node.updated_at = datetime.utcnow()

        mock_repository.get_by_id = AsyncMock(return_value=node)

        result = await service.get_node(node_id)

        assert result is not None
        assert result.id == node_id
        assert result.text == "Test node"
        assert result.node_type == "goal"
        mock_repository.get_by_id.assert_called_once_with(node_id)

    @pytest.mark.asyncio
    async def test_get_node_not_found(self, service, mock_repository):
        """Test getting a node when not found."""
        node_id = "node-1"

        mock_repository.get_by_id = AsyncMock(return_value=None)

        result = await service.get_node(node_id)

        assert result is None
        mock_repository.get_by_id.assert_called_once_with(node_id)

    @pytest.mark.asyncio
    async def test_list_nodes_by_project(self, service, mock_repository):
        """Test listing nodes by project."""
        project_id = "507f1f77bcf86cd799439011"
        node1 = MagicMock()
        node1.id = "node-1"
        node1.text = "Node 1"
        node1.project_id = project_id
        node1.node_type = "goal"
        node1.parent_id = None
        node1.children_ids = []
        node1.created_at = datetime.utcnow()
        node1.updated_at = datetime.utcnow()

        node2 = MagicMock()
        node2.id = "node-2"
        node2.text = "Node 2"
        node2.project_id = project_id
        node2.node_type = "task"
        node2.parent_id = None
        node2.children_ids = []
        node2.created_at = datetime.utcnow()
        node2.updated_at = datetime.utcnow()

        nodes = [node1, node2]

        mock_repository.list_by_project = AsyncMock(return_value=nodes)

        result = await service.list_nodes_by_project(project_id)

        assert len(result) == 2
        assert result[0].id == "node-1"
        assert result[1].id == "node-2"
        assert all(isinstance(r, ContextTreeNodeResponse) for r in result)
        assert all(r.project_id == project_id for r in result)
        mock_repository.list_by_project.assert_called_once_with(project_id)

    @pytest.mark.asyncio
    async def test_update_node_found(self, service, mock_repository):
        """Test updating a node when found."""
        node_id = "node-1"
        request = UpdateContextTreeNodeRequest(text="Updated text", node_type="task")

        updated_node = MagicMock()
        updated_node.id = "507f1f77bcf86cd799439012"
        updated_node.node_id = node_id
        updated_node.parent_id = "parent-node"
        updated_node.children_ids = ["child-1"]
        updated_node.text = "Updated text"
        updated_node.project_id = "507f1f77bcf86cd799439011"
        updated_node.node_type = "task"
        updated_node.created_at = datetime.utcnow()
        updated_node.updated_at = datetime.utcnow()

        mock_repository.update = AsyncMock(return_value=updated_node)

        result = await service.update_node(node_id, request)

        assert result is not None
        assert result.text == "Updated text"
        assert result.node_type == "task"
        mock_repository.update.assert_called_once()
        call_args = mock_repository.update.call_args[0]
        assert call_args[0] == node_id
        assert "text" in call_args[1]
        assert "node_type" in call_args[1]
        assert "updated_at" in call_args[1]
        assert call_args[1]["text"] == "Updated text"
        assert call_args[1]["node_type"] == "task"

    @pytest.mark.asyncio
    async def test_update_node_not_found(self, service, mock_repository):
        """Test updating a node when not found."""
        node_id = "node-1"
        request = UpdateContextTreeNodeRequest(text="Updated text")

        mock_repository.update = AsyncMock(return_value=None)

        result = await service.update_node(node_id, request)

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_node_found(self, service, mock_repository):
        """Test deleting a node when found."""
        node_id = "node-1"

        mock_repository.delete = AsyncMock(return_value=True)

        result = await service.delete_node(node_id)

        assert result is True
        mock_repository.delete.assert_called_once_with(node_id)

    @pytest.mark.asyncio
    async def test_delete_node_not_found(self, service, mock_repository):
        """Test deleting a node when not found."""
        node_id = "node-1"

        mock_repository.delete = AsyncMock(return_value=False)

        result = await service.delete_node(node_id)

        assert result is False
        mock_repository.delete.assert_called_once_with(node_id)
