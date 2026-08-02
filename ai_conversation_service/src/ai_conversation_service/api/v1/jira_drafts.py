"""Let PAMI fill in a Jira ticket draft.

Stateless on purpose: the draft lives in the browser and is passed in and out on every turn.
That means no new collection, no polling, and no chance of the editor showing one ticket while
the server believes in another - the screen is the source of truth until the user publishes.

Nothing here can publish to Jira. The agent has no tools, and this service cannot reach the
Jira service at all, so "the chat can fill the ticket but not send it" is a property of the
architecture rather than a rule the model is asked to follow.
"""

from fastapi import APIRouter, HTTPException, Request
from loguru import logger

from ai_conversation_service.agents.jira_draft_agent import (
    build_draft_prompt,
    merge_draft,
)
from ai_conversation_service.core.access import CallerDep
from ai_conversation_service.core.access import assert_project_access
from ai_conversation_service.schemas.jira_draft_schemas import (
    JiraDraftRequest,
    JiraDraftResponse,
)

router = APIRouter(prefix="/jira-drafts", tags=["jira-drafts"])

# Enough for the model to follow a drafting session without the prompt growing without bound.
MAX_HISTORY_MESSAGES = 12


@router.post("/assist", response_model=JiraDraftResponse)
async def assist_with_draft(
    request: JiraDraftRequest,
    http_request: Request,
    caller: CallerDep,
):
    """Revise the ticket draft according to the user's message."""
    agent = getattr(http_request.app.state, "jira_draft_agent", None)
    if agent is None:
        raise HTTPException(
            status_code=503, detail="Ticket drafting is unavailable right now"
        )

    if not request.message.strip():
        raise HTTPException(status_code=422, detail="Say what you want changed")

    # A project id is optional here - a ticket does not have to belong to a PAMI project - but
    # when one is given it is checked, so it cannot be used to reach a project the caller
    # cannot see once this starts pulling in conversation context.
    if request.project_id:
        await assert_project_access(http_request, caller, request.project_id)

    request.history = request.history[-MAX_HISTORY_MESSAGES:]

    try:
        result = await agent.run(build_draft_prompt(request))
    except Exception as error:
        logger.opt(exception=True).error(f"jira draft assist failed: {error}")
        raise HTTPException(
            status_code=502,
            detail="PAMI could not revise the ticket. Please try again.",
        )

    output = result.output
    merged = merge_draft(request.draft, output.draft)

    logger.bind(service="JiraDraftAgent").info(
        f"Revised draft: summary_len={len(merged.summary)} "
        f"description_len={len(merged.description)} type={merged.issue_type}"
    )

    return JiraDraftResponse(reply=output.reply, draft=merged)
