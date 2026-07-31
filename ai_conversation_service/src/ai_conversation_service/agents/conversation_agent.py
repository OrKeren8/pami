from dataclasses import dataclass, field
from typing import Annotated, Protocol

from loguru import logger
from pydantic import Field
from pydantic_ai import Agent, ModelRetry, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import UsageLimits

from ai_conversation_service.core.config import settings
from ai_conversation_service.core.prompt_loader import load_prompt_file
from ai_conversation_service.schemas.retrieval_schemas import (
    ConsultedConversation,
    ContextHit,
)
from ai_conversation_service.services.context_retrieval_service import (
    ContextRetrievalService,
)

CONVERSATION_CHAT_SYSTEM_PROMPT = load_prompt_file(
    "conversation_chat_system_prompt.txt"
)

_logger = logger.bind(service="ConversationAgent")


class TranscriptReader(Protocol):
    """The subset of AIConversationService the agent needs, to avoid an import cycle."""

    async def get_conversation(self, conversation_id: str): ...


@dataclass
class AgentDeps:
    """Server-owned context for one agent run. `project_id` is never model-supplied."""

    project_id: str
    conversation_id: str
    retrieval: ContextRetrievalService
    chunk_index: object | None = None
    transcripts: TranscriptReader | None = None
    consulted: dict[str, ConsultedConversation] = field(default_factory=dict)
    tool_calls: int = 0


BUDGET_SPENT_NOTE = (
    "Retrieval budget spent. Answer the user now from what you already have, and say "
    "what you could not check."
)


def _budget_exhausted(deps: AgentDeps) -> bool:
    """Whether the run has used its allowance of retrieval calls.

    Enforced in the tools rather than only through UsageLimits: a request limit kills the
    whole run once exceeded, which loses the answer the model was about to write. Refusing
    the extra call instead degrades to a shorter answer.
    """
    return deps.tool_calls >= settings.retrieval_max_tool_calls


async def search_context(
    ctx: RunContext[AgentDeps],
    query: str,
    limit: Annotated[int, Field(ge=1, le=20)] = 5,
) -> list[ContextHit]:
    """Search the user's OTHER conversations in this project for information that is
    not in the current conversation. Use it whenever the user refers to something you
    have no record of, before saying you do not know."""
    if _budget_exhausted(ctx.deps):
        _logger.info(
            f"search_context refused: {ctx.deps.tool_calls} calls already used "
            f"(limit {settings.retrieval_max_tool_calls})"
        )
        raise ModelRetry(BUDGET_SPENT_NOTE)

    ctx.deps.tool_calls += 1
    hits = await ctx.deps.retrieval.search(
        project_id=ctx.deps.project_id,
        query=query,
        exclude_conversation_id=ctx.deps.conversation_id,
        limit=limit,
    )
    for hit in hits:
        entry = ctx.deps.consulted.setdefault(
            hit.conversation_id,
            ConsultedConversation(
                conversation_id=hit.conversation_id, header=hit.header
            ),
        )
        entry.hit_count += 1
        entry.best_score = max(entry.best_score, hit.score)
    _logger.info(
        f"search_context returned {len(hits)} hits "
        f"(query_len={len(query)}, project={ctx.deps.project_id})"
    )
    return hits


async def read_conversation(
    ctx: RunContext[AgentDeps], conversation_id: str, around_message: int = -1
) -> list[str]:
    """Read a wider window from a conversation that search_context surfaced. Pass the
    conversation_id from a search result and, optionally, the message index to centre
    on."""
    if _budget_exhausted(ctx.deps):
        _logger.info(
            f"read_conversation refused: {ctx.deps.tool_calls} calls already used "
            f"(limit {settings.retrieval_max_tool_calls})"
        )
        raise ModelRetry(BUDGET_SPENT_NOTE)

    ctx.deps.tool_calls += 1
    if not ctx.deps.chunk_index or not ctx.deps.transcripts:
        return []

    conversation = await ctx.deps.transcripts.get_conversation(conversation_id)
    if not conversation or conversation.project_id != ctx.deps.project_id:
        _logger.warning(
            f"read_conversation denied for {conversation_id}: outside project "
            f"{ctx.deps.project_id}"
        )
        return []

    windows = await ctx.deps.chunk_index.read_window(
        conversation_id, around_message, project_id=ctx.deps.project_id
    )
    if windows:
        entry = ctx.deps.consulted.setdefault(
            conversation_id,
            ConsultedConversation(
                conversation_id=conversation_id,
                header=getattr(conversation, "title", None),
            ),
        )
        entry.read = True
    _logger.info(
        f"read_conversation returned {len(windows)} windows from {conversation_id}"
    )
    return windows


def build_conversation_agent() -> Agent:
    """Build the chat agent. Called from lifespan, never at import time."""
    model = OpenAIChatModel(
        settings.openai_model,
        provider=OpenAIProvider(api_key=settings.openai_api_key),
    )
    agent = Agent(
        model,
        deps_type=AgentDeps,
        output_type=str,
        system_prompt=CONVERSATION_CHAT_SYSTEM_PROMPT,
    )
    agent.tool(search_context)
    agent.tool(read_conversation)
    return agent


def build_usage_limits() -> UsageLimits:
    """Backstop only — the tools enforce the real cap.

    `request_limit` counts model requests, not tool calls: N tool calls need N + 1 requests
    because the answer costs one. The old `max_tool_calls + 1` therefore left no room for the
    answer at all, and a run that used the full allowance died with the reply half-written.
    """
    return UsageLimits(request_limit=settings.retrieval_max_tool_calls + 3)
