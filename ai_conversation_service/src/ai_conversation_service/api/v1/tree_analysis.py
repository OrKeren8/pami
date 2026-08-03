from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from ai_conversation_service.schemas.tree_analysis_schemas import (
    AnalyzeTreeRequest,
    NodeOrganizationResponse,
)
from ai_conversation_service.core.auth import ServiceCallerDep
from ai_conversation_service.services.ai_conversation_service.service import (
    ConversationNotFoundError,
)
from ai_conversation_service.services.tree_analysis_service import TreeAnalysisService
from ai_conversation_service.dependencies import get_tree_analysis_service

router = APIRouter(prefix="/tree-analysis", tags=["tree-analysis"])


@router.post("/organize-node", response_model=NodeOrganizationResponse)
async def organize_node(
    request: AnalyzeTreeRequest,
    caller: ServiceCallerDep,
    service: TreeAnalysisService = Depends(get_tree_analysis_service),
):
    """
    Analyze conversation and existing tree to suggest optimal node organization.

    Called by projects-service when a node is created, from a background task with no user
    request in flight - so it authenticates a peer service rather than a person. Left open, it
    would read any conversation whose id a caller could name.

    AI will:
    - Read the conversation about this node
    - Analyze the existing tree structure
    - Suggest the best parent for this node
    - Generate a summary and extract topics
    - Provide reasoning for the placement
    """
    try:
        return await service.analyze_and_organize_node(request)
    except ConversationNotFoundError as error:
        # Only a missing conversation is a 404. A model that answered with a header of the
        # wrong length is not "not found", and reporting it that way left the caller's log
        # saying the conversation had vanished.
        raise HTTPException(status_code=404, detail=str(error))
    except ValueError as error:
        logger.warning(f"organize_node got an unusable model response: {error}")
        raise HTTPException(
            status_code=502, detail="The model returned an unusable organization"
        )
    except Exception as error:
        # str(error) here is a botocore, OpenAI or pymongo message: it leaks the S3
        # bucket and key layout, the model and org ids, or the replica-set hostnames
        # from the connection string - to an unauthenticated caller. Logged in full,
        # reported as a fixed string.
        logger.opt(exception=True).error(f"organize_node failed: {error}")
        raise HTTPException(status_code=500, detail="Failed to analyze tree structure")
