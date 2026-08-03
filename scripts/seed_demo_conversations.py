"""Seed a project with realistic conversations, the way a person would produce them.

Every call here is one the frontend itself makes: create a conversation, send messages and let
the model answer, then turn the conversation into a context node and ask for a reindex. Nothing
is written straight into Mongo or S3, so what comes out is indistinguishable from use - the
transcripts are real model replies, the embeddings are real, and the links between nodes are
whatever the similarity floor actually decides.

That last part matters: this does not fabricate links. Conversations that are genuinely about
the same work will connect, and the two off-topic ones at the end will not. An honest graph with
a couple of islands in it says more about the system than a fully connected one would.

Usage
-----
    py scripts/seed_demo_conversations.py --project pami
    py scripts/seed_demo_conversations.py --project pami --only 3   # first three, to try it
    py scripts/seed_demo_conversations.py --list                    # show what would be sent

Costs real model calls on whatever key the AI service is configured with: roughly three
completions per conversation plus the embeddings for indexing.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request

DEFAULT_API = "https://ivwfkl5cdk.execute-api.us-east-1.amazonaws.com"

# Each entry is one conversation: a title, the messages a person would actually type, and the
# topics the node carries. The first six are the same body of work seen from different angles,
# which is what gives the graph a connected core; the last two are deliberately unrelated.
CONVERSATIONS: list[dict] = [
    {
        "title": "Graph layout and readability",
        "topics": ["graph", "layout", "d3", "ui"],
        "messages": [
            "The conversation graph gets unreadable past about twenty nodes - everything "
            "clumps in the middle and the labels overlap. What are my options for making it "
            "readable at fifty or a hundred nodes?",
            "I like the idea of pinning. If I let someone drag a node and pin it, should the "
            "force simulation keep running for the others or freeze entirely?",
            "Let's keep the simulation running and pin only what was dragged. Remember that "
            "decision - I do not want to relitigate it every time the layout feels busy.",
        ],
    },
    {
        "title": "Linking conversations by similarity",
        "topics": ["retrieval", "embeddings", "similarity", "graph"],
        "messages": [
            "How should PAMI decide that two conversations are related enough to draw a link "
            "between their nodes? I am using OpenAI embeddings and cosine similarity.",
            "What I keep hitting is calibration: with the old 384-dimension model a score of "
            "0.55 meant related, and with text-embedding-3-small the same number means almost "
            "nothing. How do I stop the threshold being a magic constant?",
            "Agreed on calibrating per model and storing which model produced each vector. And "
            "when nothing clears the floor, say so instead of forcing a link.",
        ],
    },
    {
        "title": "Turning a chat into a ticket",
        "topics": ["jira", "tickets", "ai", "workflow"],
        "messages": [
            "I want to ask PAMI in a chat for a Jira ticket and have the draft appear in the "
            "Jira window. What is the cleanest way to wire that without giving the AI service "
            "access to Jira?",
            "So the browser is the bridge - the AI returns a draft on the reply and the Jira "
            "page picks it up. What stops the model publishing a ticket by accident?",
            "Right: the drafting agent gets no tools at all, and publishing stays a click. Keep "
            "that rule, it is the whole reason I trust the feature.",
        ],
    },
    {
        "title": "Ticket formats worth using",
        "topics": ["jira", "tickets", "templates", "process"],
        "messages": [
            "What should a good story ticket contain? Ours are one line and a shrug, and then "
            "nobody knows what done means.",
            "I like the as-a line plus user flow, acceptance criteria and a definition of "
            "done. What changes for a bug?",
            "Bug leads with steps to reproduce, actual and expected - and never mixes in the "
            "story shape. Note that for later.",
        ],
    },
    {
        "title": "Per-user accounts with Cognito",
        "topics": ["auth", "cognito", "accounts", "sharing"],
        "messages": [
            "I want each user to have their own projects, and to be able to add someone to a "
            "project by email so it appears for both of them. I am on AWS with Cognito.",
            "How do I handle inviting someone who has no account yet? I do not want to create "
            "a Cognito user on their behalf.",
            "Pending invites claimed at first sign-in sounds right. And the admin page must be "
            "gated server-side, not by hiding a link.",
        ],
    },
    {
        "title": "Feature environments and deploys",
        "topics": ["aws", "deploys", "ecs", "infrastructure"],
        "messages": [
            "My ECS service reports healthy but the load balancer returns 503. The tasks are "
            "running and the target group is empty. Where do I look first?",
            "The ALB is in two subnets and the service launches tasks in six. That would do "
            "it, would it not?",
            "Fixed by reading the subnets from the ALB instead of listing them twice. Worth "
            "remembering - it cost me an afternoon.",
        ],
    },
    {
        "title": "The design system",
        "topics": ["design", "css", "tokens", "ui"],
        "messages": [
            "Every screen in my app invents its own buttons and labels, so the same control "
            "looks different depending on where you meet it. How do I fix that without a "
            "rewrite?",
            "If I build a token layer plus a few primitives, what belongs in the system and "
            "what stays with the page?",
            "So layout stays with the page and anything reusable moves into the system. Also: "
            "pills are for status only - when everything is a pill nothing is.",
        ],
    },
    {
        "title": "Rewinding the project graph",
        "topics": ["graph", "time", "ui", "history"],
        "messages": [
            "I want a scrubber under the graph that rewinds the project - nodes disappear, "
            "links unwind, and play replays the whole thing. What is the least machinery that "
            "gets me there?",
            "The graph already drops a link when one end is missing, so can I just hand it a "
            "filtered node list?",
            "Then the whole feature is one filter over creation order. Keep the end of the "
            "track meaning now, so it stays live as new nodes arrive.",
        ],
    },
    # --- deliberately unrelated: these should NOT link, and the graph is honest about it ----
    {
        "title": "Thesis submission plan",
        "topics": ["thesis", "writing", "academic"],
        "messages": [
            "I have six weeks until my thesis is due and three chapters unwritten. Help me put "
            "together a week-by-week plan that leaves time for review.",
            "The literature chapter is the one I keep avoiding. How long should I budget for it "
            "if I have already collected the sources?",
        ],
    },
    {
        "title": "Coffee gear",
        "topics": ["coffee", "personal"],
        "messages": [
            "My espresso comes out sour no matter what I do. Grinder is decent, beans are two "
            "weeks off roast. Where do I start?",
            "So grind finer and raise the temperature slightly before touching the ratio. "
            "Anything else worth trying?",
        ],
    },
]


def post(url: str, body: dict | None, timeout: int = 120) -> dict:
    data = json.dumps(body or {}).encode()
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        text = response.read().decode()
    return json.loads(text) if text else {}


def get(url: str, timeout: int = 60):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode())


def find_project(api: str, name: str) -> str:
    projects = get(f"{api}/projects/")
    for project in projects:
        if project.get("name", "").lower() == name.lower():
            return project["id"]
    available = ", ".join(project.get("name", "?") for project in projects) or "none"
    raise SystemExit(f"No project called {name!r}. Available: {available}")


def seed_one(api: str, project_id: str, spec: dict, index: int) -> str | None:
    """One conversation, end to end, exactly as the app does it."""
    title = spec["title"]
    print(f"\n[{index}] {title}")

    created = post(
        f"{api}/ai/ai-conversations/",
        {
            # The UI uses a synthetic id for a chat that has no node yet; a node is created
            # from the conversation afterwards, not before.
            "context_node_id": f"seed-session-{int(time.time())}-{index}",
            "project_id": project_id,
            "title": title,
        },
    )
    conversation_id = created.get("conversation_id") or created.get("id")
    if not conversation_id:
        print("    could not create the conversation")
        return None
    print(f"    conversation {conversation_id}")

    transcript: list[dict] = []
    for turn, message in enumerate(spec["messages"], start=1):
        print(f"    message {turn}/{len(spec['messages'])}...", end=" ", flush=True)
        try:
            result = post(
                f"{api}/ai/ai-conversations/{conversation_id}/messages", {"message": message}
            )
        except urllib.error.HTTPError as error:
            print(f"failed ({error.code})")
            return None
        reply = result.get("response") or result.get("text") or ""
        transcript.append({"role": "user", "content": message})
        transcript.append({"role": "assistant", "content": reply})
        print(f"replied {len(reply)} chars")

    # The node the graph draws. Header and summary follow what the UI writes: the last thing
    # the person said, and the model's closing answer.
    node = post(
        f"{api}/context-tree/projects/{project_id}/nodes",
        {
            "sibling_links": [],
            "header": title,
            "summary": (transcript[-1]["content"] or "")[:300],
            "conversation_id": conversation_id,
            "messages": transcript,
            "topics": spec.get("topics", []),
            "node_type": "conversation",
        },
    )
    print(f"    node {node.get('id')}")

    # Same trigger the browser fires when a conversation is snapshotted, so the text is
    # searchable and the next node can link to it.
    try:
        post(f"{api}/ai/ai-conversations/context-retrieval/reindex/{conversation_id}", None)
    except urllib.error.HTTPError as error:
        print(f"    reindex returned {error.code} (links may lag)")

    return node.get("id")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default=DEFAULT_API, help="API Gateway base URL")
    parser.add_argument("--project", default="pami", help="project name to seed into")
    parser.add_argument("--only", type=int, default=0, help="seed just the first N")
    parser.add_argument(
        "--skip", type=int, default=0, help="skip the first N (already seeded)"
    )
    parser.add_argument(
        "--list", action="store_true", help="print what would be sent and exit"
    )
    parser.add_argument(
        "--pause",
        type=float,
        default=2.0,
        # Linking happens in a background task per node, and each new node scores itself
        # against the ones already indexed. Racing ahead means a node is scored against a
        # peer whose text has not landed yet, and the link it should have had is simply
        # missing.
        help="seconds between conversations, so indexing keeps up",
    )
    args = parser.parse_args()

    specs = CONVERSATIONS[args.skip :]
    if args.only:
        specs = specs[: args.only]

    if args.list:
        for index, spec in enumerate(specs, start=args.skip + 1):
            print(f"{index}. {spec['title']}  ({len(spec['messages'])} messages)")
        return 0

    project_id = find_project(args.api, args.project)
    print(f"Seeding {len(specs)} conversations into {args.project} ({project_id})")

    created = []
    for index, spec in enumerate(specs, start=args.skip + 1):
        node_id = seed_one(args.api, project_id, spec, index)
        if node_id:
            created.append(node_id)
        time.sleep(args.pause)

    print(f"\nDone: {len(created)} of {len(specs)} conversations became nodes.")
    print("Links are written by a background task and appear within a few seconds.")
    return 0 if len(created) == len(specs) else 1


if __name__ == "__main__":
    sys.exit(main())
