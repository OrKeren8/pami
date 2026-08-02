import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { jiraApi } from '../api/axios';
import AppSidebar from '../components/layout/AppSidebar';
import { useToast } from '../components/feedback/ToastProvider';
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
        // The template's preferred type may not exist in this project, so fall back to one
        // that does rather than letting Jira reject the create.
        return match ? match.name : issueTypes[0].name;
    }, [issueTypes, ticket.issueType]);

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
                        <p>
                            Draft a ticket here or ask PAMI to fill it in, then publish it to
                            Jira when it reads right.
                        </p>
                    </div>

                    <div className="jira-header-side">
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
                            <label htmlFor="jira-description">Description</label>
                            <textarea
                                id="jira-description"
                                value={ticket.description}
                                onChange={(event) => patch({ description: event.target.value })}
                                spellCheck="true"
                            />
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
                </section>
            </main>
        </div>
    );
}

export default JiraConsolePage;
