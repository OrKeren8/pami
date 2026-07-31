from fastapi import APIRouter, HTTPException, Request
from loguru import logger

from ai_conversation_service.schemas.ai_conversation_schemas import (
    CreateConversationRequest,
    SendMessageRequest,
    ConversationResponse,
    ConversationHistoryResponse,
)
from ai_conversation_service.core.access import (
    ConversationForMemberDep,
    ProjectIdForMemberDep,
    assert_project_access,
)
from ai_conversation_service.core.auth import CurrentUserDep
from ai_conversation_service.core.config import settings
from ai_conversation_service.dependencies import AIConversationServiceDep
from ai_conversation_service.schemas.retrieval_schemas import (
    ContextHit,
    SearchContextRequest,
    SendMessageResult,
)
from ai_conversation_service.services.ai_conversation_service.service import (
    ConversationNotFoundError,
)

router = APIRouter(prefix="/ai-conversations", tags=["ai-conversations"])


@router.get("/health")
async def health_check():
    """Health check for AI conversation service."""
    return {"status": "healthy", "service": "ai-conversations"}


@router.post("/", response_model=ConversationResponse)
async def create_conversation(
    request: CreateConversationRequest,
    http_request: Request,
    user: CurrentUserDep,
    ai_conversation_service: AIConversationServiceDep,
):
    """Create a new AI conversation for a context node."""
    await assert_project_access(http_request, user, request.project_id)
    try:
        conversation = await ai_conversation_service.create_conversation(
            request.context_node_id, request.project_id, request.title
        )
        return ConversationResponse(**conversation.to_dict())
    except Exception as error:
        # str(error) here is a botocore, OpenAI or pymongo message: it leaks the S3
        # bucket and key layout, the model and org ids, or the replica-set hostnames
        # from the connection string - to an unauthenticated caller. Logged in full,
        # reported as a fixed string.
        logger.opt(exception=True).error(f"create_conversation failed: {error}")
        raise HTTPException(status_code=500, detail="Failed to create conversation")


@router.post("/{conversation_id}/messages", response_model=SendMessageResult)
async def send_message(
    conversation_id: str,
    request: SendMessageRequest,
    conversation: ConversationForMemberDep,
    ai_conversation_service: AIConversationServiceDep,
):
    """Send a message and get a response, with any consulted conversations reported."""
    try:
        return await ai_conversation_service.send_message_with_context(
            conversation_id, request.message, request.context_snapshot
        )
    except ConversationNotFoundError:
        raise HTTPException(status_code=404, detail="Conversation not found")
    except Exception as e:
        # Logged with the traceback: converting straight to a 500 left the service log
        # showing a bare status code with no reason, so a real failure could only be
        # diagnosed by reproducing it.
        logger.opt(exception=True).error(
            f"send_message failed for conversation {conversation_id}: {e}"
        )
        raise HTTPException(status_code=500, detail=f"Failed to send message: {str(e)}")


@router.get("/{conversation_id}", response_model=ConversationHistoryResponse)
async def get_conversation(
    conversation_id: str,
    # Named for what it does: the dependency's job is the membership check, and the handler
    # then loads the history separately.
    authorized: ConversationForMemberDep,
    ai_conversation_service: AIConversationServiceDep,
    limit: int | None = None,
):
    """Get conversation history."""
    try:
        conversation = await ai_conversation_service.get_conversation_history(
            conversation_id, limit
        )
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return ConversationHistoryResponse(**conversation)
    except HTTPException:
        raise
    except Exception as error:
        # str(error) here is a botocore, OpenAI or pymongo message: it leaks the S3
        # bucket and key layout, the model and org ids, or the replica-set hostnames
        # from the connection string - to an unauthenticated caller. Logged in full,
        # reported as a fixed string.
        logger.opt(exception=True).error(f"get_conversation failed: {error}")
        raise HTTPException(status_code=500, detail="Failed to get conversation")


