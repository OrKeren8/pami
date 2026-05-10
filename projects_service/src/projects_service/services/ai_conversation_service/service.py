import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError
from loguru import logger

from projects_service.core.config import settings


class ConversationMessage:
    def __init__(self, role: str, content: str, timestamp: Optional[str] = None):
        self.role = role
        self.content = content
        self.timestamp = timestamp or datetime.utcnow().isoformat()


class Conversation:
    def __init__(self, conversation_id: str, context_node_id: str, project_id: str):
        self.conversation_id = conversation_id
        self.context_node_id = context_node_id
        self.project_id = project_id
        self.messages: List[Dict[str, Any]] = []
        self.created_at = datetime.utcnow().isoformat()
        self.updated_at = datetime.utcnow().isoformat()
        self.title = f"AI Discussion - {context_node_id}"
        self.status = "active"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "context_node_id": self.context_node_id,
            "project_id": self.project_id,
            "title": self.title,
            "messages": self.messages,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "status": self.status,
            "message_count": len(self.messages)
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Conversation':
        conv = cls(
            data["conversation_id"],
            data["context_node_id"],
            data["project_id"]
        )
        conv.messages = data.get("messages", [])
        conv.created_at = data.get("created_at", conv.created_at)
        conv.updated_at = data.get("updated_at", conv.updated_at)
        conv.title = data.get("title", conv.title)
        conv.status = data.get("status", conv.status)
        return conv


