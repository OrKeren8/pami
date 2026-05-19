import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
import os
from loguru import logger
from openai import AsyncOpenAI
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

from ai_conversation_service.core.config import settings
from ai_conversation_service.models.ai_conversation import (
    Conversation,
    ConversationMessage,
)


class AIConversationService:
    """Service for managing AI conversations with OpenAI integration and S3 storage."""

    def __init__(self):
        self._logger = logger.bind(service="AIConversationService")

        # Initialize OpenAI client
        self.openai_client = None
        try:
            client_kwargs = {"api_key": settings.openai_api_key}

            # Add organization and project if provided
            if settings.openai_organization:
                client_kwargs["organization"] = settings.openai_organization
            if settings.openai_project:
                client_kwargs["project"] = settings.openai_project

            self.openai_client = AsyncOpenAI(**client_kwargs)
            self._logger.info("OpenAI client initialized successfully")
        except Exception as e:
            self._logger.error(f"Failed to initialize OpenAI client: {e}")

        # Initialize S3 client
        self.s3_client = None
        self.bucket_name = f"pami-ai-conversations-{settings.aws_region}"
        try:
            self.s3_client = boto3.client(
                "s3",
                region_name=settings.aws_region,
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
                aws_session_token=settings.aws_session_token,
                config=Config(
                    read_timeout=300, retries={"max_attempts": 3, "mode": "standard"}
                ),
            )
            self._ensure_bucket_exists()
            self._logger.info("S3 client initialized successfully")
        except Exception as e:
            self._logger.error(f"Failed to initialize S3 client: {e}")

        if self.openai_client and self.s3_client:
            self._logger.info("AI Conversation Service initialized successfully")
        else:
            self._logger.warning(
                "AI Conversation Service initialized with limited functionality"
            )

    async def create_conversation(
        self, context_node_id: str, project_id: str, title: Optional[str] = None
    ) -> Conversation:
        """Create a new conversation and save it to S3."""
        conversation_id = str(uuid.uuid4())

        conversation = Conversation(
            conversation_id=conversation_id,
            context_node_id=context_node_id,
            project_id=project_id,
        )

        if title:
            conversation.title = title

        # Save to S3
        await self._save_conversation(conversation)

        self._logger.info(
            f"Created conversation {conversation_id} for node {context_node_id}"
        )
        return conversation

    def _ensure_bucket_exists(self):
        """Ensure the S3 bucket exists, create it if it doesn't."""
        try:
            # Check if bucket exists
            self.s3_client.head_bucket(Bucket=self.bucket_name)
            self._logger.info(f"S3 bucket '{self.bucket_name}' already exists")
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            if error_code == "404" or error_code == "NoSuchBucket":
                # Bucket doesn't exist, create it
                try:
                    if settings.aws_region == "us-east-1":
                        self.s3_client.create_bucket(Bucket=self.bucket_name)
                    else:
                        self.s3_client.create_bucket(
                            Bucket=self.bucket_name,
                            CreateBucketConfiguration={
                                "LocationConstraint": settings.aws_region
                            },
                        )
                    self._logger.info(f"Created S3 bucket '{self.bucket_name}'")
                except Exception as create_error:
                    self._logger.error(
                        f"Failed to create S3 bucket '{self.bucket_name}': {create_error}"
                    )
                    raise
            else:
                self._logger.error(
                    f"Error checking S3 bucket '{self.bucket_name}': {e}"
                )
                raise

    async def _save_conversation(self, conversation: Conversation) -> None:
        """Save a conversation to S3."""
        try:
            if not self.s3_client:
                self._logger.error("S3 client not available")
                return

            # Convert conversation to JSON-serializable format
            conversation_data = {
                "conversation_id": conversation.conversation_id,
                "context_node_id": conversation.context_node_id,
                "project_id": conversation.project_id,
                "title": conversation.title,
                "messages": conversation.messages,
                "created_at": conversation.created_at,
                "updated_at": conversation.updated_at,
                "status": conversation.status,
            }

            key = f"conversations/{conversation.conversation_id}.json"
            self._logger.info(
                f"Saving conversation {conversation.conversation_id} to S3 with key: {key} in bucket: {self.bucket_name}"
            )
            response = self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=json.dumps(conversation_data, indent=2),
                ContentType="application/json",
            )
            self._logger.info(
                f"Successfully saved conversation {conversation.conversation_id} to S3 - ETag: {response.get('ETag', 'N/A')}"
            )
        except Exception as e:
            self._logger.error(
                f"Error saving conversation {conversation.conversation_id}: {e}"
            )
            raise

    async def create_conversation(
        self, context_node_id: str, project_id: str, title: Optional[str] = None
    ) -> Conversation:
        """Create a new conversation for a context node."""
        if not self.openai_client:
            raise Exception("OpenAI client not initialized")

        # Validate input parameters
        if not context_node_id or not project_id:
            raise ValueError("context_node_id and project_id are required")

        conversation_id = str(uuid.uuid4())
        conversation = Conversation(conversation_id, context_node_id, project_id)

        if title:
            # Sanitize title to prevent issues
            title = title.replace("/", "_").replace("\\", "_")[:100]  # Limit length
            conversation.title = title

        # Save the conversation to S3
        await self._save_conversation(conversation)

        self._logger.info(
            f"Created conversation {conversation_id} for node {context_node_id}"
        )
        return conversation

    async def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID from S3."""
        try:
            if not self.s3_client:
                self._logger.error("S3 client not available")
                return None

            key = f"conversations/{conversation_id}.json"
            self._logger.info(
                f"Attempting to get conversation with key: {key} from bucket: {self.bucket_name}"
            )
            response = self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            conversation_data = json.loads(response["Body"].read().decode("utf-8"))

            # Convert stored data back to Conversation object
            conversation = Conversation(
                conversation_id=conversation_data["conversation_id"],
                context_node_id=conversation_data["context_node_id"],
                project_id=conversation_data["project_id"],
            )
            conversation.messages = conversation_data.get("messages", [])
            conversation.created_at = conversation_data.get(
                "created_at", conversation.created_at
            )
            conversation.updated_at = conversation_data.get(
                "updated_at", conversation.updated_at
            )
            conversation.title = conversation_data.get("title", conversation.title)
            conversation.status = conversation_data.get("status", conversation.status)

            self._logger.info(f"Successfully retrieved conversation {conversation_id}")
            return conversation
        except ClientError as e:
            error_code = e.response["Error"]["Code"]
            error_message = e.response["Error"]["Message"]
            self._logger.warning(
                f"Conversation {conversation_id} not found - Error: {error_code} - {error_message}"
            )
            if error_code == "NoSuchKey":
                self._logger.warning(
                    f"Conversation {conversation_id} not found with key: conversations/{conversation_id}.json in bucket: {self.bucket_name}"
                )
                return None
            self._logger.error(f"Error retrieving conversation {conversation_id}: {e}")
            return None
        except Exception as e:
            self._logger.error(
                f"Unexpected error retrieving conversation {conversation_id}: {e}"
            )
            return None

    async def send_message(
        self,
        conversation_id: str,
        user_message: str,
        context_snapshot: Optional[Dict] = None,
    ) -> str:
        """Send a message to the conversation and get AI response."""
        if not self.openai_client:
            raise Exception("OpenAI client not initialized")

        # Load existing conversation or create new one
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            # Create new conversation if it doesn't exist
            conversation = Conversation(
                conversation_id=conversation_id,
                context_node_id="",  # This should be passed in or derived
                project_id="",  # This should be passed in or derived
            )

        # Prepare messages for OpenAI
        messages = []

        # Add context if provided
        if context_snapshot:
            context_text = f"Context: {json.dumps(context_snapshot, indent=2)}"
            messages.append({"role": "system", "content": context_text})

        # Add conversation history
        for msg in conversation.messages:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Add new user message
        user_msg = {
            "role": "user",
            "content": user_message,
            "timestamp": datetime.utcnow().isoformat(),
        }
        messages.append({"role": "user", "content": user_message})
        conversation.messages.append(user_msg)

        # Get AI response
        ai_response = await self._call_openai(messages)

        # Add AI response to conversation
        ai_msg = {
            "role": "assistant",
            "content": ai_response,
            "timestamp": datetime.utcnow().isoformat(),
        }
        conversation.messages.append(ai_msg)
        conversation.updated_at = datetime.utcnow().isoformat()

        # Save updated conversation to S3
        await self._save_conversation(conversation)

        self._logger.info(f"Processed message in conversation {conversation_id}")
        return ai_response

    async def get_conversation_history(
        self, conversation_id: str, limit: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """Get conversation history from S3."""
        try:
            conversation = await self.get_conversation(conversation_id)
            if not conversation:
                return None

            messages = conversation.messages
            if limit:
                messages = messages[-limit:]

            return {
                "conversation_id": conversation.conversation_id,
                "context_node_id": conversation.context_node_id,
                "project_id": conversation.project_id,
                "title": conversation.title,
                "messages": messages,
                "created_at": conversation.created_at,
                "updated_at": conversation.updated_at,
                "status": conversation.status,
            }
        except Exception as e:
            self._logger.error(
                f"Error retrieving conversation history for {conversation_id}: {e}"
            )
            return None

    async def list_conversations_for_node(
        self, context_node_id: str
    ) -> List[Dict[str, Any]]:
        """List all conversations for a context node from S3."""
        try:
            if not self.s3_client:
                self._logger.error("S3 client not available")
                return []

            conversations = []

            # List all conversation objects in the bucket
            paginator = self.s3_client.get_paginator("list_objects_v2")
            page_iterator = paginator.paginate(
                Bucket=self.bucket_name, Prefix="conversations/"
            )

            for page in page_iterator:
                if "Contents" in page:
                    for obj in page["Contents"]:
                        try:
                            # Get the conversation data
                            response = self.s3_client.get_object(
                                Bucket=self.bucket_name, Key=obj["Key"]
                            )
                            conversation_data = json.loads(
                                response["Body"].read().decode("utf-8")
                            )

                            # Filter by context_node_id
                            if (
                                conversation_data.get("context_node_id")
                                == context_node_id
                            ):
                                conversations.append(
                                    {
                                        "conversation_id": conversation_data[
                                            "conversation_id"
                                        ],
                                        "title": conversation_data["title"],
                                        "message_count": len(
                                            conversation_data["messages"]
                                        ),
                                        "created_at": conversation_data["created_at"],
                                        "updated_at": conversation_data["updated_at"],
                                        "status": conversation_data.get(
                                            "status", "active"
                                        ),
                                    }
                                )
                        except Exception as e:
                            self._logger.warning(
                                f"Error processing conversation {obj['Key']}: {e}"
                            )
                            continue

            # Sort by updated_at descending
            conversations.sort(key=lambda x: x["updated_at"], reverse=True)

            self._logger.info(
                f"Found {len(conversations)} conversations for node {context_node_id}"
            )
            return conversations

        except Exception as e:
            self._logger.error(
                f"Error listing conversations for node {context_node_id}: {e}"
            )
            return []

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation from S3."""
        try:
            if not self.s3_client:
                self._logger.error("S3 client not available")
                return False

            key = f"conversations/{conversation_id}.json"
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)

            self._logger.info(f"Deleted conversation {conversation_id} from S3")
            return True

        except ClientError as e:
            if e.response["Error"]["Code"] == "NoSuchKey":
                self._logger.warning(
                    f"Conversation {conversation_id} not found for deletion"
                )
                return True  # Consider it successful if it doesn't exist
            self._logger.error(f"Error deleting conversation {conversation_id}: {e}")
            return False
        except Exception as e:
            self._logger.error(
                f"Unexpected error deleting conversation {conversation_id}: {e}"
            )
            return False

    async def _call_openai(self, messages: List[Dict[str, Any]]) -> str:
        """Call OpenAI with conversation messages."""
        try:
            response = await self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=messages,
                max_tokens=2000,
                temperature=0.7,
            )

            ai_response = response.choices[0].message.content
            return ai_response

        except Exception as e:
            error_msg = f"OpenAI API Error: {str(e)}"
            self._logger.error(f"OpenAI call failed: {error_msg}")
            return f"I apologize, but I'm having trouble responding right now. OpenAI Error: {str(e)}"

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (1 token ≈ 4 characters for English)."""
        return len(text) // 4
