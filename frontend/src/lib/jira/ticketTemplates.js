/**
 * Ticket shapes worth writing, following the team's cx-jira-write-ticket structure.
 *
 * The point of a template is that the blank page already knows what a good ticket contains:
 * a Story leads with the user and its acceptance criteria, a Bug leads with what to do to see
 * it go wrong. Left to a bare description box, both end up as a sentence and a shrug.
 *
 * `body` is the section skeleton the editor starts from, and the same skeleton the AI is told
 * to fill - so a ticket the AI drafts and a ticket a person types look alike.
 */

export const TICKET_TEMPLATES = [
    {
        id: 'story',
        label: 'Story',
        issueType: 'Story',
        hint: 'A change described from the user’s side, with testable criteria.',
        summaryHint: 'Short outcome, e.g. "Filter the graph by conversation age"',
        body: `As a [role], I want [goal], so that [reason].

## User Flow
1.
2.
3.

## AC
-
-

## Edge Cases
- **Case** — handling

## DOD
- [ ]
- [ ]

## Technical Notes
**Scope:** Frontend only / Backend only / Full-stack
**Related tickets:**`
    },
    {
        id: 'bug',
        label: 'Bug',
        issueType: 'Bug',
        hint: 'What goes wrong, how to see it, and what should happen instead.',
        summaryHint: 'The wrong behaviour, e.g. "Graph hides nodes after a rename"',
        body: `## Screen
Where the problem appears.

## Steps to Reproduce
1.
2.
3.

## Actual Behavior


## Expected Behavior


## Impact


## DOD
- [ ] Root cause identified
- [ ] Fix implemented
- [ ] No regression in related flows

## Technical Notes
**Scope:**
**Related tickets:**`
    },
    {
        id: 'task',
        label: 'Task',
        issueType: 'Task',
        hint: 'A concrete piece of work that is not user-facing.',
        summaryHint: 'The work, e.g. "Add an index on conversation_id"',
        body: `## What
The change to make.

## Why
The reason it is worth doing.

## DOD
- [ ]
- [ ]

## Technical Notes
**Scope:**`
    },
    {
        id: 'spike',
        label: 'Spike',
        issueType: 'Task',
        hint: 'A time-boxed question to answer before committing to a build.',
        summaryHint: 'The question, e.g. "Can Cognito groups be managed in the lab account?"',
        body: `## Question
The thing we do not know.

## Why It Blocks Us
What cannot be decided until this is answered.

## Timebox
Half a day / one day.

## Done When
- [ ] The question is answered in writing
- [ ] A recommendation is recorded

## Technical Notes
**Scope:** Investigation only — no production change`
    }
];

export const DEFAULT_TEMPLATE_ID = 'story';

export const templateById = (id) =>
    TICKET_TEMPLATES.find((template) => template.id === id) || TICKET_TEMPLATES[0];

export const PRIORITIES = ['Highest', 'High', 'Medium', 'Low', 'Lowest'];

/** A fresh, empty ticket for the given template. */
export const blankTicket = (templateId = DEFAULT_TEMPLATE_ID, projectKey = '') => {
    const template = templateById(templateId);
    return {
        templateId: template.id,
        projectKey,
        issueType: template.issueType,
        summary: '',
        description: template.body,
        assigneeAccountId: '',
        priority: '',
        dueDate: '',
        labels: ['pami']
    };
};

/** Whether anything has been typed, so "discard" can warn only when there is something to lose. */
export const ticketHasContent = (ticket) => {
    if (!ticket) return false;
    const template = templateById(ticket.templateId);
    return Boolean(
        ticket.summary.trim() ||
            ticket.assigneeAccountId ||
            ticket.priority ||
            ticket.dueDate ||
            // The skeleton itself is not content; only edits to it are.
            ticket.description.trim() !== template.body.trim()
    );
};
