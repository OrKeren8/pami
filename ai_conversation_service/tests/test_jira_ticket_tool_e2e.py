"""Asking for a ticket in the chat fills a draft, and cannot publish one.

The tool is how "make me a ticket" works now that the button is gone, so the things worth
pinning are: the draft reaches the reply, it survives a model that omits fields, and it stays
incapable of reaching Jira.
"""

import pytest

from ai_conversation_service.agents.conversation_agent import (
    AgentDeps,
    draft_jira_ticket,
)


class FakeRunContext:
    """Stands in for pydantic_ai's RunContext, which only exposes `deps` to a tool."""

    def __init__(self, deps):
        self.deps = deps


def _deps():
    return AgentDeps(project_id="proj-1", conversation_id="conv-1", retrieval=None)


async def test_the_draft_lands_on_the_deps_so_the_reply_can_carry_it():
    deps = _deps()

    result = await draft_jira_ticket(
        FakeRunContext(deps),
        summary="Graph drops a node after rename",
        description="## Screen\nDashboard\n\n## Steps to Reproduce\n1. Rename a node",
        issue_type="Bug",
    )

    assert deps.jira_draft is not None
    assert deps.jira_draft["summary"] == "Graph drops a node after rename"
    assert deps.jira_draft["issue_type"] == "Bug"
    assert "Steps to Reproduce" in deps.jira_draft["description"]
    # What the model is told back matters: it must not claim the ticket was filed.
    assert "not published" in result.lower()


async def test_drafting_does_not_spend_the_retrieval_budget():
    """It fetches no context, and refusing it after a few searches would be refusing the
    thing the user actually asked for."""
    deps = _deps()
    deps.tool_calls = 99  # far past the cap

    await draft_jira_ticket(
        FakeRunContext(deps), summary="s", description="d", issue_type="Task"
    )

    assert deps.jira_draft is not None, "the cap must not block drafting"
    assert deps.tool_calls == 99, "drafting must not consume a retrieval call"


async def test_the_pami_label_is_always_present():
    """Every ticket this app creates stays identifiable, whatever the model returns."""
    deps = _deps()

    await draft_jira_ticket(
        FakeRunContext(deps),
        summary="s",
        description="d",
        issue_type="Task",
        labels=["backend"],
    )

    assert "pami" in deps.jira_draft["labels"]
    assert "backend" in deps.jira_draft["labels"]


@pytest.mark.parametrize("labels", [None, [], ["  "], ["", None]])
async def test_missing_or_blank_labels_fall_back_rather_than_producing_an_empty_list(
    labels,
):
    """Jira rejects a blank label, so a model returning [""] would fail at publish time."""
    deps = _deps()

    await draft_jira_ticket(
        FakeRunContext(deps),
        summary="s",
        description="d",
        issue_type="Task",
        labels=labels,
    )

    assert deps.jira_draft["labels"] == ["pami"]


async def test_a_long_summary_is_trimmed_to_something_jira_accepts():
    """Jira caps the summary field; an over-long one is rejected outright."""
    deps = _deps()

    await draft_jira_ticket(
        FakeRunContext(deps), summary="x" * 900, description="d", issue_type="Task"
    )

    assert len(deps.jira_draft["summary"]) <= 255


async def test_no_draft_is_reported_when_the_tool_was_never_called():
    """An ordinary answer must not offer a Jira link."""
    deps = _deps()
    assert deps.jira_draft is None


def test_the_tool_description_tells_the_model_both_ticket_shapes():
    """The model produced story headings on a Bug until these were spelled out, and a bug
    report without repro steps is the one thing a bug report is for."""
    # Normalised: the docstring wraps, so an exact phrase can straddle a line break and
    # a substring check would fail on formatting rather than on content.
    doc = " ".join((draft_jira_ticket.__doc__ or "").split())

    for heading in ["Steps to Reproduce", "Actual Behavior", "Expected Behavior"]:
        assert heading in doc, f"the bug shape must name {heading}"
    assert "## AC" in doc, "the story shape must name its acceptance criteria section"
    assert "do not mix" in doc.lower()


def test_the_tool_cannot_reach_jira():
    """The guarantee behind "the chat fills the ticket, you publish it".

    Checked at the source rather than by behaviour: the tool must not gain an HTTP client or a
    Jira import later without someone deciding to.
    """
    import inspect

    from ai_conversation_service.agents import conversation_agent

    source = inspect.getsource(conversation_agent)

    for forbidden in [
        "jira_api",
        "atlassian",
        "rest/api",
        "requests.post",
        "httpx.post",
    ]:
        assert forbidden not in source.lower(), (
            f"the chat agent must have no route to Jira, found {forbidden!r}"
        )
