from functools import lru_cache
from fastapi import Request

from ai_conversation_service.core.config import settings
from ai_conversation_service.services.ai_conversation_service.service import (
    AIConversationService,
)


@lru_cache()
def get_config():
    """Get cached configuration instance."""
    return settings()


def get_ai_conversation_service(request: Request) -> AIConversationService:
    """Get AI conversation service from app state."""
    return request.app.state.ai_conversation_service
