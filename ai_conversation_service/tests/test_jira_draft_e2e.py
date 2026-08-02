"""PAMI fills in a Jira ticket, and cannot publish it.

The second half is the part worth testing: the whole point of the split is that the chat
drafts and the user decides. A model that could reach Jira would make "submit" advisory.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ai_conversation_service.agents.jira_draft_agent import (
    build_draft_prompt,
    build_jira_draft_agent,
    merge_draft,
)
from ai_conversation_service.api.v1.jira_drafts import router as jira_drafts_router
from ai_conversation_service.core.access import caller_identity
from ai_conversation_service.schemas.jira_draft_schemas import (
    DraftMessage,
    JiraDraftRequest,
    TicketDraft,
)


class StubResult:
    def __init__(self, output):
        self.output = output


class StubAgent:
    """Stands in for the model. Records the prompt so the test can assert what it was told."""

    def __init__(self, output, fail: bool = False):
        self.output = output
        self.fail = fail
        self.prompts: list[str] = []

    async def run(self, prompt: str):
        self.prompts.append(prompt)
        if self.fail:
            raise RuntimeError("model unavailable")
        return StubResult(self.output)


def _client(agent):
    app = FastAPI()
    app.include_router(jira_drafts_router, prefix="/ai")
    app.state.jira_draft_agent = agent
    # No project id is sent in these tests, so the access check never runs; the override keeps
    # the dependency from reaching for a token that is not there.
    app.dependency_overrides[caller_identity] = lambda: None
    return TestClient(app)


class Output:
    def __init__(self, reply, draft):
        self.reply = reply
        self.draft = draft


def test_the_draft_agent_has_no_tools(monkeypatch):
    """It must have no way to reach Jira, rather than being asked not to.

    This is the guarantee behind "the chat cannot send the ticket". A tool appearing here
    later - even a read-only one - is worth failing the build over so the decision is
    deliberate.
    """
    from ai_conversation_service.agents.conversation_agent import (
        build_conversation_agent,
    )
    from ai_conversation_service.core.config import settings

    # Building an agent instantiates the OpenAI provider, which insists on a key even though
    # nothing here calls the API - this test only inspects the assembled object. A placeholder
    # keeps it hermetic; without it the test passed locally and failed in CI, where the AI job
    # has no key.
    monkeypatch.setattr(settings, "openai_api_key", "test-key-not-used", raising=False)

    def tools_of(agent):
        toolset = getattr(agent, "_function_toolset", None)
        return sorted(getattr(toolset, "tools", {}) or {})

    # First prove the introspection finds tools at all. Without this the assertion below
    # passes on any pydantic_ai version that renames the attribute - the same vacuous-pass
    # trap as a route inventory that sees no routes.
    assert tools_of(build_conversation_agent()), (
        "the chat agent has tools, so finding none here means this check is looking in the "
        "wrong place and proves nothing"
    )

    assert not tools_of(build_jira_draft_agent()), (
        "the drafting agent must have no tools: that is what makes publishing impossible "
        "rather than merely discouraged"
    )


def test_a_revision_is_applied_to_the_draft():
    filled = TicketDraft(
        template_id="bug",
        summary="Graph hides nodes after a rename",
        description="## Steps to Reproduce\n1. Rename a node",
        issue_type="Bug",
    )
    client = _client(StubAgent(Output("Filled in the steps.", filled)))

    response = client.post(
        "/ai/jira-drafts/assist",
        json={
            "message": "write the repro steps",
            "draft": {
                "template_id": "bug",
                "summary": "",
                "description": "",
                "issue_type": "Bug",
            },
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["reply"] == "Filled in the steps."
    assert body["draft"]["summary"] == "Graph hides nodes after a rename"
    assert "Rename a node" in body["draft"]["description"]


def test_a_blank_field_coming_back_does_not_wipe_what_the_user_typed():
    """Structured output happily returns "" for a field it had nothing to say about.

    Treating that as a deletion would erase a summary the user wrote by hand the moment they
    asked for an unrelated change.
    """
    original = TicketDraft(
        template_id="story",
        summary="Typed by the user",
        description="Written by the user",
        issue_type="Story",
    )
    empty = TicketDraft(template_id="story", summary="", description="", issue_type="")

    merged = merge_draft(original, empty)

    assert merged.summary == "Typed by the user"
    assert merged.description == "Written by the user"
    assert merged.issue_type == "Story"


def test_the_template_and_the_pami_label_are_not_the_models_to_change():
    original = TicketDraft(template_id="bug", labels=["pami", "graph"])
    proposed = TicketDraft(
        template_id="story", summary="x", description="y", labels=["other"]
    )

    merged = merge_draft(original, proposed)

    assert merged.template_id == "bug", "the user picked the template"
    assert "pami" in merged.labels, "every ticket this app creates stays identifiable"


def test_the_prompt_carries_the_current_draft_and_the_allowed_types():
    """Without the offered types the model can pick one the project does not have, and the
    publish then fails with an error that does not explain itself."""
    request = JiraDraftRequest(
        message="tighten the AC",
        draft=TicketDraft(summary="Existing summary", description="## AC\n- one"),
        history=[DraftMessage(role="user", content="earlier question")],
        available_issue_types=["Story", "Bug"],
    )

    prompt = build_draft_prompt(request)

    assert "Existing summary" in prompt
    assert "## AC" in prompt
    assert "Story, Bug" in prompt
    assert "earlier question" in prompt
    assert "tighten the AC" in prompt


def test_history_is_bounded():
    """A long drafting session would otherwise grow the prompt without limit."""
    from ai_conversation_service.api.v1.jira_drafts import MAX_HISTORY_MESSAGES

    agent = StubAgent(Output("ok", TicketDraft(summary="s", description="d")))
    client = _client(agent)

    client.post(
        "/ai/jira-drafts/assist",
        json={
            "message": "again",
            "draft": {"summary": "s", "description": "d"},
            "history": [
                {"role": "user", "content": f"message {index}"} for index in range(40)
            ],
        },
    )

    prompt = agent.prompts[-1]
    assert "message 39" in prompt, "the most recent turns must survive"
    assert "message 0" not in prompt, "the oldest turns must be dropped"
    assert prompt.count("User: message") <= MAX_HISTORY_MESSAGES


def test_an_empty_message_is_refused():
    client = _client(StubAgent(Output("x", TicketDraft())))

    response = client.post(
        "/ai/jira-drafts/assist", json={"message": "   ", "draft": {}}
    )

    assert response.status_code == 422


def test_a_model_failure_is_reported_not_leaked():
    client = _client(StubAgent(Output("x", TicketDraft()), fail=True))

    response = client.post(
        "/ai/jira-drafts/assist", json={"message": "go", "draft": {}}
    )

    assert response.status_code == 502
    assert "model unavailable" not in response.text, "internal errors stay in the log"


def test_drafting_is_unavailable_rather_than_crashing_when_the_agent_is_absent():
    app = FastAPI()
    app.include_router(jira_drafts_router, prefix="/ai")
    app.state.jira_draft_agent = None
    app.dependency_overrides[caller_identity] = lambda: None

    response = TestClient(app).post(
        "/ai/jira-drafts/assist", json={"message": "go", "draft": {}}
    )

    assert response.status_code == 503


@pytest.mark.parametrize("template_id", ["story", "bug", "task", "spike"])
def test_every_template_id_round_trips(template_id):
    """The editor sends whichever template the user picked; none may be rejected."""
    merged = merge_draft(
        TicketDraft(template_id=template_id),
        TicketDraft(template_id="story", summary="s", description="d"),
    )
    assert merged.template_id == template_id
