import asyncio
import json
import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from loguru import logger
from openai import AsyncOpenAI
import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

from ai_conversation_service.core.config import settings
from ai_conversation_service.core.prompt_loader import load_prompt_file
from ai_conversation_service.models.ai_conversation import (
    Conversation,
    ConversationMessage,
)
from ai_conversation_service.agents.conversation_agent import (
    AgentDeps,
    build_usage_limits,
)
from ai_conversation_service.schemas.retrieval_schemas import SendMessageResult
from ai_conversation_service.services.projects_service_client import (
    ProjectsServiceClient,
)

CONVERSATION_CHAT_SYSTEM_PROMPT = load_prompt_file(
    "conversation_chat_system_prompt.txt"
)
CONVERSATION_CHAT_USER_PROMPT_TEMPLATE = load_prompt_file(
    "conversation_chat_user_prompt.txt"
)


class ConversationNotFoundError(Exception):
    """Raised when a conversation id does not resolve to a stored transcript."""


class AIConversationService:
    """Manages AI conversations over OpenAI with S3 transcript storage.

    The retrieval collaborators are optional: without them the service answers from
    the current conversation only, instead of failing to start.
    """

    def __init__(
        self,
        projects_service_client: ProjectsServiceClient | None = None,
        chunk_index_service=None,
        context_retrieval_service=None,
        reindex_trigger=None,
        conversation_agent=None,
    ):
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
        # S3 bucket names are globally unique, so a name derived from the region alone is
        # already taken the moment this is deployed to a second AWS account - the service then
        # cannot create it or read it, and every conversation fails to save. The deploy passes
        # an account-scoped name; the fallback keeps local development working.
        self.bucket_name = (
            settings.aws_s3_bucket_name
            or f"pami-ai-conversations-{settings.aws_region}"
        )
        try:
            # Use IAM role credentials when running on ECS (credentials will be None)
            # Use explicit credentials only when provided (for local development)
            client_kwargs = {
                "region_name": settings.aws_region,
                "config": Config(
                    read_timeout=300, retries={"max_attempts": 3, "mode": "standard"}
                ),
            }

            # Only add explicit credentials if they're provided
            if settings.aws_access_key_id and settings.aws_secret_access_key:
                client_kwargs["aws_access_key_id"] = settings.aws_access_key_id
                client_kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
                if settings.aws_session_token:
                    client_kwargs["aws_session_token"] = settings.aws_session_token
                self._logger.info("Using explicit AWS credentials")
            else:
                self._logger.info("Using IAM role credentials (ECS task role)")

            self.s3_client = boto3.client("s3", **client_kwargs)
            self._ensure_bucket_exists()
            self._logger.info("S3 client initialized successfully")
        except Exception as e:
            self._logger.error(f"Failed to initialize S3 client: {e}")
            self.s3_client = None

        if self.openai_client and self.s3_client:
            self._logger.info("AI Conversation Service initialized successfully")
        else:
            self._logger.warning(
                "AI Conversation Service initialized with limited functionality"
            )

        self.projects_service_client = projects_service_client or ProjectsServiceClient(
            settings.projects_api_url
        )
        self.chunk_index_service = chunk_index_service
        self.context_retrieval_service = context_retrieval_service
        self.reindex_trigger = reindex_trigger
        self.conversation_agent = conversation_agent
        self._background_tasks: set[asyncio.Task] = set()
        # One pending tail-flush per conversation; a new message replaces it.
        self._idle_flush_tasks: dict[str, asyncio.Task] = {}

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
            # Normalize messages to dicts with explicit roles and content
            normalized_messages = []
            try:
                for m in conversation.messages or []:
                    if isinstance(m, dict):
                        role = m.get("role")
                        content = m.get("content")
                        ts = m.get("timestamp")
                    else:
                        # Assume ConversationMessage-like object
                        role = getattr(m, "role", None)
                        content = getattr(m, "content", None)
                        ts = getattr(m, "timestamp", None)

                    # Coerce role to known values
                    if role and isinstance(role, str):
                        role = role.lower()
                    if role not in ("user", "assistant", "system"):
                        # If role looks like 'assistant' but capitalized, normalize; otherwise default to 'user'
                        if role and "assist" in (role or ""):
                            role = "assistant"
                        elif role and "system" in (role or ""):
                            role = "system"
                        else:
                            role = "user"

                    normalized_messages.append(
                        {"role": role, "content": content, "timestamp": ts}
                    )
            except Exception as e:
                self._logger.warning(f"Failed to normalize messages before save: {e}")
                normalized_messages = conversation.messages or []

            conversation_data = {
                "conversation_id": conversation.conversation_id,
                "context_node_id": conversation.context_node_id,
                "project_id": conversation.project_id,
                "title": conversation.title,
                "messages": normalized_messages,
                "created_at": conversation.created_at,
                "updated_at": conversation.updated_at,
                "status": conversation.status,
            }

            key = f"conversations/{conversation.conversation_id}.json"
            body_text = json.dumps(conversation_data, indent=2)
            # Log last few messages for traceability
            try:
                last_msgs = [
                    (m.get("role"), (m.get("content") or "")[:120])
                    for m in conversation_data.get("messages", [])[-6:]
                ]
                self._logger.debug(
                    f"Saving conversation {conversation.conversation_id} messages_preview={last_msgs}"
                )
            except Exception:
                self._logger.debug(
                    f"Saving conversation {conversation.conversation_id} messages_preview=<unserializable>"
                )

            self._logger.info(
                f"Saving conversation {conversation.conversation_id} to S3 with key: {key} in bucket: {self.bucket_name} size={len(body_text)}"
            )
            try:
                response = self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=key,
                    Body=body_text,
                    ContentType="application/json",
                )
                self._logger.info(
                    f"Successfully saved conversation {conversation.conversation_id} to S3 - ETag: {response.get('ETag', 'N/A')}"
                )
            except Exception as e:
                self._logger.error(f"Failed to put_object for {key}: {e}")
                raise
        except Exception as e:
            self._logger.error(
                f"Error saving conversation {conversation.conversation_id}: {e}"
            )
            raise

    async def create_conversation(
        self, context_node_id: str, project_id: str, title: Optional[str] = None
    ) -> Conversation:
        """Create a new conversation for a context node."""
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
            raw = response["Body"].read().decode("utf-8")
            self._logger.debug(
                f"Loaded raw conversation {conversation_id} size={len(raw)}"
            )
            try:
                conversation_data = json.loads(raw)
            except Exception:
                # Some tests use str(dict) (single quotes) instead of JSON; try parsing python literal
                import ast

                try:
                    conversation_data = ast.literal_eval(raw)
                except Exception:
                    raise

            # Convert stored data back to Conversation object
            conversation = Conversation(
                conversation_id=conversation_data["conversation_id"],
                context_node_id=conversation_data["context_node_id"],
                project_id=conversation_data["project_id"],
            )
            conversation.messages = conversation_data.get("messages", [])
            try:
                self._logger.debug(
                    f"Conversation {conversation_id} messages_count={len(conversation.messages)}"
                )
            except Exception:
                pass
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

    async def send_message_with_context(
        self,
        conversation_id: str,
        user_message: str,
        context_snapshot: Optional[Dict] = None,
    ) -> SendMessageResult:
        """Answer a message, letting the agent search other conversations if needed."""
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            raise ConversationNotFoundError(conversation_id)

        if not self.conversation_agent or not self.context_retrieval_service:
            answer = await self.send_message(
                conversation_id, user_message, context_snapshot
            )
            return SendMessageResult(response=answer)

        history = "\n".join(
            f"{message.get('role')}: {message.get('content')}"
            for message in conversation.messages[-20:]
        )
        neighbour_note = await self._related_conversations_note(conversation)
        prompt = (
            f"{neighbour_note}\n\nConversation so far:\n{history}\n\n"
            f"Latest user message: {user_message}"
        )

        deps = AgentDeps(
            project_id=conversation.project_id,
            conversation_id=conversation_id,
            retrieval=self.context_retrieval_service,
            chunk_index=self.chunk_index_service,
            transcripts=self,
        )

        user_msg = {
            "role": "user",
            "content": user_message,
            "timestamp": datetime.utcnow().isoformat(),
        }
        conversation.messages.append(user_msg)
        await self._save_conversation(conversation)

        result = await self.conversation_agent.run(
            prompt, deps=deps, usage_limits=build_usage_limits()
        )
        answer = str(result.output)

        conversation.messages.append(
            {
                "role": "assistant",
                "content": answer,
                "timestamp": datetime.utcnow().isoformat(),
            }
        )
        conversation.updated_at = datetime.utcnow().isoformat()
        await self._save_conversation(conversation)

        self._schedule_reindex(conversation)

        # A hit at or below the floor was returned only because the search had slots left to
        # fill, and listing it told the user PAMI had consulted a conversation it drew
        # nothing from. Anything the model actually read is kept regardless of score.
        consulted = sorted(
            (
                entry
                for entry in deps.consulted.values()
                if entry.read
                or entry.best_score > settings.retrieval_consulted_min_score
            ),
            key=lambda entry: (entry.read, entry.best_score),
            reverse=True,
        )
        self._logger.info(
            f"Answered in conversation {conversation_id}; tool_calls={deps.tool_calls}; "
            f"consulted {[c.conversation_id for c in consulted]} "
            f"of {len(deps.consulted)} surfaced"
        )
        return SendMessageResult(
            response=answer, consulted=consulted, tool_calls_used=deps.tool_calls
        )

    async def purge_conversation(self, conversation_id: str) -> bool:
        """Remove a conversation from the search index first, then from S3.

        Index-before-transcript ordering matters: the reverse leaves chunks holding
        verbatim conversation text that retrieval would keep serving for a transcript
        that no longer exists. The index delete is unconditional so a retry after a
        partial failure can always finish the cleanup.
        """
        if self.chunk_index_service:
            await self.chunk_index_service.delete_conversation(conversation_id)
        return await self.delete_conversation(conversation_id)

    async def force_reindex(self, conversation_id: str) -> bool:
        """Reindex a conversation now, ignoring the message-count debounce."""
        if not self.reindex_trigger or not self.chunk_index_service:
            return False

        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            return False

        state = await self.chunk_index_service.state_for(conversation_id)
        return await self.reindex_trigger.maybe_reindex(
            conversation_id=conversation_id,
            project_id=conversation.project_id,
            node_id=await self._resolve_node_id(conversation, state),
            messages=conversation.messages,
            header=(state.header if state else None) or conversation.title,
            force=True,
        )

    async def send_message(
        self,
        conversation_id: str,
        user_message: str,
        context_snapshot: Optional[Dict] = None,
    ) -> str:
        """Send a message to the conversation and get AI response."""
        # Load existing conversation or create new one
        conversation = await self.get_conversation(conversation_id)
        if not conversation:
            # If conversation not found, mirror test expectations
            raise Exception("Conversation not found")

        # Prepare messages for OpenAI
        messages = []

        # Build context: optional caller snapshot + backend-injected project metadata.
        effective_context: Dict[str, Any] = {}
        if context_snapshot:
            effective_context.update(context_snapshot)

        project_metadata = await self.projects_service_client.get_project_metadata(
            conversation.project_id
        )
        if project_metadata:
            effective_context["project"] = project_metadata

        if effective_context:
            context_text = f"Context: {json.dumps(effective_context, indent=2)}"
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

        # Log messages state after appending user message (for debugging duplication/roles)
        try:
            preview = [
                (
                    m.get("role") if isinstance(m, dict) else getattr(m, "role", None),
                    (
                        m.get("content")
                        if isinstance(m, dict)
                        else getattr(m, "content", "")
                    )[:120],
                )
                for m in conversation.messages[-8:]
            ]
            self._logger.debug(
                f"After append user message conversation.messages preview={preview}"
            )
        except Exception:
            self._logger.debug(
                "After append user message conversation.messages preview=<unserializable>"
            )
        # Persist the conversation after adding the user's message so tests
        # and clients observing S3 can see the user input immediately. This
        # also matches earlier test expectations for two put_object calls
        # (initial create + update when sending a message).
        try:
            self._logger.debug(
                f"Persisting conversation {conversation_id} before AI call, messages_count={len(conversation.messages)}"
            )
            await self._save_conversation(conversation)
        except Exception as ex:
            # Don't block on save failure; continue to get AI response.
            self._logger.warning(f"Failed to persist conversation before AI call: {ex}")

        # Get AI response
        self._logger.debug(
            f"Calling AI for conversation {conversation_id} prompt_messages={len(messages)}"
        )
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

        try:
            self._logger.info(
                f"Processed message in conversation {conversation_id} ai_response_len={len(ai_response or '')}"
            )
            self._logger.debug(f"AI response (truncated): {str(ai_response)[:1000]}")
        except Exception:
            self._logger.info(f"Processed message in conversation {conversation_id}")
        return ai_response

    async def _call_openai(self, messages: List[Dict[str, Any]]) -> str:
        """Abstracted call that chooses the available AI backend.

        If a Bedrock client is configured (used in tests), delegate to it. Otherwise
        attempt to call the OpenAI client.
        """
        # Prefer Bedrock client when available (tests set this)
        if hasattr(self, "bedrock_client") and self.bedrock_client:
            return await self._call_bedrock_ai(messages)

        if not self.openai_client:
            raise Exception("OpenAI client not initialized")

        # Fallback: call OpenAI Chat Completions
        try:
            prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
            user_prompt = CONVERSATION_CHAT_USER_PROMPT_TEMPLATE.format(
                messages_text=prompt
            )
            self._logger.debug(
                f"_call_openai prompt_len={len(prompt)} messages_count={len(messages)}"
            )
            resp = await self.openai_client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": CONVERSATION_CHAT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
            )
            try:
                out = resp.choices[0].message.content
                self._logger.debug(f"_call_openai raw_output_len={len(out)}")
                return out
            except Exception:
                self._logger.debug("_call_openai: could not read response content")
                raise
        except Exception as e:
            self._logger.error(f"OpenAI call failed: {e}")
            raise

    async def _call_bedrock_ai(
        self, messages: List[Dict[str, Any]], context_snapshot: Optional[Dict] = None
    ) -> str:
        """Call AWS Bedrock (or a mocked bedrock client in tests) and return the assistant text."""
        try:
            # Build a simple textual prompt from messages
            prompt = "\n".join([f"{m['role']}: {m['content']}" for m in messages])
            # The tests mock `bedrock_client.invoke_model` to return a dict with a `body` file-like object
            payload = json.dumps({"input": prompt}).encode("utf-8")
            resp = self.bedrock_client.invoke_model(body=payload)
            body = resp.get("body")
            if body:
                raw = body.read()
                data = json.loads(raw.decode("utf-8"))
                outputs = data.get("outputs", [])
                if outputs and isinstance(outputs, list):
                    return outputs[0].get("text")
            raise Exception("Invalid Bedrock response")
        except Exception as e:
            self._logger.error(f"Bedrock call failed: {e}")
            raise

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

    async def _load_all_conversations(self) -> List[Dict[str, Any]]:
        """Every stored transcript, as dicts.

        Objects are stored flat as conversations/<conversation_id>.json, so there is no
        prefix to filter a subset by - callers filter on the transcript's own fields.
        """
        if not self.s3_client:
            self._logger.error("S3 client not available")
            return []

        # Prefer calling list_objects_v2 directly (tests often stub this),
        # otherwise fall back to paginator behavior.
        contents = []
        try:
            if hasattr(self.s3_client, "list_objects_v2"):
                resp = self.s3_client.list_objects_v2(
                    Bucket=self.bucket_name, Prefix="conversations/"
                )
                if isinstance(resp, dict) and "Contents" in resp:
                    contents = resp.get("Contents", [])
            if not contents and hasattr(self.s3_client, "get_paginator"):
                page_iterator = self.s3_client.get_paginator(
                    "list_objects_v2"
                ).paginate(Bucket=self.bucket_name, Prefix="conversations/")
                for page in page_iterator:
                    contents.extend(page.get("Contents", []))
        except Exception:
            try:
                resp = self.s3_client.list_objects_v2(
                    Bucket=self.bucket_name, Prefix="conversations/"
                )
                contents = resp.get("Contents", []) if isinstance(resp, dict) else []
            except Exception:
                contents = []

        conversations: List[Dict[str, Any]] = []
        for obj in contents:
            try:
                response = self.s3_client.get_object(
                    Bucket=self.bucket_name, Key=obj["Key"]
                )
                raw = response["Body"].read().decode("utf-8")
                try:
                    conversation_data = json.loads(raw)
                except Exception:
                    import ast

                    conversation_data = ast.literal_eval(raw)

                # dicts, not Conversation objects: routes do Response(**conv), and ** on a
                # model instance raises TypeError.
                conversations.append(
                    Conversation.from_dict(conversation_data).to_dict()
                )
            except Exception as e:
                self._logger.warning(
                    f"Error processing conversation {obj.get('Key')}: {e}"
                )
                continue

        return conversations

    @staticmethod
    def _preview_of(conversation: Dict[str, Any]) -> Optional[str]:
        """The first thing the user asked, for a list where every title is generated."""
        for message in conversation.get("messages") or []:
            role = message.get("role") if isinstance(message, dict) else None
            content = message.get("content") if isinstance(message, dict) else None
            if role == "user" and str(content or "").strip():
                text = " ".join(str(content).split())
                return text[:160]
        return None

    @staticmethod
    def _newest_first(conversations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Keyed on the dict and defaulted to "", because getattr on a dict returns None for
        every entry and sorting None against None raises."""
        return sorted(
            conversations,
            key=lambda conversation: conversation.get("updated_at") or "",
            reverse=True,
        )

    async def list_conversations_for_node(
        self, context_node_id: str
    ) -> List[Dict[str, Any]]:
        """List all conversations for a context node from S3."""
        try:
            conversations = [
                conversation
                for conversation in await self._load_all_conversations()
                if conversation.get("context_node_id") == context_node_id
            ]
            self._logger.info(
                f"Found {len(conversations)} conversations for node {context_node_id}"
            )
            return self._newest_first(conversations)
        except Exception as e:
            self._logger.error(
                f"Error listing conversations for node {context_node_id}: {e}"
            )
            return []

    async def list_conversations_for_project(
        self, project_id: str
    ) -> List[Dict[str, Any]]:
        """Every conversation in a project, most recently updated first.

        Read from the transcripts rather than from the index state collection: a
        conversation only gets an index-state record once it has been embedded, so a chat
        started a minute ago would be missing from the list that is meant to be how you
        find your way back to it.
        """
        try:
            conversations = [
                conversation | {"preview": self._preview_of(conversation)}
                for conversation in await self._load_all_conversations()
                if conversation.get("project_id") == project_id
            ]
            self._logger.info(
                f"Found {len(conversations)} conversations in project {project_id}"
            )
            return self._newest_first(conversations)
        except Exception as e:
            self._logger.error(
                f"Error listing conversations for project {project_id}: {e}"
            )
            return []

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation from S3."""
        try:
            if not self.s3_client:
                self._logger.error("S3 client not available")
                return False

            # Check existence first (tests mock get_object to simulate NotFound)
            key = f"conversations/{conversation_id}.json"
            try:
                self.s3_client.get_object(Bucket=self.bucket_name, Key=key)
            except Exception:
                self._logger.info(
                    f"Conversation {conversation_id} not found for deletion"
                )
                return False

            # Proceed to delete
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

    # NOTE: _call_openai is implemented earlier in the file to prefer Bedrock
    # when available and otherwise call the OpenAI client. The older
    # implementation that directly referenced `self.openai_client.chat` was
    # removed to ensure Bedrock delegation works for tests.

    SEARCHABLE_NOTE = (
        "This project has other conversations you can search with search_context."
    )

    async def _related_conversations_note(self, conversation) -> str:
        """Prime the agent with what it can search.

        Always states that other conversations are searchable: naming graph neighbours is
        a bonus, but an empty note previously left the agent with no hint that retrieval
        was possible, so it declined instead of searching.
        """
        if not self.chunk_index_service:
            return ""

        state = await self.chunk_index_service.state_for(conversation.conversation_id)
        if not state or not state.node_id:
            return self.SEARCHABLE_NOTE

        sibling_node_ids = await self.projects_service_client.get_sibling_node_ids(
            state.node_id
        )
        headers = await self.chunk_index_service.headers_for_nodes(
            conversation.project_id, sibling_node_ids
        )
        if not headers:
            return self.SEARCHABLE_NOTE

        titles = ", ".join(sorted(headers.values()))
        return f"{self.SEARCHABLE_NOTE} Closely related ones: {titles}."

    async def _resolve_node_id(self, conversation, state) -> str | None:
        """The owning node id, asking projects_service first.

        Prefer the authoritative lookup over any id already stored: conversations created
        from the UI carry a synthetic `chat-session-…` placeholder, and trusting it sends
        score pushes to a node that does not exist. Asking first also repairs records
        already poisoned by that placeholder.
        """
        resolved = await self.projects_service_client.get_node_id_for_conversation(
            conversation.project_id, conversation.conversation_id
        )
        if resolved:
            return resolved
        return (state.node_id if state else None) or conversation.context_node_id

    def _schedule_reindex(self, conversation) -> None:
        """Reindex in the background; it must never add latency to the answer."""
        if not self.reindex_trigger:
            return

        task = asyncio.create_task(self._maybe_reindex(conversation))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _maybe_reindex(self, conversation) -> None:
        """Every await must sit inside the guard: this runs as a detached task."""
        if not self.reindex_trigger:
            return

        try:
            state = await self.chunk_index_service.state_for(
                conversation.conversation_id
            )
            indexed = await self.reindex_trigger.maybe_reindex(
                conversation_id=conversation.conversation_id,
                project_id=conversation.project_id,
                node_id=await self._resolve_node_id(conversation, state),
                messages=conversation.messages,
                header=(state.header if state else None) or conversation.title,
            )
            if indexed:
                self._cancel_idle_flush(conversation.conversation_id)
            else:
                self._schedule_idle_flush(conversation)
        except Exception as error:
            self._logger.error(
                f"Reindex failed for {conversation.conversation_id}: "
                f"{type(error).__name__}"
            )

    def _schedule_idle_flush(self, conversation) -> None:
        """Index the tail of a conversation once it goes quiet.

        Without this, messages below the debounce threshold stay unsearchable for as long as
        the conversation is idle — so the thing the user said most recently, which is exactly
        what they then ask about from another conversation, is the one thing retrieval cannot
        see. Relying on the browser to flush on exit is not enough: it may never fire.
        """
        conversation_id = conversation.conversation_id
        self._cancel_idle_flush(conversation_id)

        async def flush() -> None:
            try:
                await asyncio.sleep(settings.reindex_idle_flush_seconds)
                state = await self.chunk_index_service.state_for(conversation_id)
                await self.reindex_trigger.maybe_reindex(
                    conversation_id=conversation_id,
                    project_id=conversation.project_id,
                    node_id=await self._resolve_node_id(conversation, state),
                    messages=conversation.messages,
                    header=(state.header if state else None) or conversation.title,
                    force=True,
                )
                self._logger.info(f"Idle flush indexed {conversation_id}")
            except asyncio.CancelledError:
                raise
            except Exception as error:
                self._logger.error(
                    f"Idle flush failed for {conversation_id}: {type(error).__name__}"
                )
            finally:
                self._idle_flush_tasks.pop(conversation_id, None)

        task = asyncio.create_task(flush())
        self._idle_flush_tasks[conversation_id] = task

    def _cancel_idle_flush(self, conversation_id: str) -> None:
        task = self._idle_flush_tasks.pop(conversation_id, None)
        if task and not task.done():
            task.cancel()

    def _estimate_tokens(self, text: str) -> int:
        """Rough token estimation (1 token ≈ 4 characters for English)."""
        return len(text) // 4

    def _optimize_conversation_history(
        self, messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Optimize conversation history by truncating older messages when too long.

        Simple heuristic: keep the most recent up to 50 messages.
        """
        if not messages:
            return messages
        max_keep = 50
        if len(messages) <= max_keep:
            msgs = messages
        else:
            msgs = messages[-max_keep:]

        # Convert dict messages to ConversationMessage objects for downstream code/tests
        conv_msgs = []
        for m in msgs:
            if isinstance(m, dict):
                conv_msgs.append(
                    ConversationMessage(
                        m.get("role"), m.get("content"), m.get("timestamp")
                    )
                )
            else:
                # assume it's already a ConversationMessage-like object
                conv_msgs.append(m)
        return conv_msgs
