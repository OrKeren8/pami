from functools import lru_cache
from fastapi import Request

from ai_conversation_service.core.config import settings
from ai_conversation_service.services.ai_conversation_service.service import (
    AIConversationService,
)
from ai_conversation_service.services.tree_analysis_service import TreeAnalysisService


@lru_cache()
def get_config():
    """Get cached configuration instance."""
    return settings()


def get_ai_conversation_service(request: Request) -> AIConversationService:
    """Get AI conversation service from app state."""
    # Make the dependency import-safe for tests: create and store a service
    # instance on the app state when it's not already present.
    if not hasattr(request.app.state, "ai_conversation_service"):
        svc = AIConversationService()
        request.app.state.ai_conversation_service = svc
        return svc
    return request.app.state.ai_conversation_service


def get_tree_analysis_service(request: Request) -> TreeAnalysisService:
    """Get tree analysis service from app state."""
    if not hasattr(request.app.state, "tree_analysis_service"):
        svc = TreeAnalysisService()
        request.app.state.tree_analysis_service = svc
        return svc
    return request.app.state.tree_analysis_service
