# Feature ideas

Ideas that were proposed and parked, kept here so they survive the conversation they came from.
Each one says what it is, why it fits PAMI specifically, and what already exists so the cost is
honest. Delete an entry when it ships or when it stops being a good idea — a backlog that only
grows is a backlog nobody reads.

**In progress:** Time machine (below).

---

## 1. Time machine — *chosen, in progress*

A scrubber under the graph. Drag it back and the project rewinds: nodes disappear, links unwind,
conversations un-happen. Let go and it plays forward.

- **Why it fits:** the graph is a static picture of the present. The project's shape over time is
  the more interesting story, and it is the thing that reads best to someone seeing PAMI for the
  first time.
- **Already exists:** `created_at` on every node, conversation and task; the graph renders from a
  plain node list, so a filtered list is all the rewind needs.
- **Size:** small–medium, almost entirely frontend.

## 2. Ticket status on the graph

When a node's ticket is published, the node shows its live Jira state (To Do / In Progress /
Done) and colours accordingly.

- **Why it fits:** joins the two halves of the product — what was discussed and what is actually
  moving — so the graph becomes a status board rather than a memory.
- **Already exists:** `GET /jira/projects/{key}/issues` returns key, status and updated time;
  nodes already carry a `conversation_id` and could carry an issue key.
- **Size:** small. Needs an `issue_key` on the node, written when a ticket is published from a
  draft that came from that node's conversation.

## 3. Topic focus

Type a topic, or pick one of the stored chips, and the graph dims everything except matching
nodes and their links.

- **Why it fits:** at fifty nodes the graph is a hairball. Nodes already store `topics`, which
  nothing in the UI reads today.
- **Size:** small. The dim-and-highlight pass already exists for the create-node spotlight.

## 4. "You've been here before"

You start a new chat and type the first message. PAMI answers: *this is 84% the conversation
"Feature envs" from 30 July — continue there instead?* One click and you are in the old thread.

- **Why it fits:** this is the thesis on the tin. Today PAMI remembers only when asked; this
  makes it remember before an hour is spent re-explaining something.
- **Already exists:** the whole embedding and similarity stack, including calibrated floors per
  model and near-peer reporting. It needs one similarity call against the first message.
- **Size:** small–medium. The judgement call is the threshold: too low and it nags.

## 5. Onboarding brief

One button: "explain this project to someone new". PAMI reads everything and writes a brief —
what the project is, the decisions taken and why, what is in flight, where the risks are — with
every claim linked to the conversation it came from.

- **Why it fits:** the most impressive single artefact the system could produce, and the
  citations are what prove the memory is real rather than plausible.
- **Already exists:** retrieval, transcripts, node summaries.
- **Size:** medium. Needs a bounded read strategy so the cost does not scale with the whole
  project, and the same verbatim-quote check any extraction feature needs.

## 6. Standup in one click

"What I did / what is next / what is blocked", assembled from the last few days of conversations
plus Jira activity, ready to post to a Slack channel.

- **Why it fits:** the only idea here that would be used every morning.
- **Already exists:** the Slack writer, Jira recent-issues, conversation timestamps.
- **Size:** medium.

## 7. Talk to PAMI

Hold a key and speak; the browser transcribes and sends it.

- **Why it fits:** costs almost nothing and changes how the product feels to use.
- **Already exists:** everything — the Web Speech API needs no backend, and the chat already
  handles streaming-looking replies and autoscroll.
- **Size:** small. Browser support is the catch: Chrome is fine, Firefox is not.

## 8. Open loops — *proposed, not wanted*

PAMI surfaces what was left hanging: commitments, unanswered questions, decisions never acted
on, each traceable to the message that produced it.

Kept because the reasoning behind it still holds even though the feature was passed over: the
**Task model is fully built and completely unused** — status, due date, assignee, dependencies,
CRUD routes, a Mongo index — and the UI only ever reads it, so every node modal reports zero
tasks forever. Whatever eventually fills that subsystem, this is the note that it is sitting
there empty.
