import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { aiApi, projectsApi } from '../api/axios';
import AppSidebar from '../components/layout/AppSidebar';
import './HomePage.css';
import './ChatViewPage.css';

const SORTS = [
    { id: 'updated_at', label: 'Last used' },
    { id: 'created_at', label: 'Created' }
];

const STORED_PROJECT_KEY = 'pami.chatView.projectId';

// Long enough to cross the gap between a card and the preview without it vanishing, short
// enough that moving down the list does not leave the wrong preview on screen.
const PREVIEW_CLOSE_DELAY_MS = 180;
const PREVIEW_MESSAGE_LIMIT = 6;

const resolveProjectId = (project) =>
    project?.id || project?._id?.$oid || (project?._id ? String(project._id) : null);

const asUtc = (iso) => {
    if (!iso) return null;
    const date = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`);
    return Number.isNaN(date.getTime()) ? null : date;
};

/** "2 hours ago" reads faster than a timestamp when scanning for the one you just left. */
const relativeTime = (iso) => {
    const then = asUtc(iso);
    if (!then) return 'unknown';

    const seconds = Math.max(0, (Date.now() - then.getTime()) / 1000);
    const units = [
        ['year', 31536000],
        ['month', 2592000],
        ['day', 86400],
        ['hour', 3600],
        ['minute', 60]
    ];
    for (const [unit, size] of units) {
        const value = Math.floor(seconds / size);
        if (value >= 1) return `${value} ${unit}${value === 1 ? '' : 's'} ago`;
    }
    return 'just now';
};

const absoluteTime = (iso) => asUtc(iso)?.toLocaleString() || '';

function ChatViewPage() {
    const navigate = useNavigate();

    const [projects, setProjects] = useState([]);
    const [projectId, setProjectId] = useState(null);
    const [conversations, setConversations] = useState([]);
    // conversation_id -> { header, summary } from the context node the conversation became.
    const [nodeInfo, setNodeInfo] = useState({});
    const [sortBy, setSortBy] = useState(SORTS[0].id);
    const [search, setSearch] = useState('');
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);

    const [previewId, setPreviewId] = useState(null);
    const [snippets, setSnippets] = useState({});
    const closeTimerRef = useRef(null);

    useEffect(() => {
        let cancelled = false;

        const loadProjects = async () => {
            try {
                const response = await projectsApi.get('/projects/');
                if (cancelled) return;

                const list = response.data || [];
                setProjects(list);

                let stored = null;
                try {
                    stored = window.localStorage.getItem(STORED_PROJECT_KEY);
                } catch (storageError) {
                    stored = null;
                }
                const ids = list.map(resolveProjectId).filter(Boolean);
                setProjectId(ids.includes(stored) ? stored : ids[0] || null);
            } catch (loadError) {
                if (cancelled) return;
                console.error('Failed to load projects:', loadError);
                setError('Could not load your projects.');
                setIsLoading(false);
            }
        };

        loadProjects();
        return () => {
            cancelled = true;
        };
    }, []);

    const loadConversations = useCallback(async () => {
        if (!projectId) return;

        setIsLoading(true);
        setError(null);
        try {
            // The nodes carry the AI-written header and summary; a conversation's own title is
            // generated as "AI Discussion - <node id>". A failed node fetch only costs the
            // summaries, so it must not take the list down with it.
            const [conversationsResponse, nodesResponse] = await Promise.all([
                aiApi.get(`/ai-conversations/project/${projectId}`),
                projectsApi
                    .get(`/context-tree/projects/${projectId}/nodes`)
                    .catch(() => ({ data: [] }))
            ]);

            setConversations(conversationsResponse.data || []);
            setNodeInfo(
                Object.fromEntries(
                    (nodesResponse.data || [])
                        .filter((node) => node.conversation_id)
                        .map((node) => [
                            node.conversation_id,
                            { header: node.header, summary: node.summary }
                        ])
                )
            );
        } catch (loadError) {
            console.error('Failed to load conversations:', loadError);
            setError('Could not load the conversations for this project.');
        } finally {
            setIsLoading(false);
        }
    }, [projectId]);

    useEffect(() => {
        if (!projectId) return;
        try {
            window.localStorage.setItem(STORED_PROJECT_KEY, projectId);
        } catch (storageError) {
            /* a blocked localStorage only costs the remembered project */
        }
        loadConversations();
    }, [projectId, loadConversations]);

    const decorated = useMemo(
        () =>
            conversations.map((conversation) => {
                const node = nodeInfo[conversation.conversation_id] || {};
                return {
                    ...conversation,
                    // Falls back to the opening question, which is still more use than the
                    // generated title, and only then to a placeholder.
                    displayTitle:
                        node.header || conversation.preview || 'Untitled conversation',
                    displaySummary: node.summary || null
                };
            }),
        [conversations, nodeInfo]
    );

    const visible = useMemo(() => {
        const needle = search.trim().toLowerCase();
        const matches = needle
            ? decorated.filter((conversation) =>
                  `${conversation.displayTitle} ${conversation.displaySummary || ''} ${
                      conversation.preview || ''
                  }`
                      .toLowerCase()
                      .includes(needle)
              )
            : decorated;

        // Copied before sorting: the fetched array is state, and sorting in place would
        // mutate it without React knowing.
        return [...matches].sort((left, right) =>
            String(right[sortBy] || '').localeCompare(String(left[sortBy] || ''))
        );
    }, [decorated, search, sortBy]);

    const loadSnippet = useCallback(async (conversationId) => {
        setSnippets((current) =>
            current[conversationId] ? current : { ...current, [conversationId]: 'loading' }
        );
        try {
            const response = await aiApi.get(`/ai-conversations/${conversationId}`);
            const messages = (response.data?.messages || [])
                .filter((message) => String(message.content || '').trim())
                .slice(0, PREVIEW_MESSAGE_LIMIT)
                .map((message) => ({
                    role: message.role === 'user' ? 'user' : 'assistant',
                    content: String(message.content)
                }));
            setSnippets((current) => ({ ...current, [conversationId]: messages }));
        } catch (snippetError) {
            console.error('Failed to load the conversation snippet:', snippetError);
            setSnippets((current) => ({ ...current, [conversationId]: 'error' }));
        }
    }, []);

    const showPreview = useCallback(
        (conversationId) => {
            clearTimeout(closeTimerRef.current);
            setPreviewId(conversationId);
            setSnippets((current) => {
                if (!current[conversationId]) loadSnippet(conversationId);
                return current;
            });
        },
        [loadSnippet]
    );

    const hidePreview = useCallback(() => {
        clearTimeout(closeTimerRef.current);
        closeTimerRef.current = setTimeout(
            () => setPreviewId(null),
            PREVIEW_CLOSE_DELAY_MS
        );
    }, []);

    useEffect(() => () => clearTimeout(closeTimerRef.current), []);

    useEffect(() => {
        if (!previewId) return undefined;
        const onKeyDown = (event) => {
            if (event.key === 'Escape') {
                clearTimeout(closeTimerRef.current);
                setPreviewId(null);
            }
        };
        window.addEventListener('keydown', onKeyDown);
        return () => window.removeEventListener('keydown', onKeyDown);
    }, [previewId]);

    const openConversation = (conversationId) => {
        navigate(`/dashboard?conversation=${encodeURIComponent(conversationId)}`);
    };

    const projectName = useMemo(() => {
        const match = projects.find((project) => resolveProjectId(project) === projectId);
        return match?.name || 'project';
    }, [projects, projectId]);

    const previewed = visible.find(
        (conversation) => conversation.conversation_id === previewId
    );

    const previewBody = () => {
        const snippet = snippets[previewId];
        if (snippet === 'loading' || snippet === undefined) {
            return <p className="chat-preview-note">Loading the conversation…</p>;
        }
        if (snippet === 'error') {
            return <p className="chat-preview-note">Could not load this conversation.</p>;
        }
        if (!snippet.length) {
            return <p className="chat-preview-note">This conversation is empty.</p>;
        }
        return snippet.map((message, index) => (
            <p key={index} className={`chat-preview-line chat-preview-${message.role}`}>
                <span className="chat-preview-role">
                    {message.role === 'user' ? 'You' : 'PAMI'}
                </span>
                {message.content}
            </p>
        ));
    };

    const body = () => {
        if (isLoading) {
            return (
                <div className="ds-state">
                    <span className="ds-spinner" aria-hidden="true" />
                    <p>Loading conversations…</p>
                </div>
            );
        }

        if (error) {
            return (
                <div className="ds-state">
                    <p>{error}</p>
                    <button type="button" className="ds-btn ds-btn-primary ds-btn-sm" onClick={loadConversations}>
                        Try again
                    </button>
                </div>
            );
        }

        if (!conversations.length) {
            return (
                <div className="ds-state">
                    <p>No conversations in {projectName} yet.</p>
                    <button
                        type="button"
                        className="ds-btn ds-btn-primary ds-btn-sm"
                        onClick={() => navigate('/dashboard')}
                    >
                        Start one
                    </button>
                </div>
            );
        }

        if (!visible.length) {
            return (
                <div className="ds-state">
                    <p>Nothing matches “{search.trim()}”.</p>
                </div>
            );
        }

        return (
            <ul className="chat-view-list">
                {visible.map((conversation) => (
                    <li key={conversation.conversation_id}>
                        <button
                            type="button"
                            className={`chat-view-card${
                                previewId === conversation.conversation_id
                                    ? ' chat-view-card-previewing'
                                    : ''
                            }`}
                            onClick={() => openConversation(conversation.conversation_id)}
                            onMouseEnter={() => showPreview(conversation.conversation_id)}
                            onMouseLeave={hidePreview}
                            onFocus={() => showPreview(conversation.conversation_id)}
                            onBlur={hidePreview}
                        >
                            <span className="chat-view-card-main">
                                <span className="chat-view-card-title">
                                    {conversation.displayTitle}
                                </span>
                                <span className="chat-view-card-meta">
                                    <span title={absoluteTime(conversation.updated_at)}>
                                        {relativeTime(conversation.updated_at)}
                                    </span>
                                    <span className="chat-view-dot" aria-hidden="true" />
                                    <span>
                                        {conversation.message_count}{' '}
                                        {conversation.message_count === 1
                                            ? 'message'
                                            : 'messages'}
                                    </span>
                                    {sortBy === 'created_at' && (
                                        <>
                                            <span className="chat-view-dot" aria-hidden="true" />
                                            <span>
                                                created {relativeTime(conversation.created_at)}
                                            </span>
                                        </>
                                    )}
                                    {conversation.displaySummary && (
                                        <>
                                            <span className="chat-view-dot" aria-hidden="true" />
                                            <span className="chat-view-card-summary">
                                                {conversation.displaySummary}
                                            </span>
                                        </>
                                    )}
                                </span>
                            </span>
                            <span className="chat-view-card-open" aria-hidden="true">
                                ›
                            </span>
                        </button>
                    </li>
                ))}
            </ul>
        );
    };

    return (
        <div className="dashboard-container chat-view-page">
            <AppSidebar active="chats" />

            <main className="chat-view-main">
                <header className="chat-view-header ds-header-rule">
                    <div className="chat-view-heading">
                        <span className="chat-view-kicker">All Sessions</span>
                        <h1>Your conversations</h1>
                        <p>
                            Every conversation in {projectName}, so you can pick up where you left
                            off instead of hunting for its node on the graph.
                        </p>
                    </div>

                    <div className="ds-inline chat-view-controls">
                        {projects.length > 1 && (
                            <label className="ds-field chat-view-control">
                                <span>Project</span>
                                <select
                                    className="ds-select"
                                    value={projectId || ''}
                                    onChange={(event) => setProjectId(event.target.value)}
                                >
                                    {projects.map((project) => (
                                        <option
                                            key={resolveProjectId(project)}
                                            value={resolveProjectId(project)}
                                        >
                                            {project.name}
                                        </option>
                                    ))}
                                </select>
                            </label>
                        )}

                        <label className="ds-field chat-view-control">
                            <span>Sort by</span>
                            <select
                                className="ds-select"
                                value={sortBy}
                                onChange={(event) => setSortBy(event.target.value)}
                            >
                                {SORTS.map((sort) => (
                                    <option key={sort.id} value={sort.id}>
                                        {sort.label}
                                    </option>
                                ))}
                            </select>
                        </label>

                        <label className="ds-field chat-view-control chat-view-search">
                            <span>Search</span>
                            <input
                                className="ds-input"
                                type="search"
                                value={search}
                                placeholder="Find a conversation"
                                onChange={(event) => setSearch(event.target.value)}
                            />
                        </label>
                    </div>
                </header>

                <section className="chat-view-body">{body()}</section>
            </main>

            {previewed && (
                // Click-through to the conversation, so the preview is a shortcut rather than
                // something to dismiss before acting on it.
                <div
                    className="chat-preview"
                    role="button"
                    tabIndex={-1}
                    aria-label={`Open ${previewed.displayTitle}`}
                    onClick={() => openConversation(previewed.conversation_id)}
                    onMouseEnter={() => clearTimeout(closeTimerRef.current)}
                    onMouseLeave={hidePreview}
                >
                    <div className="chat-preview-header">
                        <span className="chat-preview-title">{previewed.displayTitle}</span>
                        <span className="chat-preview-count">
                            {previewed.message_count}{' '}
                            {previewed.message_count === 1 ? 'message' : 'messages'}
                        </span>
                    </div>

                    <div className="chat-preview-body">{previewBody()}</div>

                    <span className="chat-preview-hint">Click to open this conversation</span>
                </div>
            )}
        </div>
    );
}

export default ChatViewPage;