@router.get("/node/{context_node_id}", response_model=list[ConversationResponse])
async def list_conversations_for_node(
    context_node_id: str,
    http_request: Request,
    user: CurrentUserDep,
    ai_conversation_service: AIConversationServiceDep,
):
    """List all conversations for a context node.

    A node id alone says nothing about who may see it, so each conversation is filtered by
    membership of the project it belongs to rather than trusting the node id.
    """
    try:
        conversations = await ai_conversation_service.list_conversations_for_node(
            context_node_id
        )
        allowed = []
        for conv in conversations:
            client = getattr(ai_conversation_service, "projects_service_client", None)
            if client and await client.can_access_project(
                user.user_id, conv.get("project_id")
            ):
                allowed.append(conv)
        return [ConversationResponse(**conv) for conv in allowed]
    except Exception as error:
        # str(error) here is a botocore, OpenAI or pymongo message: it leaks the S3
        # bucket and key layout, the model and org ids, or the replica-set hostnames
        # from the connection string - to an unauthenticated caller. Logged in full,
        # reported as a fixed string.
        logger.opt(exception=True).error(f"list_conversations_for_node failed: {error}")
        raise HTTPException(status_code=500, detail="Failed to list conversations")


@router.get("/project/{project_id}", response_model=list[ConversationResponse])
async def list_conversations_for_project(
    project_id: ProjectIdForMemberDep,
    ai_conversation_service: AIConversationServiceDep,
):
    """Every conversation in a project, most recently updated first."""
    try:
        conversations = await ai_conversation_service.list_conversations_for_project(
            project_id
        )
        return [ConversationResponse(**conv) for conv in conversations]
    except Exception as error:
        logger.opt(exception=True).error(
            f"list_conversations_for_project failed: {error}"
        )
        raise HTTPException(status_code=500, detail="Failed to list conversations")


@router.post("/context-retrieval/search", response_model=list[ContextHit])
async def search_context(
    request: SearchContextRequest,
    http_request: Request,
    user: CurrentUserDep,
    ai_conversation_service: AIConversationServiceDep,
):
    """Run the same retrieval the agent tool runs. Debug only, disabled by default."""
    if not settings.enable_retrieval_debug_api:
        raise HTTPException(status_code=404, detail="Not found")
    if not ai_conversation_service.context_retrieval_service:
        raise HTTPException(status_code=503, detail="Retrieval is unavailable")
    # Even behind a flag: this endpoint returns snippets from a client-supplied project id,
    # which is the whole point of checking it.
    await assert_project_access(http_request, user, request.project_id)
    return await ai_conversation_service.context_retrieval_service.search(
        project_id=request.project_id,
        query=request.query,
        exclude_conversation_id=request.exclude_conversation_id,
        limit=request.limit,
    )


@router.post("/context-retrieval/reindex/{conversation_id}", status_code=202)
async def reindex_conversation(
    conversation_id: str,
    conversation: ConversationForMemberDep,
    ai_conversation_service: AIConversationServiceDep,
):
    """Force a reindex, ignoring the debounce. Idempotent."""
    if not ai_conversation_service.chunk_index_service:
        raise HTTPException(status_code=503, detail="Retrieval is unavailable")

    reindexed = await ai_conversation_service.force_reindex(conversation_id)
    if not reindexed:
        raise HTTPException(
            status_code=404, detail="Conversation not found or has no messages"
        )
    return {"status": "reindexed", "conversation_id": conversation_id}


@router.delete("/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    conversation: ConversationForMemberDep,
    ai_conversation_service: AIConversationServiceDep,
):
    """Delete a conversation and remove it from the search index."""
    try:
        deleted = await ai_conversation_service.purge_conversation(conversation_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Conversation not found")

        return {"message": "Conversation deleted successfully"}
    except HTTPException:
        raise
    except Exception as error:
        # str(error) here is a botocore, OpenAI or pymongo message: it leaks the S3
        # bucket and key layout, the model and org ids, or the replica-set hostnames
        # from the connection string - to an unauthenticated caller. Logged in full,
        # reported as a fixed string.
        logger.opt(exception=True).error(f"delete_conversation failed: {error}")
        raise HTTPException(status_code=500, detail="Failed to delete conversation")
