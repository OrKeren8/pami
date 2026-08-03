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

// Jira status names are per project, so match on what they mean rather than on an exact set.
const statusPill = (status) => {
    const name = (status || '').toLowerCase();
    if (name.includes('done') || name.includes('closed') || name.includes('resolved')) {
        return 'ds-pill ds-pill-done';
    }
    if (name.includes('progress') || name.includes('review') || name.includes('doing')) {
        return 'ds-pill ds-pill-progress';
    }
    return 'ds-pill ds-pill-todo';
};

// One box does both jobs: narrow the list, or jump straight to a key. Which one is meant is
// decided by what was typed, not by a second field the user has to find.
const KEY_SHAPE = /^[A-Za-z][A-Za-z0-9_]*-\d+$/;

const shortDate = (iso) => {
    if (!iso) return '';
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return '';
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
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
    // Editing first, formatting on demand. The other way round meant Enter and clicks in
    // the description did something other than type, which is the last thing an editor should
    // do. The Formatted button is right beside the label.
    const [showPreview, setShowPreview] = useState(false);
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
    const [recentIssues, setRecentIssues] = useState([]);
    const [isLoadingRecent, setIsLoadingRecent] = useState(false);
    const [issueFilter, setIssueFilter] = useState('');

    // Nothing said the draft was kept, so closing the tab looked like losing the work.
    const [savedAt, setSavedAt] = useState(null);
    // Discard asks for a second click on the same button instead of offering an Undo at the
    // other end of the row - by the time you have found the undo you have already had the
    // fright, and the two controls being far apart is what made it a fright.
    const [isConfirmingDiscard, setIsConfirmingDiscard] = useState(false);

    useEffect(() => {
        writeStored(DRAFT_KEY, JSON.stringify(ticket));
        setSavedAt(Date.now());
    }, [ticket]);

    useEffect(() => {
        if (projectKey) writeStored(PROJECT_KEY, projectKey);
    }, [projectKey]);

    // A confirm that stays armed forever is a trap: come back to the tab later and the button
    // that says Discard really does discard on one click.
    useEffect(() => {
        if (!isConfirmingDiscard) return undefined;
        const timer = window.setTimeout(() => setIsConfirmingDiscard(false), 6000);
        return () => window.clearTimeout(timer);
    }, [isConfirmingDiscard]);

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

    // The issue browser is a list, not a key to remember. Loaded only in that mode: the
    // compose canvas has no use for it.
    useEffect(() => {
        if (!projectKey || mode !== 'issue') return undefined;

        let cancelled = false;
        setIsLoadingRecent(true);
        jiraApi
            .get(`/projects/${projectKey}/issues`)
            .then((response) => {
                if (!cancelled) setRecentIssues(response.data?.issues || []);
            })
            .catch((error) => {
                console.error('Could not list recent issues:', error);
                if (!cancelled) setRecentIssues([]);
            })
            .finally(() => {
                if (!cancelled) setIsLoadingRecent(false);
            });

        return () => {
            cancelled = true;
        };
    }, [projectKey, mode]);

    // A half-written ticket only lives in this tab, so leaving is worth one question.
    useEffect(() => {
        const warn = (event) => {
            if (!ticketHasContent(ticket)) return undefined;
            event.preventDefault();
            // Browsers show their own wording; the string only has to be non-empty.
            event.returnValue = '';
            return '';
        };
        window.addEventListener('beforeunload', warn);
        return () => window.removeEventListener('beforeunload', warn);
    }, [ticket]);

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

    const openIssue = async (event, explicitKey) => {
        event?.preventDefault();
        // Taken as an argument when a row is clicked: setIssueKeyInput has not applied yet at
        // that point, so reading it from state would open the previous key.
        const key = (explicitKey || issueKeyInput).trim().toUpperCase();
        if (!key) return;

        setIssueKeyInput(key);
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
            setCommentBody('');
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

    const closeIssue = () => {
        setIssue(null);
        setThread([]);
        setCommentBody('');
        setCommentAsk('');
        setIssueError(null);
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
        if (!isConfirmingDiscard && ticketHasContent(ticket)) {
            setIsConfirmingDiscard(true);
            return;
        }
        setIsConfirmingDiscard(false);
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

    const filteredIssues = useMemo(() => {
        const needle = issueFilter.trim().toLowerCase();
        if (!needle) return recentIssues;
        return recentIssues.filter((row) =>
            `${row.key} ${row.summary || ''}`.toLowerCase().includes(needle)
        );
    }, [recentIssues, issueFilter]);

    const renderIssueBrowser = () => (
        <div className="jira-issue-browser">
            <div className="ds-spread jira-browser-head">
                <span className="ds-section-label">
                    {isLoadingRecent
                        ? 'Loading issues…'
                        : recentIssues.length
                          ? `${projectKey} · recently updated`
                          : 'No issues in this project yet'}
                </span>
                <form className="jira-browser-find" onSubmit={openIssue}>
                    <input
                        className="ds-input ds-input-sm"
                        type="text"
                        value={issueFilter}
                        placeholder="Filter, or type a key…"
                        aria-label="Filter issues, or type an issue key"
                        onChange={(event) => {
                            setIssueFilter(event.target.value);
                            setIssueKeyInput(event.target.value);
                        }}
                    />
                    <button
                        type="submit"
                        className="ds-btn ds-btn-ghost ds-btn-sm"
                        disabled={isLoadingIssue || !KEY_SHAPE.test(issueKeyInput.trim())}
                        title="Type a full issue key, e.g. SCRUM-12"
                    >
                        {isLoadingIssue ? 'Opening…' : 'Open'}
                    </button>
                </form>
            </div>

            {issueError && (
                <p className="ds-error" role="alert">
                    {issueError}
                </p>
            )}

            {!isLoadingRecent && recentIssues.length > 0 && filteredIssues.length === 0 && (
                <p className="ds-hint">Nothing matches “{issueFilter}”.</p>
            )}

            <ul className="ds-list jira-issue-list">
                {filteredIssues.map((row) => (
                    <li key={row.key}>
                        <button
                            type="button"
                            className="ds-row"
                            onClick={() => openIssue(null, row.key)}
                        >
                            <span className="jira-row-key">{row.key}</span>
                            <span className="ds-row-truncate">{row.summary}</span>
                            <span className="jira-row-when">{shortDate(row.updated)}</span>
                            <span className={statusPill(row.status)}>{row.status}</span>
                        </button>
                    </li>
                ))}
            </ul>
        </div>
    );

    const renderIssue = () => (
        <div className="jira-issue-detail">
            <div className="jira-issue-head">
                <div className="ds-spread">
                    <button type="button" className="ds-btn ds-btn-quiet" onClick={closeIssue}>
                        &larr; All issues
                    </button>
                    <div className="ds-inline">
                        <button
                            type="button"
                            className="ds-btn ds-btn-ghost ds-btn-sm"
                            onClick={() => openIssue(null, issue.issue_key)}
                            disabled={isLoadingIssue}
                        >
                            {isLoadingIssue ? 'Refreshing…' : 'Refresh'}
                        </button>
                        <a
                            className="jira-open-in-jira"
                            href={issue.issue_url}
                            target="_blank"
                            rel="noreferrer"
                        >
                            Open in Jira ↗
                        </a>
                    </div>
                </div>

                <h2>
                    <span className="jira-issue-key">{issue.issue_key}</span>
                    {issue.summary}
                </h2>

                <div className="ds-inline">
                    {issue.status && (
                        <span className={statusPill(issue.status)}>{issue.status}</span>
                    )}
                    {(issue.labels || []).map((label) => (
                        <span key={label} className="ds-pill ds-pill-accent">
                            {label}
                        </span>
                    ))}
                </div>

                {/* Type, assignee, priority and due date are facts about the issue, not
                    statuses. As pills they crowded out the one pill that matters. */}
                <div className="ds-meta">
                    {issue.issue_type && <span>{issue.issue_type}</span>}
                    <span className="ds-meta-sep" aria-hidden="true" />
                    <span>{issue.assignee || 'Unassigned'}</span>
                    {issue.priority && (
                        <>
                            <span className="ds-meta-sep" aria-hidden="true" />
                            <span>{issue.priority} priority</span>
                        </>
                    )}
                    {issue.due_date && (
                        <>
                            <span className="ds-meta-sep" aria-hidden="true" />
                            <span>due {issue.due_date}</span>
                        </>
                    )}
                </div>
            </div>

            <div className="jira-issue-scroll">
                {/* The description was missing from this view entirely, which is what made an
                    opened issue look empty. Same renderer as the compose preview, so a ticket
                    reads the same before and after it is published. */}
                <section className="jira-issue-section">
                    <span className="ds-section-label">Description</span>
                    {issue.description ? (
                        <div className="jira-description-preview">
                            <TicketPreview text={issue.description} />
                        </div>
                    ) : (
                        <p className="ds-hint">This issue has no description in Jira.</p>
                    )}
                </section>

                <section className="jira-issue-section">
                    <span className="ds-section-label">
                        {thread.length
                            ? `${thread.length} comment${thread.length === 1 ? '' : 's'}`
                            : 'No comments yet'}
                    </span>
                    {thread.map((comment) => (
                        <div key={comment.id} className="jira-comment">
                            <div className="ds-spread">
                                <span className="jira-comment-who">
                                    {comment.author || 'Someone'}
                                </span>
                                <span className="ds-hint">{shortDate(comment.created)}</span>
                            </div>
                            <p>{comment.body}</p>
                        </div>
                    ))}
                </section>
            </div>

            <form className="jira-comment-composer" onSubmit={postComment}>
                {/* One row, not a chat: no history, no transcript. It asks PAMI to write into
                    the box below, which the user then edits and posts. */}
                <div className="jira-assist-row">
                    <input
                        className="ds-input"
                        type="text"
                        value={commentAsk}
                        placeholder="Ask PAMI to draft the reply…"
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
                        className="ds-btn ds-btn-ghost"
                        onClick={askPamiForComment}
                        disabled={isDraftingComment || !commentAsk.trim()}
                    >
                        {isDraftingComment ? 'Drafting…' : 'Draft with PAMI'}
                    </button>
                </div>

                <div className="ds-field">
                    <label htmlFor="jira-comment">Your reply</label>
                    <textarea
                        id="jira-comment"
                        className="ds-textarea jira-comment-box"
                        value={commentBody}
                        placeholder="Write a comment, or ask PAMI to draft one."
                        onChange={(event) => setCommentBody(event.target.value)}
                    />
                </div>

                <div className="ds-spread jira-composer-actions">
                    <span className="ds-hint">PAMI drafts into this box. Posting is your click.</span>
                    <div className="ds-inline">
                        <button
                            type="button"
                            className="ds-btn ds-btn-ghost"
                            onClick={() => setCommentBody('')}
                            disabled={!commentBody}
                        >
                            Clear
                        </button>
                        <button
                            type="submit"
                            className="ds-btn ds-btn-primary"
                            disabled={isPosting || !commentBody.trim()}
                        >
                            {isPosting ? 'Posting…' : 'Post comment'}
                        </button>
                    </div>
                </div>
            </form>
        </div>
    );

    return (
        <div className="dashboard-container jira-page">
            <AppSidebar active="jira" />

            <main className="jira-main">
                <header className="jira-header ds-header-rule">
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
                        <div className="ds-tabs" role="tablist" aria-label="Workspace mode">
                            <button
                                type="button"
                                role="tab"
                                aria-selected={mode === 'compose'}
                                className="ds-tab"
                                onClick={() => setMode('compose')}
                            >
                                New ticket
                            </button>
                            <button
                                type="button"
                                role="tab"
                                aria-selected={mode === 'issue'}
                                className="ds-tab"
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

                        <label className="ds-field jira-project-picker">
                            <span>Project</span>
                            <select
                                className="ds-select"
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
                    <div className="ds-error" role="alert">
                        <strong>Jira is not reachable.</strong>{' '}
                        {connection.detail || 'Check the Jira service configuration.'}
                    </div>
                )}

                <section className="jira-body">
                    {mode === 'issue' ? (
                        <div className="ds-panel ds-panel-pad jira-canvas">
                            {issue ? renderIssue() : renderIssueBrowser()}
                        </div>
                    ) : (
                        <form
                            className="ds-panel ds-panel-pad jira-canvas"
                            onSubmit={submit}
                            onKeyDown={(event) => {
                                // Enter in any single-line field submits a form by default,
                                // which here would publish the ticket to Jira mid-sentence.
                                // Publishing is the button's job only.
                                if (event.key !== 'Enter') return;

                                // Ctrl/Cmd+Enter publishes from anywhere in the form, including
                                // mid-description - the shortcut every issue tracker has.
                                if (event.metaKey || event.ctrlKey) {
                                    event.preventDefault();
                                    submit(event);
                                    return;
                                }

                                if (event.target.tagName !== 'TEXTAREA') {
                                    event.preventDefault();
                                }
                            }}
                        >
                            <div className="ds-panel-head">
                                <div className="ds-tabs" role="tablist" aria-label="Ticket type">
                                    {TICKET_TEMPLATES.map((option) => (
                                        <button
                                            key={option.id}
                                            type="button"
                                            role="tab"
                                            aria-selected={option.id === ticket.templateId}
                                            className="ds-tab"
                                            onClick={() => applyTemplate(option.id)}
                                            title={option.hint}
                                        >
                                            {option.label}
                                        </button>
                                    ))}
                                </div>

                                <span className="ds-hint">{template.hint}</span>
                            </div>

                            <div className="ds-field">
                                <div className="ds-field-head">
                                    <label htmlFor="jira-summary">Summary</label>
                                    {/* Quiet until it matters: Jira rejects an over-long
                                        summary, and finding that out at publish time is late. */}
                                    {ticket.summary.length > 180 && (
                                        <span
                                            className={`jira-counter ${
                                                ticket.summary.length > 250 ? 'over' : ''
                                            }`}
                                        >
                                            {ticket.summary.length} / 250
                                        </span>
                                    )}
                                </div>
                                <input
                                    id="jira-summary"
                                    className="ds-input"
                                    ref={summaryRef}
                                    type="text"
                                    value={ticket.summary}
                                    placeholder={template.summaryHint}
                                    onChange={(event) => patch({ summary: event.target.value })}
                                />
                            </div>

                            <div className="ds-field jira-field-grow">
                                <div className="ds-field-head">
                                    <label htmlFor="jira-description">Description</label>
                                    <button
                                        type="button"
                                        className="ds-btn ds-btn-ghost ds-btn-sm"
                                        onClick={() => setShowPreview((shown) => !shown)}
                                    >
                                        {showPreview ? 'Edit text' : 'Formatted'}
                                    </button>
                                </div>

                                {/* An empty box used to say nothing about what belongs in it or
                                    where a filled one comes from. Both ways out are here. */}
                                {!ticket.description.trim() && (
                                    <div className="ds-empty jira-empty-strip">
                                        <p className="ds-empty-body">
                                            Empty. Start from the skeleton, or ask PAMI in a chat
                                            to draft this from what you discussed.
                                        </p>
                                        <button
                                            type="button"
                                            className="ds-btn ds-btn-ghost ds-btn-sm"
                                            onClick={() => {
                                                patch({ description: template.body });
                                                setShowPreview(false);
                                            }}
                                        >
                                            Load {template.label} skeleton
                                        </button>
                                    </div>
                                )}

                                {showPreview && ticket.description.trim() ? (
                                    <div className="jira-description-preview">
                                        <TicketPreview text={ticket.description} />
                                    </div>
                                ) : (
                                    <textarea
                                        id="jira-description"
                                        className="ds-textarea jira-description-box"
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
                                <label className="ds-field">
                                    <span>Type</span>
                                    <select
                                        className="ds-select"
                                        value={resolvedIssueType}
                                        onChange={(event) =>
                                            patch({ issueType: event.target.value })
                                        }
                                    >
                                        {issueTypes.length ? (
                                            issueTypes.map((type) => (
                                                <option key={type.id} value={type.name}>
                                                    {type.name}
                                                </option>
                                            ))
                                        ) : (
                                            <option value={ticket.issueType}>
                                                {ticket.issueType}
                                            </option>
                                        )}
                                    </select>
                                </label>

                                <label className="ds-field">
                                    <span>Assignee</span>
                                    <select
                                        className="ds-select"
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

                                <label className="ds-field">
                                    <span className="jira-priority-row">
                                        <span
                                            className={`jira-priority-dot jira-priority-${(
                                                ticket.priority || 'none'
                                            ).toLowerCase()}`}
                                            aria-hidden="true"
                                        />
                                        Priority
                                    </span>
                                    <select
                                        className="ds-select"
                                        value={ticket.priority}
                                        onChange={(event) =>
                                            patch({ priority: event.target.value })
                                        }
                                    >
                                        <option value="">Default</option>
                                        {PRIORITIES.map((priority) => (
                                            <option key={priority} value={priority}>
                                                {priority}
                                            </option>
                                        ))}
                                    </select>
                                </label>

                                <label className="ds-field">
                                    <span>Due date</span>
                                    <input
                                        className="ds-input"
                                        type="date"
                                        value={ticket.dueDate}
                                        onChange={(event) => patch({ dueDate: event.target.value })}
                                    />
                                </label>
                            </div>

                            <div className="ds-spread jira-canvas-actions">
                                <div className="ds-inline">
                                    {ticket.labels.map((label) => (
                                        <span key={label} className="ds-pill ds-pill-accent">
                                            {label}
                                        </span>
                                    ))}
                                    {savedAt && <span className="ds-hint">Draft saved</span>}
                                </div>

                                <div className="ds-inline">
                                    {isConfirmingDiscard && (
                                        <button
                                            type="button"
                                            className="ds-btn ds-btn-quiet"
                                            onClick={() => setIsConfirmingDiscard(false)}
                                        >
                                            Keep it
                                        </button>
                                    )}
                                    <button
                                        type="button"
                                        className={`ds-btn ${
                                            isConfirmingDiscard ? 'ds-btn-danger' : 'ds-btn-ghost'
                                        }`}
                                        onClick={discard}
                                    >
                                        {isConfirmingDiscard ? 'Discard for good' : 'Discard'}
                                    </button>
                                    <button
                                        type="submit"
                                        className="ds-btn ds-btn-primary"
                                        disabled={
                                            isSubmitting || connection.status !== 'connected'
                                        }
                                    >
                                        {isSubmitting ? 'Publishing…' : 'Submit to Jira'}
                                    </button>
                                </div>
                            </div>

                            {/* Inside the form so Enter in a field is handled by the same
                                keydown rule as the rest of the canvas. */}
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
                    )}
                </section>
            </main>
        </div>
    );
}

export default JiraConsolePage;
