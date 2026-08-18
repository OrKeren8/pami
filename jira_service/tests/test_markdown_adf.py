"""The ticket text the editor produces, as the document Jira actually stores.

Nothing is stubbed: the converter is pure, and the document itself is the thing worth
checking, because a mistake here is only visible after a ticket has been published.
"""

from jira_service.services.jira_api_service import JiraApiService
from jira_service.services.markdown_adf import markdown_to_adf

TEMPLATE = """As a [role], I want [goal], so that [reason].

## User Flow
1.
2.
3.

## AC
-
-

## Edge Cases
- **Case** - handling

## DOD
- [ ] written
- [x] done

## Technical Notes
**Scope:** Frontend only
"""


def kinds(doc):
    return [block["type"] for block in doc["content"]]


def flatten(doc):
    """The service's own reader. Unbound, because it never touches self or the network."""
    return JiraApiService._adf_to_text(None, doc)


def test_headings_become_headings():
    doc = markdown_to_adf("## User Flow")
    assert doc["content"][0]["type"] == "heading"
    assert doc["content"][0]["attrs"]["level"] == 2
    assert doc["content"][0]["content"][0]["text"] == "User Flow"


def test_the_template_keeps_its_structure():
    doc = markdown_to_adf(TEMPLATE)
    assert kinds(doc) == [
        "paragraph",
        "heading",
        "orderedList",
        "heading",
        "bulletList",
        "heading",
        "bulletList",
        "heading",
        "taskList",
        "heading",
        "paragraph",
    ]


def test_empty_rows_survive_as_items():
    doc = markdown_to_adf("1.\n2.\n3.")
    items = doc["content"][0]["content"]
    assert len(items) == 3
    # An empty paragraph carries no content at all; a text node with "" is invalid ADF.
    assert "content" not in items[0]["content"][0]


def test_checkboxes_carry_their_state():
    items = markdown_to_adf("- [ ] open\n- [x] shut")["content"][0]["content"]
    assert [item["attrs"]["state"] for item in items] == ["TODO", "DONE"]
    assert items[0]["attrs"]["localId"] != items[1]["attrs"]["localId"]


def test_bold_and_code_become_marks():
    nodes = markdown_to_adf("**Scope:** uses `uv`")["content"][0]["content"]
    assert nodes[0]["text"] == "Scope:"
    assert nodes[0]["marks"] == [{"type": "strong"}]
    assert nodes[-1]["marks"] == [{"type": "code"}]


def test_prose_after_a_list_does_not_reorder_it():
    assert kinds(markdown_to_adf("- one\ntrailing note")) == ["bulletList", "paragraph"]


def test_a_numbered_list_keeps_its_first_number():
    assert markdown_to_adf("3. third")["content"][0]["attrs"]["order"] == 3


def test_an_empty_ticket_is_still_a_document():
    assert markdown_to_adf("")["content"] == [{"type": "paragraph"}]


def test_a_rule_is_not_an_empty_bullet():
    assert kinds(markdown_to_adf("---")) == ["rule"]


def test_reading_an_issue_back_keeps_its_shape():
    """Published and then fetched, a ticket must still look like the ticket that was written.

    The console shows what Jira returns, so a flattener that dropped the markers would show
    an issue as unstructured prose the moment it made the round trip.
    """
    written = "## AC\n- one\n- [ ] todo\n- [x] did\n\n**bold** tail"
    read_back = flatten(markdown_to_adf(written))
    assert "## AC" in read_back
    assert "- one" in read_back
    assert "- [ ] todo" in read_back
    assert "- [x] did" in read_back
    assert "**bold** tail" in read_back
