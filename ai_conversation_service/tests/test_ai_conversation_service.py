import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from ai_conversation_service.services.ai_conversation_service.service import (
    AIConversationService,
    Conversation,
)


class TestAIConversationService:
    @pytest.fixture
    def mock_s3_client(self):
        return MagicMock()

    @pytest.fixture
    def mock_bedrock_client(self):
        return MagicMock()

    @pytest.fixture
    def service(self, mock_s3_client, mock_bedrock_client):
        with patch("boto3.client") as mock_boto3_client:
            mock_boto3_client.side_effect = lambda service, **kwargs: {
                "s3": mock_s3_client,
                "bedrock-runtime": mock_bedrock_client,
            }.get(service, MagicMock())

            service = AIConversationService()
            service.s3_client = mock_s3_client
            service.bedrock_client = mock_bedrock_client
            return service

    @pytest.mark.asyncio
    async def test_create_conversation(self, service, mock_s3_client):
        # Arrange
        context_node_id = "node123"
        project_id = "proj123"
        title = "Test Conversation"

        # Act
        conversation = await service.create_conversation(
            context_node_id, project_id, title
        )

        # Assert
        assert conversation.context_node_id == context_node_id
        assert conversation.project_id == project_id
        assert conversation.title == title
        assert conversation.status == "active"
        assert len(conversation.messages) == 0
        assert conversation.conversation_id is not None

        # Verify S3 was called to save initial conversation
        mock_s3_client.put_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_send_message_success(
        self, service, mock_s3_client, mock_bedrock_client
    ):
        # Arrange
        conversation_id = "conv123"
        user_message = "Hello AI"
        context_snapshot = {"some": "data"}

        # Mock conversation loading
        conversation_data = {
            "conversation_id": conversation_id,
            "context_node_id": "node123",
            "project_id": "proj123",
            "title": "Test",
            "messages": [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "status": "active",
        }

        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(
                read=MagicMock(return_value=str(conversation_data).encode())
            )
        }

        # Mock Bedrock response
        mock_bedrock_client.invoke_model.return_value = {
            "body": MagicMock(
                read=MagicMock(return_value=b'{"outputs": [{"text": "Hello human!"}]}')
            )
        }

        # Act
        response = await service.send_message(
            conversation_id, user_message, context_snapshot
        )

        # Assert
        assert "Hello human!" in response

        # Verify S3 was called to save updated conversation
        assert mock_s3_client.put_object.call_count == 2  # Initial load + save

    @pytest.mark.asyncio
    async def test_send_message_conversation_not_found(self, service, mock_s3_client):
        # Arrange
        mock_s3_client.get_object.side_effect = Exception("NoSuchKey")

        # Act & Assert
        with pytest.raises(Exception, match="Conversation not found"):
            await service.send_message("nonexistent", "Hello")

    @pytest.mark.asyncio
    async def test_get_conversation_history(self, service, mock_s3_client):
        # Arrange
        conversation_id = "conv123"
        conversation_data = {
            "conversation_id": conversation_id,
            "context_node_id": "node123",
            "project_id": "proj123",
            "title": "Test Conversation",
            "messages": [
                {
                    "role": "user",
                    "content": "Hello",
                    "timestamp": datetime.utcnow().isoformat(),
                    "context_snapshot": None,
                },
                {
                    "role": "assistant",
                    "content": "Hi there!",
                    "timestamp": datetime.utcnow().isoformat(),
                    "model": "anthropic.claude-3-sonnet-20240229-v1:0",
                    "tokens_used": 150,
                },
            ],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "status": "active",
        }

        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(
                read=MagicMock(return_value=str(conversation_data).encode())
            )
        }

        # Act
        history = await service.get_conversation_history(conversation_id)

        # Assert
        assert history["conversation_id"] == conversation_id
        assert len(history["messages"]) == 2
        assert history["messages"][0]["role"] == "user"
        assert history["messages"][1]["role"] == "assistant"

    @pytest.mark.asyncio
    async def test_list_conversations_for_node(self, service, mock_s3_client):
        # Arrange
        context_node_id = "node123"

        # Mock S3 list_objects_v2 to return conversation keys
        mock_s3_client.list_objects_v2.return_value = {
            "Contents": [
                {"Key": f"conversations/{context_node_id}/conv1.json"},
                {"Key": f"conversations/{context_node_id}/conv2.json"},
                {
                    "Key": f"conversations/other_node/conv3.json"
                },  # Should be filtered out
            ]
        }

        # Mock get_object for individual conversations
        conversation_data = {
            "conversation_id": "conv1",
            "context_node_id": context_node_id,
            "project_id": "proj123",
            "title": "Conversation 1",
            "messages": [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "status": "active",
        }

        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(
                read=MagicMock(return_value=str(conversation_data).encode())
            )
        }

        # Act
        conversations = await service.list_conversations_for_node(context_node_id)

        # Assert
        assert len(conversations) == 2  # Only conversations for the specified node
        assert all(conv.context_node_id == context_node_id for conv in conversations)

    @pytest.mark.asyncio
    async def test_delete_conversation(self, service, mock_s3_client):
        # Arrange
        conversation_id = "conv123"
        context_node_id = "node123"

        # Mock conversation exists
        conversation_data = {
            "conversation_id": conversation_id,
            "context_node_id": context_node_id,
            "project_id": "proj123",
            "title": "Test",
            "messages": [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "status": "active",
        }

        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(
                read=MagicMock(return_value=str(conversation_data).encode())
            )
        }

        # Act
        result = await service.delete_conversation(conversation_id)

        # Assert
        assert result is True
        mock_s3_client.delete_object.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_conversation_not_found(self, service, mock_s3_client):
        # Arrange
        mock_s3_client.get_object.side_effect = Exception("NoSuchKey")

        # Act
        result = await service.delete_conversation("nonexistent")

        # Assert
        assert result is False

    def test_optimize_conversation_history(self, service):
        # Arrange
        messages = [
            {
                "role": "user",
                "content": "Hello",
                "timestamp": datetime.utcnow().isoformat(),
            },
            {
                "role": "assistant",
                "content": "Hi!",
                "timestamp": datetime.utcnow().isoformat(),
            },
            # Add many more messages to exceed token limit
        ] * 100  # 200 messages total

        # Act
        optimized = service._optimize_conversation_history(messages)

        # Assert
        # Should be less than original due to summarization
        assert len(optimized) < len(messages)
        # Should keep recent messages
        assert optimized[-1].role == "assistant"
        assert optimized[-2].role == "user"

    def test_estimate_tokens(self, service):
        # Arrange
        text = "Hello world! This is a test message."

        # Act
        tokens = service._estimate_tokens(text)

        # Assert
        # Rough estimate: ~4 tokens per word
        assert tokens > 0
        assert tokens < 50  # Should be reasonable

    @pytest.mark.asyncio
    async def test_call_bedrock_ai(self, service, mock_bedrock_client):
        # Arrange
        messages = [
            {
                "role": "user",
                "content": "Hello AI",
                "timestamp": datetime.utcnow().isoformat(),
            }
        ]
        context_snapshot = {"some": "context"}

        mock_bedrock_client.invoke_model.return_value = {
            "body": MagicMock(
                read=MagicMock(return_value=b'{"outputs": [{"text": "Hello human!"}]}')
            )
        }

        # Act
        response = await service._call_bedrock_ai(messages, context_snapshot)

        # Assert
        assert response == "Hello human!"
        mock_bedrock_client.invoke_model.assert_called_once()

    @pytest.mark.asyncio
    async def test_call_bedrock_ai_error_handling(self, service, mock_bedrock_client):
        # Arrange
        messages = [
            {
                "role": "user",
                "content": "Hello",
                "timestamp": datetime.utcnow().isoformat(),
            }
        ]
        mock_bedrock_client.invoke_model.side_effect = Exception("Bedrock error")

        # Act & Assert
        with pytest.raises(Exception, match="Bedrock error"):
            await service._call_bedrock_ai(messages)

    @pytest.mark.asyncio
    async def test_create_conversation_requires_context_and_project(self, service):
        with pytest.raises(
            ValueError, match="context_node_id and project_id are required"
        ):
            await service.create_conversation("", "")

    @pytest.mark.asyncio
    async def test_create_conversation_sanitizes_and_truncates_title(
        self, service, mock_s3_client
    ):
        long_title = "bad/title\\name_" + ("x" * 200)

        conversation = await service.create_conversation(
            "node123", "proj123", long_title
        )

        assert "/" not in conversation.title
        assert "\\" not in conversation.title
        assert len(conversation.title) <= 100
        mock_s3_client.put_object.assert_called()

    @pytest.mark.asyncio
    async def test_get_conversation_invalid_payload_returns_none(
        self, service, mock_s3_client
    ):
        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(
                read=MagicMock(return_value=b"not-json-or-python-literal")
            )
        }

        conversation = await service.get_conversation("conv123")

        assert conversation is None

    @pytest.mark.asyncio
    async def test_get_conversation_history_respects_limit(
        self, service, mock_s3_client
    ):
        conversation_id = "conv123"
        messages = [
            {
                "role": "user",
                "content": f"msg-{i}",
                "timestamp": datetime.utcnow().isoformat(),
            }
            for i in range(5)
        ]
        conversation_data = {
            "conversation_id": conversation_id,
            "context_node_id": "node123",
            "project_id": "proj123",
            "title": "Test",
            "messages": messages,
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
            "status": "active",
        }

        mock_s3_client.get_object.return_value = {
            "Body": MagicMock(
                read=MagicMock(return_value=str(conversation_data).encode())
            )
        }

        history = await service.get_conversation_history(conversation_id, limit=2)

        assert history is not None
        assert len(history["messages"]) == 2
        assert history["messages"][0]["content"] == "msg-3"
        assert history["messages"][1]["content"] == "msg-4"

    @pytest.mark.asyncio
    async def test_call_openai_without_any_backend_raises(self, service):
        service.bedrock_client = None
        service.openai_client = None

        with pytest.raises(Exception, match="OpenAI client not initialized"):
            await service._call_openai([{"role": "user", "content": "hi"}])
