import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { aiApi, jiraApi } from '../api/axios';
import AppSidebar from '../components/layout/AppSidebar';
import { useToast } from '../components/feedback/ToastProvider';
import TicketPreview from '../components/jira/TicketPreview';
import { clearDraftOrigin, readDraftOrigin } from '../lib/jira/jiraHandoff';
import {
    PRIORITIES,
    TICKET_TEMPLATES,
    blankTicket,
    templateById,
    ticketHasContent
} from '../lib/jira/ticketTemplates';
import './HomePage.css';
import './JiraConsolePage.css';

// The draft survives a refresh: it is the one thing on this page a user would be upset to
// lose, and it only exists in the browser until they press Submit.
const DRAFT_KEY = 'pami.jira.draft';
const PROJECT_KEY = 'pami.jira.projectKey';

const readStored = (key) => {
    try {
        return window.localStorage.getItem(key);
    } catch (error) {
        return null;
    }
};

const writeStored = (key, value) => {
    try {
        if (value === null) window.localStorage.removeItem(key);
        else window.localStorage.setItem(key, value);
    } catch (error) {
        /* a blocked localStorage only costs the saved draft */
    }
};

const loadDraft = () => {
    const raw = readStored(DRAFT_KEY);
    if (!raw) return null;
    try {
        const parsed = JSON.parse(raw);
        return parsed && typeof parsed === 'object' ? parsed : null;
    } catch (error) {
        return null;
    }
};

