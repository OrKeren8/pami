from fastapi import APIRouter, Depends, HTTPException

from ai_conversation_service.schemas.tree_analysis_schemas import (
    AnalyzeTreeRequest,
    NodeOrganizationResponse,
)
from ai_conversation_service.services.tree_analysis_service import TreeAnalysisService
from ai_conversation_service.dependencies import get_tree_analysis_service


router = APIRouter(prefix="/tree-analysis", tags=["tree-analysis"])


@router.post("/organize-node", response_model=NodeOrganizationResponse)
async def organize_node(
    request: AnalyzeTreeRequest,
    service: TreeAnalysisService = Depends(get_tree_analysis_service),
):
    """
    Analyze conversation and existing tree to suggest optimal node organization.
    
    AI will:
    - Read the conversation about this node
    - Analyze the existing tree structure
    - Suggest the best parent for this node
    - Generate a summary and extract topics
    - Provide reasoning for the placement
    """
    try:
        return await service.analyze_and_organize_node(request)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to analyze tree structure: {str(e)}"
        )
