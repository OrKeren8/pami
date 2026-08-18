"""Turn the ticket text the editor produces into an Atlassian document.

Jira Cloud takes descriptions and comments as ADF, a document tree - not as text. The whole
description used to be wrapped in a single paragraph node, so a ticket that reads as headings,
a numbered user flow and a checklist in PAMI arrived in Jira as one block of prose with the
raw `##`, `-` and `**` still in it.

The shapes handled here are exactly the ones the templates and the drafting agent write:
headings, bullet lists, numbered lists, checklists, and paragraphs, with bold and inline code
inside them. Anything else stays plain text rather than being guessed at - a wrong guess in a
published ticket is worse than an unstyled line.
"""

from __future__ import annotations

import re
from typing import Any

HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
# Checklists are tested before bullets, because "- [ ] x" is also a bullet.
CHECK = re.compile(r"^\s*[-*]\s+\[([ xX])\]\s*(.*)$")
# The text is optional throughout: a template ships its lists empty, and an empty row is an
# item waiting to be filled rather than a paragraph that happens to start with a dash.
BULLET = re.compile(r"^\s*[-*](?:\s+(.*))?$")
NUMBERED = re.compile(r"^\s*(\d+)[.)](?:\s+(.*))?$")
# A rule, not an empty bullet.
RULE = re.compile(r"^\s*([-*_])\1{2,}\s*$")

# Bold before italic so `**x**` is not read as an italic wrapping `*x*`, and code first of all
# so emphasis inside a code span stays literal.
INLINE = re.compile(r"(`[^`]+`|\*\*[^*]+\*\*|__[^_]+__|\*[^*\n]+\*)")


def _text_nodes(text: str) -> list[dict[str, Any]]:
    """Inline spans for one line. Empty text yields no nodes, which ADF requires."""
    nodes: list[dict[str, Any]] = []
    for part in INLINE.split(text or ""):
        if not part:
            continue
        # (opening delimiter, mark) in the order the pattern matches them. `__` and `**` are
        # the same mark, which is why this is a table rather than a branch per form.
        for fence, mark in (
            ("`", "code"),
            ("**", "strong"),
            ("__", "strong"),
            ("*", "em"),
        ):
            if (
                part.startswith(fence)
                and part.endswith(fence)
                and len(part) > 2 * len(fence)
            ):
                nodes.append(
                    {
                        "type": "text",
                        "text": part[len(fence) : -len(fence)],
                        "marks": [{"type": mark}],
                    }
                )
                break
        else:
            nodes.append({"type": "text", "text": part})
    return nodes


def _paragraph(text: str) -> dict[str, Any]:
    """A paragraph node. Content is omitted when empty: ADF rejects an empty text node."""
    nodes = _text_nodes(text)
    return {"type": "paragraph", "content": nodes} if nodes else {"type": "paragraph"}


def _list_item(text: str) -> dict[str, Any]:
    return {"type": "listItem", "content": [_paragraph(text)]}


class _Builder:
    """Collects lines into blocks, closing whatever list is open when the shape changes."""

    def __init__(self) -> None:
        self.blocks: list[dict[str, Any]] = []
        self.paragraph: list[str] = []
        self.list_node: dict[str, Any] | None = None
        self.list_kind: str | None = None
        # Task items need ids that are unique within the document. A counter rather than
        # random ids, so the same text always produces the same document.
        self.task_id = 0

    def flush_paragraph(self) -> None:
        if self.paragraph:
            self.blocks.append(_paragraph(" ".join(self.paragraph)))
            self.paragraph = []

    def flush_list(self) -> None:
        if self.list_node:
            self.blocks.append(self.list_node)
            self.list_node = None
            self.list_kind = None

    def open_list(self, kind: str, node: dict[str, Any]) -> None:
        if self.list_kind != kind:
            self.flush_list()
            self.list_node = node
            self.list_kind = kind

    def next_task_id(self) -> str:
        self.task_id += 1
        return f"task-{self.task_id}"

    def done(self) -> list[dict[str, Any]]:
        self.flush_paragraph()
        self.flush_list()
        return self.blocks


def markdown_to_adf(text: str) -> dict[str, Any]:
    """The document Jira should store for this ticket text."""
    builder = _Builder()

    for raw_line in (text or "").split("\n"):
        line = raw_line.rstrip()

        if not line.strip():
            builder.flush_paragraph()
            builder.flush_list()
            continue

        if RULE.match(line):
            builder.flush_paragraph()
            builder.flush_list()
            builder.blocks.append({"type": "rule"})
            continue

        heading = HEADING.match(line)
        if heading:
            builder.flush_paragraph()
            builder.flush_list()
            # Capped at 6, which is as deep as ADF goes.
            level = min(6, len(heading.group(1)))
            node: dict[str, Any] = {"type": "heading", "attrs": {"level": level}}
            content = _text_nodes(heading.group(2))
            if content:
                node["content"] = content
            builder.blocks.append(node)
            continue

        check = CHECK.match(line)
        if check:
            builder.flush_paragraph()
            builder.open_list(
                "task",
                {
                    "type": "taskList",
                    "attrs": {"localId": "tasks"},
                    "content": [],
                },
            )
            item: dict[str, Any] = {
                "type": "taskItem",
                "attrs": {
                    "localId": builder.next_task_id(),
                    "state": "DONE" if check.group(1).lower() == "x" else "TODO",
                },
            }
            content = _text_nodes(check.group(2))
            if content:
                item["content"] = content
            builder.list_node["content"].append(item)  # type: ignore[index]
            continue

        numbered = NUMBERED.match(line)
        if numbered:
            builder.flush_paragraph()
            # Carries its own first number, so a list broken up by prose keeps counting
            # instead of restarting at 1 on every fragment.
            start = int(numbered.group(1) or 1)
            builder.open_list(
                "ordered",
                {"type": "orderedList", "attrs": {"order": start}, "content": []},
            )
            builder.list_node["content"].append(_list_item(numbered.group(2) or ""))  # type: ignore[index]
            continue

        bullet = BULLET.match(line)
        if bullet:
            builder.flush_paragraph()
            builder.open_list("bullet", {"type": "bulletList", "content": []})
            builder.list_node["content"].append(_list_item(bullet.group(1) or ""))  # type: ignore[index]
            continue

        # Prose ends a list. Without this the list and the paragraph collect in parallel and
        # whichever is flushed first wins, which reorders the ticket.
        builder.flush_list()
        builder.paragraph.append(line.strip())

    content = builder.done()
    # A document may not be empty, and an empty ticket is a real case: the user can publish
    # one with only a summary.
    return {"type": "doc", "version": 1, "content": content or [{"type": "paragraph"}]}