function JiraConsolePage() {
    const toast = useToast();

    const [connection, setConnection] = useState({ status: 'checking', detail: null });
    const [projects, setProjects] = useState([]);
    const [projectKey, setProjectKey] = useState(readStored(PROJECT_KEY) || '');
    const [issueTypes, setIssueTypes] = useState([]);
    const [users, setUsers] = useState([]);
    const [ticket, setTicket] = useState(() => loadDraft() || blankTicket());
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [lastCreated, setLastCreated] = useState(null);
    const summaryRef = useRef(null);
    // Formatted by default: the templates are full of ## headings and - [ ] boxes, which
    // read as punctuation in a textarea. Editing is one click away.
    const [showPreview, setShowPreview] = useState(true);
    // Set when the chat handed this draft over, so there is a way back to the exact
    // conversation that produced it.
    const [origin] = useState(() => readDraftOrigin());

    // Two modes in one window: writing a new ticket, or replying on an existing one. A second
    // page would have duplicated the sidebar, the connection check and the project picker.
    const [mode, setMode] = useState('compose');
    const [issueKeyInput, setIssueKeyInput] = useState('');
    const [issue, setIssue] = useState(null);
    const [thread, setThread] = useState([]);
    const [isLoadingIssue, setIsLoadingIssue] = useState(false);
    const [issueError, setIssueError] = useState(null);
    const [commentBody, setCommentBody] = useState('');
    const [isPosting, setIsPosting] = useState(false);
    const [isDraftingComment, setIsDraftingComment] = useState(false);
    const [commentAsk, setCommentAsk] = useState('');


    useEffect(() => {
        writeStored(DRAFT_KEY, JSON.stringify(ticket));
    }, [ticket]);

    useEffect(() => {
        if (projectKey) writeStored(PROJECT_KEY, projectKey);
    }, [projectKey]);

    const patch = useCallback((fields) => {
        setTicket((current) => ({ ...current, ...fields }));
    }, []);

    // --- Connection and reference data -------------------------------------------------

    const connect = useCallback(async () => {
        setConnection({ status: 'checking', detail: null });
        try {
            const [checked, listed] = await Promise.all([
                jiraApi.post('/connection-check'),
                jiraApi.get('/list-projects')
            ]);
            const found = listed.data?.projects || [];
            setProjects(found);
            setConnection({
                status: 'connected',
                detail: `${checked.data?.total_projects ?? found.length} project(s)`
            });

            setProjectKey((current) => {
                if (current && found.some((project) => project.key === current)) return current;
                return found[0]?.key || '';
            });
        } catch (error) {
            console.error('Jira connection failed:', error);
            // The service reports which environment variable is missing, and that is the one
            // useful thing to pass on rather than a generic failure.
            const detail = error?.response?.data?.detail;
            setConnection({
                status: 'error',
                detail: typeof detail === 'string' ? detail.slice(0, 160) : null
            });
        }
    }, []);

    useEffect(() => {
        connect();
    }, [connect]);

    useEffect(() => {
        if (!projectKey) {
            setIssueTypes([]);
            setUsers([]);
            return;
        }

        let cancelled = false;
        const load = async () => {
            // Independent of each other, and neither is worth failing the page over: without
            // them the editor falls back to a free-text type and an unassigned ticket.
            const [typesResult, usersResult] = await Promise.allSettled([
                jiraApi.get(`/projects/${projectKey}/issue-types`),
                jiraApi.get(`/projects/${projectKey}/users`)
            ]);
            if (cancelled) return;

            setIssueTypes(
                typesResult.status === 'fulfilled'
                    ? typesResult.value.data?.issue_types || []
                    : []
            );
            setUsers(
                usersResult.status === 'fulfilled' ? usersResult.value.data?.users || [] : []
            );
        };

        load();
        return () => {
            cancelled = true;
        };
    }, [projectKey]);

    // --- Template, submit, discard -----------------------------------------------------

    const applyTemplate = (templateId) => {
        const template = templateById(templateId);
        const previous = templateById(ticket.templateId);
        const untouched = ticket.description.trim() === previous.body.trim();

        // Only overwrite the description when it is still the previous skeleton. Someone who
        // has written three paragraphs and then browses the templates should not lose them.
        setTicket((current) => ({
            ...current,
            templateId: template.id,
            issueType: template.issueType,
            description: untouched ? template.body : current.description
        }));

        if (!untouched) {
            toast.notify(
                'Switched the ticket type. Your description was kept - clear it to load the template.'
            );
        }
    };

    const resolvedIssueType = useMemo(() => {
        if (!issueTypes.length) return ticket.issueType;

        const match = issueTypes.find(
            (type) => type.name.toLowerCase() === ticket.issueType.toLowerCase()
        );
        if (match) return match.name;

        // The template's preferred type may not exist here - a team-managed project can offer
        // only Epic and Task, which is what the live SCRUM project does - so fall back rather
        // than letting Jira reject the create. Task before the first entry on purpose: filing
        // a bug as an Epic is worse than filing it as a Task, and Epic often sorts first.
        const task = issueTypes.find((type) => type.name.toLowerCase() === 'task');
        const nonEpic = issueTypes.find((type) => type.name.toLowerCase() !== 'epic');
        return (task || nonEpic || issueTypes[0]).name;
    }, [issueTypes, ticket.issueType]);

    // --- Replying on an existing issue -------------------------------------------------

    const openIssue = async (event) => {
        event?.preventDefault();
        const key = issueKeyInput.trim().toUpperCase();
        if (!key) return;

        setIsLoadingIssue(true);
        setIssueError(null);
        try {
            // Both at once: an issue with no comments is a normal state, and the header should
            // not wait on the thread to render.
            const [issueResult, commentsResult] = await Promise.all([
                jiraApi.get(`/issues/${key}`),
                jiraApi.get(`/issues/${key}/comments`)
            ]);
            setIssue(issueResult.data || null);
            setThread(commentsResult.data?.comments || []);
        } catch (error) {
            console.error('Could not open the issue:', error);
            const status = error?.response?.status;
            setIssue(null);
            setThread([]);
            setIssueError(
                status === 404
                    ? `No issue called ${key}, or you cannot see it.`
                    : 'Could not load that issue. Please try again.'
            );
        } finally {
            setIsLoadingIssue(false);
        }
    };

    const refreshThread = async () => {
        if (!issue?.issue_key) return;
        try {
            const response = await jiraApi.get(`/issues/${issue.issue_key}/comments`);
            setThread(response.data?.comments || []);
        } catch (error) {
            console.error('Could not refresh the thread:', error);
        }
    };

    const askPamiForComment = async () => {
        const ask = commentAsk.trim();
        if (!ask || !issue?.issue_key || isDraftingComment) return;

        setIsDraftingComment(true);
        try {
            const response = await aiApi.post('/jira-drafts/comment', {
                issue_key: issue.issue_key,
                issue_summary: issue.summary || '',
                message: ask,
                // The thread as displayed. Sent from here so the AI service needs no route to
                // Jira, and so PAMI replies to what the user is actually looking at.
                thread: thread.map((comment) => ({
                    author: comment.author,
                    body: comment.body
                }))
            });
            // Into the composer, not straight onto the issue: posting is the user's click, the
            // same rule the ticket canvas follows.
            setCommentBody(response.data?.comment || '');
            setCommentAsk('');
            if (response.data?.reply) toast.notify(response.data.reply, { duration: 7000 });
        } catch (error) {
            console.error('PAMI could not draft the comment:', error);
            toast.error(
                error?.response?.status === 503
                    ? 'Comment drafting is not available right now.'
                    : 'PAMI could not draft that comment. Try rephrasing.'
            );
        } finally {
            setIsDraftingComment(false);
        }
    };

    const postComment = async (event) => {
        event.preventDefault();
        const body = commentBody.trim();
        if (!body || !issue?.issue_key) return;

        setIsPosting(true);
        try {
            await jiraApi.post(`/issues/${issue.issue_key}/comments`, { body });
            setCommentBody('');
            await refreshThread();
            toast.success(`Posted to ${issue.issue_key}.`);
        } catch (error) {
            console.error('Could not post the comment:', error);
            toast.error('Could not post that comment. Please try again.');
        } finally {
            setIsPosting(false);
        }
    };

    const discard = () => {
        if (
            ticketHasContent(ticket) &&
            !window.confirm('Discard this ticket and start a new one? This cannot be undone.')
        ) {
            return;
        }
        setTicket(blankTicket(ticket.templateId, projectKey));
        setLastCreated(null);
        summaryRef.current?.focus();
    };

    const submit = async (event) => {
        event.preventDefault();

        if (!projectKey) {
            toast.error('Choose a Jira project first.');
            return;
        }
        if (!ticket.summary.trim()) {
            toast.error('A ticket needs a summary.');
            summaryRef.current?.focus();
            return;
        }

        setIsSubmitting(true);
        try {
            const response = await jiraApi.post('/issues', {
                project_key: projectKey,
                summary: ticket.summary.trim(),
                description: ticket.description.trim() || null,
                issue_type: resolvedIssueType,
                priority: ticket.priority || null,
                due_date: ticket.dueDate || null,
                labels: ticket.labels,
                assignee_account_id: ticket.assigneeAccountId || null
            });

            const created = response.data || {};
            setLastCreated({ key: created.issue_key, url: created.issue_url });
            toast.success(`Created ${created.issue_key} in Jira.`);

            // A submitted ticket is done, so the canvas clears - which is the whole "new
            // canvas appears" behaviour, just reached by succeeding instead of discarding.
            setTicket(blankTicket(ticket.templateId, projectKey));
            } catch (error) {
            console.error('Failed to create the Jira issue:', error);
            const detail = error?.response?.data?.detail;
            toast.error(
                typeof detail === 'string'
                    ? `Jira rejected the ticket: ${detail.slice(0, 200)}`
                    : 'Could not create the ticket in Jira. Please try again.'
            );
        } finally {
            setIsSubmitting(false);
        }
    };

    // --- Render ------------------------------------------------------------------------

    const template = templateById(ticket.templateId);
    const statusLabel = {
        checking: 'Checking…',
        connected: 'Connected',
        error: 'Not connected'
    }[connection.status];

    return (
        <div className="dashboard-container jira-page">
            <AppSidebar active="jira" onJira={() => {}} />

            <main className="jira-main">
                <header className="jira-header">
                    <div className="jira-heading">
                        <span className="jira-kicker">Jira</span>
                        <h1>Ticket workspace</h1>
                        {origin?.conversationId && (
                            <a
                                className="jira-back-to-chat"
                                href={`/dashboard?conversation=${encodeURIComponent(
                                    origin.conversationId
                                )}`}
                                onClick={clearDraftOrigin}
                            >
                                &larr; Back to the chat this came from
                            </a>
                        )}
                    </div>

                    <div className="jira-header-side">
                        <div className="jira-mode-tabs" role="tablist" aria-label="Workspace mode">
                            <button
                                type="button"
                                role="tab"
                                aria-selected={mode === 'compose'}
                                className={`jira-mode-tab ${mode === 'compose' ? 'active' : ''}`}
                                onClick={() => setMode('compose')}
                            >
                                New ticket
                            </button>
                            <button
                                type="button"
                                role="tab"
                                aria-selected={mode === 'issue'}
                                className={`jira-mode-tab ${mode === 'issue' ? 'active' : ''}`}
                                onClick={() => setMode('issue')}
                            >
                                Open issue
                            </button>
                        </div>

                        <div className={`jira-status jira-status-${connection.status}`}>
                            <span className="jira-status-dot" aria-hidden="true" />
                            <span>{statusLabel}</span>
                            {connection.status === 'error' && (
                                <button type="button" className="jira-retry" onClick={connect}>
                                    Retry
                                </button>
                            )}
                        </div>

                        <label className="jira-control">
                            <span>Project</span>
                            <select
                                value={projectKey}
                                onChange={(event) => setProjectKey(event.target.value)}
                                disabled={!projects.length}
                            >
                                {!projects.length && <option value="">No projects</option>}
                                {projects.map((project) => (
                                    <option key={project.key} value={project.key}>
                                        {project.key} — {project.name}
                                    </option>
                                ))}
                            </select>
                        </label>
                    </div>
                </header>

                {connection.status === 'error' && (
                    <div className="jira-banner" role="alert">
                        <strong>Jira is not reachable.</strong>{' '}
                        {connection.detail || 'Check the Jira service configuration.'}
                    </div>
                )}

                <section className="jira-body">
                  {mode === 'issue' ? (
                    <>
                    <div className="jira-canvas">
                        <form className="jira-issue-open" onSubmit={openIssue}>
                            <div className="jira-field">
                                <label htmlFor="jira-issue-key">Issue key</label>
                                <input
                                    id="jira-issue-key"
                                    type="text"
                                    value={issueKeyInput}
                                    placeholder={`${projectKey || 'SCRUM'}-123`}
                                    onChange={(event) => setIssueKeyInput(event.target.value)}
                                />
                            </div>
                            <button
                                type="submit"
                                className="jira-btn jira-btn-primary"
                                disabled={isLoadingIssue || !issueKeyInput.trim()}
                            >
                                {isLoadingIssue ? 'Opening...' : 'Open'}
                            </button>
                        </form>

                        {issueError && (
                            <p className="jira-issue-error" role="alert">
                                {issueError}
                            </p>
                        )}

                        {issue && (
                            <>
                                <div className="jira-issue-head">
                                    <a href={issue.issue_url} target="_blank" rel="noreferrer">
                                        {issue.issue_key}
                                    </a>
                                    <h2>{issue.summary}</h2>
                                    <div className="jira-issue-meta">
                                        {issue.status && <span>{issue.status}</span>}
                                        {issue.issue_type && <span>{issue.issue_type}</span>}
                                        <span>{issue.assignee || 'Unassigned'}</span>
                                    </div>
                                </div>

                                <div className="jira-thread">
                                    <span className="jira-thread-label">
                                        {thread.length
                                            ? `${thread.length} comment${
                                                  thread.length === 1 ? '' : 's'
                                              }`
                                            : 'No comments yet'}
                                    </span>
                                    {thread.map((comment) => (
                                        <div key={comment.id} className="jira-comment">
                                            <span className="jira-comment-who">
                                                {comment.author || 'Someone'}
                                            </span>
                                            <p>{comment.body}</p>
                                        </div>
                                    ))}
                                </div>

                                <form className="jira-comment-composer" onSubmit={postComment}>
                                    {/* One row, not a chat: no history, no transcript. It asks
                                        PAMI to write into the box below, which the user then
                                        edits and posts. */}
                                    <div className="jira-assist-row">
                                        <input
                                            type="text"
                                            value={commentAsk}
                                            placeholder="Ask PAMI to draft the reply..."
                                            onChange={(event) => setCommentAsk(event.target.value)}
                                            onKeyDown={(event) => {
                                                if (event.key === 'Enter') {
                                                    event.preventDefault();
                                                    askPamiForComment();
                                                }
                                            }}
                                        />
                                        <button
                                            type="button"
                                            className="jira-btn jira-btn-ghost"
                                            onClick={askPamiForComment}
                                            disabled={isDraftingComment || !commentAsk.trim()}
                                        >
                                            {isDraftingComment ? 'Drafting...' : 'Draft with PAMI'}
                                        </button>
                                    </div>

                                    <div className="jira-field">
                                        <label htmlFor="jira-comment">Your reply</label>
                                        <textarea
                                            id="jira-comment"
                                            value={commentBody}
                                            placeholder="Write a comment, or ask PAMI to draft one."
                                            onChange={(event) =>
                                                setCommentBody(event.target.value)
                                            }
                                        />
                                    </div>
                                    <div className="jira-canvas-actions">
                                        <span className="jira-template-hint">
                                            PAMI drafts into this box. Posting is your click.
                                        </span>
                                        <div className="jira-buttons">
                                            <button
                                                type="button"
                                                className="jira-btn jira-btn-ghost"
                                                onClick={() => setCommentBody('')}
                                                disabled={!commentBody}
                                            >
                                                Clear
                                            </button>
                                            <button
                                                type="submit"
                                                className="jira-btn jira-btn-primary"
                                                disabled={isPosting || !commentBody.trim()}
                                            >
                                                {isPosting ? 'Posting...' : 'Post comment'}
                                            </button>
                                        </div>
                                    </div>
                                </form>
                            </>
                        )}
                    </div>

                    </>
                  ) : (
                    <>
                    <form className="jira-canvas" onSubmit={submit}>
                        <div className="jira-canvas-head">
                            <div className="jira-template-tabs" role="tablist" aria-label="Ticket type">
                                {TICKET_TEMPLATES.map((option) => (
                                    <button
                                        key={option.id}
                                        type="button"
                                        role="tab"
                                        aria-selected={option.id === ticket.templateId}
                                        className={`jira-template-tab ${
                                            option.id === ticket.templateId ? 'active' : ''
                                        }`}
                                        onClick={() => applyTemplate(option.id)}
                                        title={option.hint}
                                    >
                                        {option.label}
                                    </button>
                                ))}
                            </div>

                            <span className="jira-template-hint">{template.hint}</span>
                        </div>

                        <div className="jira-field">
                            <label htmlFor="jira-summary">Summary</label>
                            <input
                                id="jira-summary"
                                ref={summaryRef}
                                type="text"
                                value={ticket.summary}
                                placeholder={template.summaryHint}
                                onChange={(event) => patch({ summary: event.target.value })}
                            />
                        </div>

                        <div className="jira-field jira-field-grow">
                            <div className="jira-description-head">
                                <label htmlFor="jira-description">Description</label>
                                <button
                                    type="button"
                                    className="jira-preview-toggle"
                                    onClick={() => setShowPreview((shown) => !shown)}
                                >
                                    {showPreview ? 'Edit text' : 'Formatted'}
                                </button>
                            </div>

                            {showPreview ? (
                                // Clicking the rendered ticket drops straight into editing it,
                                // so the formatted view is not a dead end.
                                <div
                                    className="jira-description-preview"
                                    role="button"
                                    tabIndex={0}
                                    title="Click to edit"
                                    onClick={() => setShowPreview(false)}
                                    onKeyDown={(event) => {
                                        if (event.key === 'Enter') setShowPreview(false);
                                    }}
                                >
                                    <TicketPreview text={ticket.description} />
                                </div>
                            ) : (
                                <textarea
                                    id="jira-description"
                                    value={ticket.description}
                                    onChange={(event) =>
                                        patch({ description: event.target.value })
                                    }
                                    spellCheck="true"
                                    autoFocus
                                />
                            )}
                        </div>

                        <div className="jira-field-row">
                            <label className="jira-field">
                                <span>Type</span>
                                <select
                                    value={resolvedIssueType}
                                    onChange={(event) => patch({ issueType: event.target.value })}
                                >
                                    {issueTypes.length ? (
                                        issueTypes.map((type) => (
                                            <option key={type.id} value={type.name}>
                                                {type.name}
                                            </option>
                                        ))
                                    ) : (
                                        <option value={ticket.issueType}>{ticket.issueType}</option>
                                    )}
                                </select>
                            </label>

                            <label className="jira-field">
                                <span>Assignee</span>
                                <select
                                    value={ticket.assigneeAccountId}
                                    onChange={(event) =>
                                        patch({ assigneeAccountId: event.target.value })
                                    }
                                >
                                    <option value="">Unassigned</option>
                                    {users.map((user) => (
                                        <option key={user.account_id} value={user.account_id}>
                                            {user.display_name}
                                        </option>
                                    ))}
                                </select>
                            </label>

                            <label className="jira-field">
                                <span>Priority</span>
                                <select
                                    value={ticket.priority}
                                    onChange={(event) => patch({ priority: event.target.value })}
                                >
                                    <option value="">Default</option>
                                    {PRIORITIES.map((priority) => (
                                        <option key={priority} value={priority}>
                                            {priority}
                                        </option>
                                    ))}
                                </select>
                            </label>

                            <label className="jira-field">
                                <span>Due date</span>
                                <input
                                    type="date"
                                    value={ticket.dueDate}
                                    onChange={(event) => patch({ dueDate: event.target.value })}
                                />
                            </label>
                        </div>

                        <div className="jira-canvas-actions">
                            <div className="jira-labels">
                                {ticket.labels.map((label) => (
                                    <span key={label} className="jira-label">
                                        {label}
                                    </span>
                                ))}
                            </div>

                            <div className="jira-buttons">
                                <button
                                    type="button"
                                    className="jira-btn jira-btn-ghost"
                                    onClick={discard}
                                >
                                    Discard
                                </button>
                                <button
                                    type="submit"
                                    className="jira-btn jira-btn-primary"
                                    disabled={isSubmitting || connection.status !== 'connected'}
                                >
                                    {isSubmitting ? 'Publishing…' : 'Submit to Jira'}
                                </button>
                            </div>
                        </div>

                        {/* Placed inside the form so Enter in a field submits the ticket, not
                            the chat - the chat has its own form below. */}
                        {lastCreated?.key && (
                            <p className="jira-created" role="status">
                                Published{' '}
                                <a href={lastCreated.url} target="_blank" rel="noreferrer">
                                    {lastCreated.key}
                                </a>
                                . The canvas is ready for the next one.
                            </p>
                        )}
                    </form>

                    </>
                  )}
                </section>
            </main>
        </div>
    );
}

export default JiraConsolePage;
