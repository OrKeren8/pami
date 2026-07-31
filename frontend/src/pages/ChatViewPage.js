import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { aiApi, projectsApi } from '../api/axios';
import AppSidebar from '../components/layout/AppSidebar';
import { useToast } from '../components/feedback/ToastProvider';
import './HomePage.css';
import './ChatViewPage.css';

const SORTS = [
    { id: 'updated_at', label: 'Last used' },
    { id: 'created_at', label: 'Created' }
];

const STORED_PROJECT_KEY = 'pami.chatView.projectId';

const resolveProjectId = (project) =>
    project?.id || project?._id?.$oid || (project?._id ? String(project._id) : null);

/** "2 hours ago" reads faster than a timestamp when scanning for the one you just left. */
const relativeTime = (iso) => {
    if (!iso) return 'unknown';
    const then = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`);
    if (Number.isNaN(then.getTime())) return 'unknown';

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

const absoluteTime = (iso) => {
    if (!iso) return '';
    const date = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`);
    return Number.isNaN(date.getTime()) ? '' : date.toLocaleString();
};

function ChatViewPage() {
    const navigate = useNavigate();
    const toast = useToast();

    const [projects, setProjects] = useState([]);
    const [projectId, setProjectId] = useState(null);
    const [conversations, setConversations] = useState([]);
    const [sortBy, setSortBy] = useState(SORTS[0].id);
    const [search, setSearch] = useState('');
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState(null);

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
            const response = await aiApi.get(`/ai-conversations/project/${projectId}`);
            setConversations(response.data || []);
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

    const visible = useMemo(() => {
        const needle = search.trim().toLowerCase();
        const matches = needle
            ? conversations.filter((conversation) =>
                  `${conversation.title || ''} ${conversation.preview || ''}`
                      .toLowerCase()
                      .includes(needle)
              )
            : conversations;

        // Copied before sorting: the fetched array is state, and sorting in place would
        // mutate it without React knowing.
        return [...matches].sort((left, right) =>
            String(right[sortBy] || '').localeCompare(String(left[sortBy] || ''))
        );
    }, [conversations, search, sortBy]);

    const openConversation = (conversation) => {
        navigate(`/dashboard?conversation=${encodeURIComponent(conversation.conversation_id)}`);
    };

    const projectName = useMemo(() => {
        const match = projects.find((project) => resolveProjectId(project) === projectId);
        return match?.name || 'project';
    }, [projects, projectId]);

    const body = () => {
        if (isLoading) {
            return (
                <div className="chat-view-state">
                    <span className="chat-view-spinner" aria-hidden="true" />
                    <p>Loading conversations…</p>
                </div>
            );
        }

        if (error) {
            return (
                <div className="chat-view-state">
                    <p>{error}</p>
                    <button type="button" className="chat-view-retry" onClick={loadConversations}>
                        Try again
                    </button>
                </div>
            );
        }

        if (!conversations.length) {
            return (
                <div className="chat-view-state">
                    <p>No conversations in {projectName} yet.</p>
                    <button
                        type="button"
                        className="chat-view-retry"
                        onClick={() => navigate('/dashboard')}
                    >
                        Start one
                    </button>
                </div>
            );
        }

        if (!visible.length) {
            return (
                <div className="chat-view-state">
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
                            className="chat-view-card"
                            onClick={() => openConversation(conversation)}
                        >
                            <span className="chat-view-card-main">
                                <span className="chat-view-card-title">
                                    {conversation.preview || conversation.title || 'Untitled conversation'}
                                </span>
                                <span className="chat-view-card-meta">
                                    <span title={absoluteTime(conversation.updated_at)}>
                                        {relativeTime(conversation.updated_at)}
                                    </span>
                                    <span className="chat-view-dot" aria-hidden="true" />
                                    <span>
                                        {conversation.message_count}{' '}
                                        {conversation.message_count === 1 ? 'message' : 'messages'}
                                    </span>
                                    {sortBy === 'created_at' && (
                                        <>
                                            <span className="chat-view-dot" aria-hidden="true" />
                                            <span>created {relativeTime(conversation.created_at)}</span>
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
            <AppSidebar
                active="chats"
                onJira={() => {
                    toast.notify('Open the dashboard to connect Jira.');
                    navigate('/dashboard?integration=jira');
                }}
            />

            <main className="chat-view-main">
                <header className="chat-view-header">
                    <div className="chat-view-heading">
                        <span className="chat-view-kicker">Chat View</span>
                        <h1>Your conversations</h1>
                        <p>
                            Every conversation in {projectName}, so you can pick up where you left
                            off instead of hunting for its node on the graph.
                        </p>
                    </div>

                    <div className="chat-view-controls">
                        {projects.length > 1 && (
                            <label className="chat-view-control">
                                <span>Project</span>
                                <select
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

                        <label className="chat-view-control">
                            <span>Sort by</span>
                            <select
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

                        <label className="chat-view-control chat-view-search">
                            <span>Search</span>
                            <input
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
        </div>
    );
}

export default ChatViewPage;