class AIConversationService:
    """Service for managing AI conversations with S3 storage and Bedrock integration."""

    def __init__(self):
        self._logger = logger.bind(service="AIConversationService")

        # Initialize AWS clients
        try:
            self.s3_client = boto3.client(
                's3',
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key
            )

            self.bedrock_client = boto3.client(
                'bedrock-runtime',
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                config=boto3.config.Config(
                    read_timeout=300,  # 5 minutes for model inference
                    retries={'max_attempts': 3, 'mode': 'standard'}
                )
            )

            self.bucket_name = f"pami-conversations-{settings.aws_region}"
            self._ensure_bucket_exists()

            self._logger.info("AI Conversation Service initialized successfully")

        except Exception as e:
            self._logger.error(f"Failed to initialize AI Conversation Service: {e}")
            self.s3_client = None
            self.bedrock_client = None

    def _ensure_bucket_exists(self):
        """Create S3 bucket if it doesn't exist."""
        try:
            self.s3_client.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                # Bucket doesn't exist, create it
                try:
                    if settings.aws_region == 'us-east-1':
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.s3_client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={'LocationConstraint': settings.aws_region}
                        )
                    self._logger.info(f"Created S3 bucket: {self.bucket_name}")
                except Exception as e:
                    self._logger.error(f"Failed to create bucket {self.bucket_name}: {e}")
            else:
                self._logger.error(f"Error checking bucket {self.bucket_name}: {e}")

    async def create_conversation(self, context_node_id: str, project_id: str, title: Optional[str] = None) -> Conversation:
        """Create a new conversation for a context node."""
        if not self.s3_client:
            raise Exception("S3 client not initialized")

        conversation_id = str(uuid.uuid4())
        conversation = Conversation(conversation_id, context_node_id, project_id)

        if title:
            conversation.title = title

        # Save to S3
        await self._save_conversation(conversation)

        self._logger.info(f"Created conversation {conversation_id} for node {context_node_id}")
        return conversation

    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        if not self.s3_client:
            raise Exception("S3 client not initialized")

        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=f"conversations/{conversation_id}.json"
            )

            data = json.loads(response['Body'].read().decode('utf-8'))
            return Conversation.from_dict(data)

        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return None
            raise

    async def send_message(self, conversation_id: str, user_message: str, context_snapshot: Optional[Dict] = None) -> str:
        """Send a message to the conversation and get AI response."""
        if not self.bedrock_client or not self.s3_client:
            raise Exception("AWS clients not initialized")

        # Load conversation
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            raise Exception(f"Conversation {conversation_id} not found")

        # Add user message
        user_msg = {
            "role": "user",
            "content": user_message,
            "timestamp": datetime.utcnow().isoformat(),
            "context_snapshot": context_snapshot
        }
        conversation.messages.append(user_msg)

        # Get AI response
        ai_response = await self._call_bedrock(conversation.messages)

        # Add AI response
        ai_msg = {
            "role": "assistant",
            "content": ai_response,
            "timestamp": datetime.utcnow().isoformat(),
            "model": settings.bedrock_model_id,
            "tokens_used": self._estimate_tokens(ai_response)
        }
        conversation.messages.append(ai_msg)

        # Update metadata
        conversation.updated_at = datetime.utcnow().isoformat()

        # Save updated conversation
        await self._save_conversation(conversation)

        self._logger.info(f"Processed message in conversation {conversation_id}")
        return ai_response

    async def get_conversation_history(self, conversation_id: str, limit: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """Get conversation history."""
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            return None

        data = conversation.to_dict()
        if limit:
            data["messages"] = data["messages"][-limit:]

        return data

    async def list_conversations_for_node(self, context_node_id: str) -> List[Dict[str, Any]]:
        """List all conversations for a context node."""
        if not self.s3_client:
            raise Exception("S3 client not initialized")

        try:
            # List objects with prefix
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=f"conversations/"
            )

            conversations = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    key = obj['Key']
                    if key.endswith('.json'):
                        try:
                            conv_response = self.s3_client.get_object(
                                Bucket=self.bucket_name,
                                Key=key
                            )
                            data = json.loads(conv_response['Body'].read().decode('utf-8'))

                            if data.get('context_node_id') == context_node_id:
                                conversations.append({
                                    "conversation_id": data["conversation_id"],
                                    "title": data["title"],
                                    "created_at": data["created_at"],
                                    "updated_at": data["updated_at"],
                                    "message_count": data.get("message_count", 0),
                                    "status": data.get("status", "active")
                                })

                        except Exception as e:
                            self._logger.error(f"Error reading conversation {key}: {e}")

            return conversations

        except Exception as e:
            self._logger.error(f"Error listing conversations for node {context_node_id}: {e}")
            return []

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation."""
        if not self.s3_client:
            raise Exception("S3 client not initialized")

        try:
            self.s3_client.delete_object(
                Bucket=self.bucket_name,
                Key=f"conversations/{conversation_id}.json"
            )
            self._logger.info(f"Deleted conversation {conversation_id}")
            return True

        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return False
            raise

    async def _save_conversation(self, conversation: Conversation):
        """Save conversation to S3."""
        data = conversation.to_dict()

        self.s3_client.put_object(
            Bucket=self.bucket_name,
            Key=f"conversations/{conversation.conversation_id}.json",
            Body=json.dumps(data, indent=2),
            ContentType='application/json'
        )

    async def _call_bedrock(self, messages: List[Dict[str, Any]]) -> str:
        """Call Bedrock with conversation messages."""
        # Convert to Bedrock format and limit to prevent token overflow
        bedrock_messages = []
        total_tokens = 0
        max_tokens = 180000  # Leave room for response

        # Process messages in reverse order (most recent first)
        for msg in reversed(messages):
            msg_tokens = self._estimate_tokens(msg["content"])
            if total_tokens + msg_tokens > max_tokens:
                break

            bedrock_messages.insert(0, {
                "role": msg["role"],
                "content": msg["content"]
            })
            total_tokens += msg_tokens

        try:
            response = self.bedrock_client.invoke_model(
                modelId=settings.bedrock_model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 2000,
                    "messages": bedrock_messages
                })
            )

            response_body = json.loads(response['body'].read())
            return response_body['content'][0]['text']

        except Exception as e:
            self._logger.error(f"Bedrock call failed: {e}")
            return "I apologize, but I'm having trouble responding right now. Please try again."

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (1 token ≈ 4 characters for English)."""
        return len(text) // 4