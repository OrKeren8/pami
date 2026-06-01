from typing import List, Optional
from datetime import datetime
from loguru import logger
import uuid
import aiohttp
import traceback

from projects_service.data.context_tree_repository import ContextTreeRepository
from projects_service.models.context_tree import ContextTreeNode
from projects_service.schemas.context_tree_schemas import (
    CreateContextTreeNodeRequest,
    UpdateContextTreeNodeRequest,
    ContextTreeNodeResponse,
)
from projects_service.core.config import settings


class AIOrganizationError(Exception):
    """Raised when the AI organization service fails to provide a usable response."""


class ContextTreeService:
    """Service for context tree business logic."""

    def __init__(self, context_tree_repository: ContextTreeRepository):
        self._logger = logger.bind(service="ContextTreeService")
        self._context_tree_repository = context_tree_repository

    async def create_node(
        self, project_id: str, request: CreateContextTreeNodeRequest
    ) -> ContextTreeNodeResponse:
        """Create a new context tree node."""
        # Log incoming request for traceability
        try:
            self._logger.debug(
                f"create_node called: project_id={project_id} request={request.dict()}"
            )
        except Exception:
            self._logger.debug(
                f"create_node called: project_id={project_id} request=<unserializable>"
            )
        # Create domain model from request
        node = ContextTreeNode(
            parent_id=request.parent_id,
            children_ids=request.children_ids,
            header=request.header,
            summary=request.summary,
            topics=request.topics,
            project_id=project_id,
            node_type=request.node_type,
            color=request.color,
        )
        created_node = await self._context_tree_repository.create(node)
        self._logger.info(
            f"Created node in DB with id={created_node.id} (type={type(created_node.id)})"
        )
        # Log created node snapshot
        try:
            self._logger.debug(
                f"Created node snapshot: id={created_node.id} header={created_node.header} summary_len={len(created_node.summary or '')} topics={created_node.topics} parent_id={created_node.parent_id}"
            )
        except Exception:
            self._logger.debug(
                f"Created node snapshot: id={created_node.id} <unserializable fields>"
            )

        # If the request provided an existing conversation_id, reuse it instead
        req_conv = getattr(request, "conversation_id", None)
        if req_conv:
            created_node.conversation_id = req_conv
            self._logger.info(
                f"Using provided conversation_id {req_conv} for node {created_node.id}"
            )
            # Persist conversation_id (best-effort)
            try:
                try:
                    created_node.conversation_id = req_conv
                    await created_node.save()
                    self._logger.debug(
                        f"Persisted provided conversation_id {req_conv} on node {created_node.id}"
                    )
                except TypeError:
                    await self._context_tree_repository.update(
                        str(created_node.id), {"conversation_id": req_conv}
                    )
                    self._logger.debug(
                        f"Updated repository with provided conversation_id {req_conv} for node {created_node.id}"
                    )
            except Exception as e:
                self._logger.warning(
                    f"Could not persist provided conversation_id for node {created_node.id}: {e}"
                )

            # Schedule AI organization using the provided conversation id
            try:
                import asyncio

                asyncio.create_task(
                    self._ai_organize_node(created_node, project_id, req_conv)
                )
                self._logger.debug(
                    f"Scheduled background AI organize for node {created_node.id} conv={req_conv}"
                )
            except Exception:
                await self._ai_organize_node(
                    created_node, project_id, req_conv, raise_on_no_response=True
                )
        else:
            # Create AI conversation for this node
            conversation_id = await self._create_ai_conversation(
                str(created_node.id), project_id
            )
            if conversation_id:
                # Associate conversation_id with the created node in-memory. Persistence
                # is intentionally left to the repository layer or later operations
                # to avoid requiring DB save semantics during unit tests.
                created_node.conversation_id = conversation_id
                self._logger.info(
                    f"Created AI conversation {conversation_id} for node {created_node.id}"
                )
                # Attempt to persist conversation_id to node for easier tracing (best-effort)
                try:
                    try:
                        created_node.conversation_id = conversation_id
                        await created_node.save()
                        self._logger.debug(
                            f"Persisted conversation_id {conversation_id} on node {created_node.id}"
                        )
                    except TypeError:
                        await self._context_tree_repository.update(
                            str(created_node.id), {"conversation_id": conversation_id}
                        )
                        self._logger.debug(
                            f"Updated repository with conversation_id {conversation_id} for node {created_node.id}"
                        )
                except Exception as e:
                    self._logger.warning(
                        f"Could not persist conversation_id for node {created_node.id}: {e}"
                    )

                # Seed the AI conversation with the node's summary/header so tree-analysis
                # has content to analyze. If no explicit summary provided, use header or
                # a brief auto-generated note. Failures here should not block node creation.
                try:
                    seed_message = None
                    if getattr(request, "summary", None):
                        seed_message = request.summary
                    elif getattr(request, "header", None):
                        seed_message = f"Title: {request.header}"
                    else:
                        seed_message = f"New node created with id {created_node.id}"

                    async with aiohttp.ClientSession() as session:
                        seed_url = f"{settings.ai_service_url}/ai-conversations/{conversation_id}/messages"
                        seed_payload = {
                            "message": seed_message,
                            "context_snapshot": {"project_id": project_id},
                        }
                        self._logger.debug(
                            f"Seeding AI conversation: url={seed_url} payload={seed_payload}"
                        )
                        async with session.post(
                            seed_url, json=seed_payload
                        ) as seed_resp:
                            seed_status = seed_resp.status
                            seed_body = await seed_resp.text()
                            self._logger.debug(
                                f"Seed response status={seed_status} body={seed_body}"
                            )
                except Exception as e:
                    self._logger.warning(
                        f"Failed to seed AI conversation for node {created_node.id}: {e}"
                    )

                # Let AI organize the node in the tree asynchronously (don't block create)
                try:
                    import asyncio

                    # Schedule background organization and log scheduling
                    asyncio.create_task(
                        self._ai_organize_node(
                            created_node, project_id, conversation_id
                        )
                    )
                    self._logger.debug(
                        f"Scheduled background AI organize for node {created_node.id} conv={conversation_id}"
                    )
                except Exception:
                    # If background scheduling fails, fall back to synchronous call
                    await self._ai_organize_node(
                        created_node,
                        project_id,
                        conversation_id,
                        raise_on_no_response=True,
                    )

        # If the node has a parent, update the parent's children list
        if request.parent_id:
            parent_node = await self._context_tree_repository.get_by_id(
                request.parent_id
            )
            if parent_node:
                # Add the new child to parent's children_ids if not already present
                child_id_str = str(created_node.id)
                if child_id_str not in parent_node.children_ids:
                    parent_node.children_ids.append(child_id_str)
                    try:
                        await parent_node.save()
                    except TypeError:
                        await self._context_tree_repository.update(
                            str(parent_node.id),
                            {"children_ids": parent_node.children_ids},
                        )
                    self._logger.info(
                        f"Updated parent {request.parent_id} to include child {child_id_str}"
                    )

        # Ensure color and conversation_id are proper strings or None (tests may use MagicMock)
        color_val = getattr(created_node, "color", None)
        color = color_val if isinstance(color_val, str) else None
        conv_val = getattr(created_node, "conversation_id", None)
        conv = conv_val if isinstance(conv_val, str) else None

        return ContextTreeNodeResponse(
            id=str(created_node.id),
            parent_id=created_node.parent_id,
            children_ids=created_node.children_ids,
            header=created_node.header,
            color=color,
            summary=created_node.summary,
            topics=created_node.topics,
            project_id=created_node.project_id,
            node_type=created_node.node_type,
            conversation_id=conv,
            created_at=created_node.created_at,
            updated_at=created_node.updated_at,
        )

    async def _create_ai_conversation(
        self, context_node_id: str, project_id: str
    ) -> Optional[str]:
        """Create an AI conversation for a context node."""
        try:
            url = f"{settings.ai_service_url}/ai-conversations/"
            payload = {
                "context_node_id": context_node_id,
                "project_id": project_id,
                "title": f"AI Discussion - Node {context_node_id[:8]}",
            }
            self._logger.debug(
                f"Calling AI create conversation: url={url} payload={payload}"
            )
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload) as response:
                    status = response.status
                    body = await response.text()
                    self._logger.debug(
                        f"AI create_conversation response status={status} body={body}"
                    )
                    if 200 <= status < 300:
                        try:
                            return (await response.json()).get("conversation_id")
                        except Exception:
                            self._logger.error(
                                f"Failed to parse create_conversation JSON: {traceback.format_exc()}"
                            )
                            return None
                    else:
                        self._logger.error(
                            f"Failed to create AI conversation: {status} - {body}"
                        )
                        return None
        except Exception as e:
            self._logger.error(
                f"Error calling AI service: {e}\n{traceback.format_exc()}"
            )
            return None

    async def _ai_organize_node(
        self,
        node: ContextTreeNode,
        project_id: str,
        conversation_id: str,
        raise_on_no_response: bool = False,
    ) -> None:
        """Request AI to analyze and organize node in the tree."""
        try:
            self._logger.debug(
                f"_ai_organize_node start: node={node.id} project_id={project_id} conversation_id={conversation_id} current_summary_len={len(node.summary or '')}"
            )
            # Get all nodes in the project for context
            all_nodes = await self._context_tree_repository.list_by_project(project_id)

            # Build tree context (exclude the current node since it's new)
            tree_context = [
                {
                    "id": str(n.id),
                    "parent_id": n.parent_id,
                    "header": n.header,
                    "summary": n.summary,
                    "topics": n.topics,
                    "node_type": n.node_type,
                }
                for n in all_nodes
                if str(n.id) != str(node.id)
            ]

            async with aiohttp.ClientSession() as session:
                url = f"{settings.ai_service_url}/tree-analysis/organize-node"
                payload = {
                    "node_id": str(node.id),
                    "conversation_id": conversation_id,
                    "current_tree": tree_context,
                }
                self._logger.debug(
                    f"Calling AI tree-analysis: url={url} payload_summary={{'node_id': payload['node_id'], 'conversation_id': payload['conversation_id'], 'current_tree_len': {len(tree_context)}}}"
                )
                async with session.post(url, json=payload) as response:
                    status = response.status
                    raw_body = await response.text()
                    self._logger.debug(
                        f"AI tree-analysis response status={status} body={raw_body}"
                    )
                    if 200 <= status < 300:
                        try:
                            ai_suggestion = await response.json()
                            self._logger.debug(f"Parsed AI suggestion: {ai_suggestion}")
                        except Exception:
                            self._logger.error(
                                f"Failed to parse tree-analysis JSON: {traceback.format_exc()}"
                            )
                            ai_suggestion = {}
                        # If AI returned an empty suggestion and the caller requested
                        # to be notified, raise an error so upstream callers can
                        # surface this to users instead of silently continuing.
                        if raise_on_no_response and (
                            not ai_suggestion or len(ai_suggestion) == 0
                        ):
                            raise AIOrganizationError(
                                f"AI tree-analysis returned no suggestion for node {node.id}"
                            )
                        self._logger.info(
                            f"AI suggested organization for node {node.id}: {ai_suggestion.get('reasoning') or 'NO_REASONING'}"
                        )

                        # Update node with AI suggestions
                        node.summary = ai_suggestion.get("summary", node.summary)
                        node.topics = ai_suggestion.get("topics", node.topics)

                        # Respect AI-provided header if present; do not derive a fallback locally.
                        node.header = ai_suggestion.get("header", node.header)
                        suggested_parent = ai_suggestion.get("suggested_parent_id")

                        # Update parent if AI suggests a different one
                        if suggested_parent and suggested_parent != node.parent_id:
                            # Remove from old parent's children
                            if node.parent_id:
                                old_parent = (
                                    await self._context_tree_repository.get_by_id(
                                        node.parent_id
                                    )
                                )
                                if (
                                    old_parent
                                    and str(node.id) in old_parent.children_ids
                                ):
                                    old_parent.children_ids.remove(str(node.id))
                                    try:
                                        await old_parent.save()
                                    except TypeError:
                                        await self._context_tree_repository.update(
                                            str(old_parent.id),
                                            {"children_ids": old_parent.children_ids},
                                        )

                            # Set new parent
                            node.parent_id = suggested_parent

                            # Add to new parent's children
                            new_parent = await self._context_tree_repository.get_by_id(
                                suggested_parent
                            )
                            if (
                                new_parent
                                and str(node.id) not in new_parent.children_ids
                            ):
                                new_parent.children_ids.append(str(node.id))
                                try:
                                    await new_parent.save()
                                except TypeError:
                                    await self._context_tree_repository.update(
                                        str(new_parent.id),
                                        {"children_ids": new_parent.children_ids},
                                    )

                        try:
                            await node.save()
                        except TypeError:
                            await self._context_tree_repository.update(
                                str(node.id),
                                {
                                    "header": node.header,
                                    "summary": node.summary,
                                    "topics": node.topics,
                                    "parent_id": node.parent_id,
                                },
                            )
                        self._logger.info(f"Updated node {node.id} with AI suggestions")
                    else:
                        text = await response.text()
                        self._logger.error(
                            f"Failed to get AI organization: {response.status} - {text}"
                        )
                        if raise_on_no_response:
                            raise AIOrganizationError(
                                f"AI tree-analysis failed: status={response.status} body={text}"
                            )
        except Exception as e:
            self._logger.error(f"Error requesting AI organization: {e}")
            # If the caller explicitly requested that failures be raised, re-raise
            # an AIOrganizationError so the API layer can return an error to the user.
            if isinstance(e, AIOrganizationError):
                raise
            # Otherwise, swallow the error to avoid blocking node creation

    async def get_node(self, node_id: str) -> Optional[ContextTreeNodeResponse]:
        """Get a context tree node by its node_id."""
        node = await self._context_tree_repository.get_by_id(node_id)
        if not node:
            return None

        color_val = getattr(node, "color", None)
        color = color_val if isinstance(color_val, str) else None
        conv_val = getattr(node, "conversation_id", None)
        conv = conv_val if isinstance(conv_val, str) else None

        return ContextTreeNodeResponse(
            id=str(node.id),
            parent_id=node.parent_id,
            children_ids=node.children_ids,
            header=node.header,
            color=color,
            summary=node.summary,
            topics=node.topics,
            project_id=node.project_id,
            node_type=node.node_type,
            conversation_id=conv,
            created_at=node.created_at,
            updated_at=node.updated_at,
        )

    async def list_nodes_by_project(
        self, project_id: str
    ) -> List[ContextTreeNodeResponse]:
        """List all context tree nodes for a project."""
        nodes = await self._context_tree_repository.list_by_project(project_id)
        return [
            ContextTreeNodeResponse(
                id=str(n.id),
                parent_id=n.parent_id,
                children_ids=n.children_ids,
                header=n.header,
                color=(
                    getattr(n, "color", None)
                    if isinstance(getattr(n, "color", None), str)
                    else None
                ),
                summary=n.summary,
                topics=n.topics,
                project_id=n.project_id,
                node_type=n.node_type,
                conversation_id=(
                    getattr(n, "conversation_id", None)
                    if isinstance(getattr(n, "conversation_id", None), str)
                    else None
                ),
                created_at=n.created_at,
                updated_at=n.updated_at,
            )
            for n in nodes
        ]

    async def update_node(
        self, node_id: str, request: UpdateContextTreeNodeRequest
    ) -> Optional[ContextTreeNodeResponse]:
        """Update a context tree node."""
        update_data = request.dict(exclude_unset=True)
        update_data["updated_at"] = datetime.utcnow()

        node = await self._context_tree_repository.update(node_id, update_data)
        if not node:
            return None

        # Coerce potentially-mocked values to strings to satisfy Pydantic expectations in tests
        color_val = getattr(node, "color", None)
        conversation_val = getattr(node, "conversation_id", None)
        return ContextTreeNodeResponse(
            id=str(node.id),
            parent_id=node.parent_id,
            children_ids=node.children_ids,
            header=node.header,
            color=str(color_val) if color_val is not None else None,
            summary=node.summary,
            topics=node.topics,
            project_id=node.project_id,
            node_type=node.node_type,
            conversation_id=(
                str(conversation_val) if conversation_val is not None else None
            ),
            created_at=node.created_at,
            updated_at=node.updated_at,
        )

    async def delete_node(self, node_id: str) -> bool:
        """Delete a context tree node.

        Behavior:
        - Re-parent children to the deleted node's parent
        - Update parent's children list to remove the node and include the former children
        - Request AI service to delete the associated conversation (if any)
        - Delete the node from the repository
        """
        # fetch the node
        self._logger.info(f"Attempting to delete node {node_id}")
        node = await self._context_tree_repository.get_by_id(node_id)
        if not node:
            self._logger.warning(f"Node {node_id} not found for deletion")
            return False

        parent_id = node.parent_id
        children_ids = list(node.children_ids or [])

        # Reparent children to the deleted node's parent
        for child_id in children_ids:
            child = await self._context_tree_repository.get_by_id(child_id)
            if not child:
                continue
            child.parent_id = parent_id
            await self._context_tree_repository.update(
                child_id, {"parent_id": parent_id}
            )
            self._logger.info(f"Reparented child {child_id} to parent {parent_id}")

        # Update parent children list: remove this node, add the children
        if parent_id:
            parent = await self._context_tree_repository.get_by_id(parent_id)
            if parent:
                # remove the node id if present
                try:
                    parent.children_ids.remove(str(node_id))
                except ValueError:
                    pass
                # add children (avoid duplicates)
                for cid in children_ids:
                    if str(cid) not in parent.children_ids:
                        parent.children_ids.append(str(cid))
                await self._context_tree_repository.update(
                    parent_id, {"children_ids": parent.children_ids}
                )
                self._logger.info(
                    f"Updated parent {parent_id} children list after deleting {node_id}"
                )

        # Ask AI service to delete conversation if exists
        conv_id = getattr(node, "conversation_id", None)
        if conv_id:
            try:
                deleted_ai = await self._delete_ai_conversation(conv_id)
                if deleted_ai:
                    self._logger.info(
                        f"Deleted AI conversation {conv_id} for node {node_id}"
                    )
                else:
                    self._logger.warning(
                        f"AI conversation {conv_id} deletion returned false for node {node_id}"
                    )
            except Exception as e:
                self._logger.error(f"Failed to delete AI conversation {conv_id}: {e}")

        # Finally delete the node
        deleted = await self._context_tree_repository.delete(node_id)
        if deleted:
            self._logger.info(f"Node {node_id} deleted successfully")
        else:
            self._logger.error(f"Failed to delete node {node_id} from repository")
        return deleted

    async def _delete_ai_conversation(self, conversation_id: str) -> bool:
        """Request AI service to delete a conversation by id."""
        try:
            url = f"{settings.ai_service_url}/ai-conversations/{conversation_id}"
            self._logger.debug(f"Calling AI delete conversation: url={url}")
            async with aiohttp.ClientSession() as session:
                async with session.delete(url) as response:
                    status = response.status
                    body = await response.text()
                    self._logger.debug(
                        f"AI delete response status={status} body={body}"
                    )
                    if 200 <= status < 300:
                        return True
                    self._logger.error(f"AI delete returned {status}: {body}")
                    return False
        except Exception as e:
            self._logger.error(
                f"Error deleting AI conversation: {e}\n{traceback.format_exc()}"
            )
            return False
