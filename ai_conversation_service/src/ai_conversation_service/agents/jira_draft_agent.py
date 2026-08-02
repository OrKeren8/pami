from loguru import logger
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from ai_conversation_service.core.config import settings
from ai_conversation_service.core.prompt_loader import load_prompt_file
from ai_conversation_service.schemas.jira_draft_schemas import (
    JiraDraftRequest,
    JiraDraftResponse,
    TicketDraft,
)

JIRA_DRAFT_SYSTEM_PROMPT = load_prompt_file("jira_draft_system_prompt.txt")

_logger = logger.bind(service="JiraDraftAgent")


class DraftOutput(JiraDraftResponse):
    """Structured output. Both halves come back together so the reply cannot describe an edit
    the draft does not actually contain."""


def build_jira_draft_agent() -> Agent:
    """Build the ticket-drafting agent. Called from lifespan, never at import time.

    Has no tools on purpose. The one thing it must not be able to do is publish - that is the
    user's decision - and the surest way to guarantee that is to give it no way to reach Jira
    at all. It only rewrites a draft that the browser holds.
    """
    model = OpenAIChatModel(
        settings.openai_model,
        provider=OpenAIProvider(api_key=settings.openai_api_key),
    )
    return Agent(
        model,
        output_type=DraftOutput,
        system_prompt=JIRA_DRAFT_SYSTEM_PROMPT,
    )


def build_draft_prompt(request: JiraDraftRequest) -> str:
    """The current ticket, the conversation so far, and what the user just asked."""
    draft = request.draft

    lines = ["## Ticket as it stands"]
    lines.append(f"template: {draft.template_id}")
    lines.append(f"issue_type: {draft.issue_type}")
    lines.append(f"summary: {draft.summary or '(empty)'}")
    lines.append(f"priority: {draft.priority or '(unset)'}")
    lines.append(f"due_date: {draft.due_date or '(unset)'}")
    lines.append(f"labels: {', '.join(draft.labels) or '(none)'}")
    lines.append("description:")
    lines.append(draft.description or "(empty)")

    if request.available_issue_types:
        lines.append("")
        lines.append(
            "## Issue types this project offers\n"
            + ", ".join(request.available_issue_types)
        )

    if request.history:
        lines.append("")
        lines.append("## Conversation so far")
        # Oldest first, and bounded by the caller: the whole exchange would grow without limit
        # across a long drafting session.
        for message in request.history:
            speaker = "User" if message.role == "user" else "PAMI"
            lines.append(f"{speaker}: {message.content}")

    lines.append("")
    lines.append("## What the user just asked")
    lines.append(request.message)

    return "\n".join(lines)


def merge_draft(original: TicketDraft, proposed: TicketDraft) -> TicketDraft:
    """Keep what the model is not allowed to decide, and never silently empty a field.

    A model returning a structured object will happily return "" for a field it had nothing to
    say about, which would wipe a summary the user typed themselves. So a blank coming back is
    treated as "no change" rather than as a deletion, and the template the user chose always
    wins - the draft belongs to them.
    """
    merged = proposed.model_copy()
    merged.template_id = original.template_id

    if not merged.summary.strip():
        merged.summary = original.summary
    if not merged.description.strip():
        merged.description = original.description
    if not merged.issue_type.strip():
        merged.issue_type = original.issue_type

    # `pami` marks every ticket this app created, and is not the model's to drop.
    labels = [label for label in merged.labels if label.strip()] or list(
        original.labels
    )
    if "pami" not in labels:
        labels.append("pami")
    merged.labels = labels

    return merged
