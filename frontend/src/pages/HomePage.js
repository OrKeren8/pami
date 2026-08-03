import React, { useState, useEffect, useRef, useMemo, useCallback } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import "./HomePage.css";
import { projectsApi, aiApi, jiraApi } from "../api/axios";
import AppSidebar from "../components/layout/AppSidebar";
import GraphCanvas from "../components/graph/GraphCanvas";
import { deriveGraph } from "../lib/graph/deriveGraph";
import { useToast } from "../components/feedback/ToastProvider";
import useChatScroll from "../hooks/useChatScroll";
import useRevealedText from "../hooks/useRevealedText";
import { draftFromApi, stashDraft } from "../lib/jira/jiraHandoff";

const MODAL_LABELS = {
    createProject: "Create project",
    viewNodeDetails: "Node details",
    slack: "Connect Slack",
    slackActions: "Slack actions",
    slackCreateChannel: "Create Slack channel",
    slackSendMessage: "Send Slack message",
    jira: "Connect Jira",
    jiraActions: "Jira actions",
    shareProject: "Share project",
};

const NodeDetailsModal = ({ selectedNode, nodeTasks, subNodes, nearPeers = [], isModalDataLoading, closeModal, fetchProjects, onNodeColorChange, onOpenConversation }) => {
    const [isDeleting, setIsDeleting] = useState(false);
    const [isSavingColor, setIsSavingColor] = useState(false);
    const toast = useToast();
    if (!selectedNode) return null;

    const nodeColor = selectedNode.color || "#2196f3";
    const nodeColorOptions = [
        { label: "Blue", value: "#2196f3" },
        { label: "Purple", value: "#8b5cf6" },
        { label: "Pink", value: "#f06292" },
        { label: "Green", value: "#22c55e" },
        { label: "Orange", value: "#f59e0b" },
        { label: "Red", value: "#ef4444" },
        { label: "Cyan", value: "#06b6d4" },
        { label: "Slate", value: "#64748b" },
    ];

    const handleColorSelect = async (newColor) => {
        if (!onNodeColorChange || isSavingColor) return;
        setIsSavingColor(true);
        try {
            await onNodeColorChange(selectedNode, newColor);
        } finally {
            setIsSavingColor(false);
        }
    };

    const handleDelete = async () => {
        // The old text promised to "reparent its children". The context tree is a sibling
        // graph with no parents or children: deleting a node removes its conversation and
        // strips the reciprocal links from its peers. Nothing is reparented, and the links
        // are destroyed rather than preserved.
        const linkCount = (selectedNode.sibling_links || []).length;
        const ok = window.confirm(
            `Delete "${selectedNode.name}"?\n\n` +
            `Its conversation and ${linkCount} connection${linkCount === 1 ? "" : "s"} to other ` +
            `nodes will be removed. This cannot be undone.`
        );
        if (!ok) return;
        setIsDeleting(true);
        try {
            const nodeId = selectedNode.id || selectedNode._id || (selectedNode._id && selectedNode._id.$oid) || null;
            if (!nodeId) throw new Error("Selected node has no id");

            let deletePath = null;
            if (selectedNode.nodeKind === "context" || selectedNode.project_id || selectedNode.status === 'context') {
                deletePath = `/context-tree/nodes/${nodeId}`;
            } else {
                deletePath = `/projects/${nodeId}`;
            }

            await projectsApi.delete(deletePath);
            toast.success(`${selectedNode.name} deleted.`);
            closeModal();
            await fetchProjects();
        } catch (err) {
            // The raw payload used to go straight into the alert: users got a dialog full of
            // FastAPI validation JSON, which also leaks server internals.
            console.error('Failed to delete node:', err);
            const status = err && err.response ? err.response.status : null;
            toast.error(
                status === 503
                    ? "The node's conversation could not be removed, so nothing was deleted. Please try again."
                    : "Could not delete this node. Please try again."
            );
        } finally {
            setIsDeleting(false);
        }
    };

    return (
        <div className="node-details-shell" style={{ "--node-color": nodeColor }}>
            <div className="node-details-hero">
                <div className="node-details-hero-main">
                    <div className="node-details-icon" aria-hidden="true">
                        <span></span>
                    </div>

                    <div className="node-details-title-group">
                        <span className="node-details-kicker">Context Node</span>
                        <h2>{selectedNode.name || "Untitled node"}</h2>
                    </div>
                </div>

                <div className="node-details-actions">
                    <button
                        type="button"
                        className="node-details-action node-details-action-secondary"
                        onClick={() => onOpenConversation && onOpenConversation(selectedNode)}
                        title="Open node chat"
                    >
                        Open Chat
                    </button>

                    <button
                        type="button"
                        className="node-details-action node-details-action-danger"
                        onClick={handleDelete}
                        disabled={isDeleting}
                        title="Delete node"
                    >
                        {isDeleting ? "Deleting..." : "Delete"}
                    </button>
                </div>
            </div>

            <div className="node-details-color-row">
                <span className="node-details-color-label">Node color</span>
                <div className="node-details-color-picker" title="Node color">
                    {nodeColorOptions.map((option) => (
                        <button
                            key={option.value}
                            type="button"
                            className={`node-details-color-dot ${nodeColor === option.value ? "selected" : ""}`}
                            disabled={isSavingColor}
                            title={option.label}
                            aria-label={`Set node color to ${option.label}`}
                            onClick={() => handleColorSelect(option.value)}
                            style={{ "--dot-color": option.value }}
                        >
                            <span>{nodeColor === option.value ? "✓" : ""}</span>
                        </button>
                    ))}
                </div>
            </div>

            <div className="node-details-grid">
                <section className="node-details-card node-details-summary-card">
                    <div className="node-details-card-header">
                        <span className="node-details-card-label">Mission objective</span>
                        <span className="node-details-status-pill">{selectedNode.status || "context"}</span>
                    </div>

                    <div className="node-details-description node-details-description-primary">
                        <p>
                            {selectedNode.goal || "No mission objective has been configured for this intelligence layer."}
                        </p>
                    </div>
                </section>

                <section className="node-details-card node-details-metrics-card">
                    <span className="node-details-card-label">Node context</span>

                    <div className="node-details-metrics">
                        <div className="node-details-metric">
                            <strong>{subNodes.length}</strong>
                            <span>Siblings</span>
                        </div>

                        <div className="node-details-metric">
                            <strong>{nodeTasks.length}</strong>
                            <span>Project tasks</span>
                        </div>

                        <div className="node-details-metric">
                            <strong>{selectedNode.status || "context"}</strong>
                            <span>Layer type</span>
                        </div>
                    </div>
                </section>
            </div>

            <div className="node-details-body">
                {isModalDataLoading ? (
                    <div className="node-details-loading">
                        <div className="loading-spinner"></div>
                        <p>Loading connected node resources...</p>
                    </div>
                ) : (
                    <>
                        <section className="node-details-section">
                            <div className="node-details-section-header">
                                <div>
                                    <span className="node-details-section-kicker">Structure</span>
                                    <h3>Connected siblings</h3>
                                </div>
                                <span className="node-details-count">{subNodes.length}</span>
                            </div>

                            {subNodes.length > 0 ? (
                                <div className="node-details-chip-list">
                                    {subNodes.map((sub, idx) => (
                                        <span key={idx} className="node-details-chip">
                                            {sub.header || sub.name || "Related Node"}
                                        </span>
                                    ))}
                                </div>
                            ) : (
                                <p className="node-details-empty">No sibling links are attached to this context node yet.</p>
                            )}

                            {/* Named, not linked. Nothing cleared the similarity floor, and
                                drawing an edge anyway would assert a relationship the
                                numbers do not support. */}
                            {nearPeers.length > 0 && (
                                <div className="node-details-near-peers">
                                    <span className="node-details-near-peers-label">
                                        Closest, but not close enough to link
                                    </span>
                                    <div className="node-details-chip-list">
                                        {nearPeers.map((peer, idx) => (
                                            <span
                                                key={idx}
                                                className="node-details-chip node-details-chip-weak"
                                                title={`Similarity ${peer.similarity.toFixed(2)}`}
                                            >
                                                {peer.header}
                                            </span>
                                        ))}
                                    </div>
                                </div>
                            )}
                        </section>

                        <section className="node-details-section">
                            <div className="node-details-section-header">
                                <div>
                                    <span className="node-details-section-kicker">Execution</span>
                                    {/* Tasks carry a project_id and nothing else, so these are
                                        the project's tasks, identical for every node in it.
                                        Labelling them "attached" implied a per-node link that
                                        does not exist in the data. */}
                                    <h3>Tasks in this project</h3>
                                </div>
                                <span className="node-details-count">{nodeTasks.length}</span>
                            </div>

                            {nodeTasks.length > 0 ? (
                                <div className="node-details-task-list">
                                    {nodeTasks.map((task, idx) => (
                                        <div key={idx} className="node-details-task-item">
                                            <div>
                                                <strong>{task.title || "Task"}</strong>
                                                <span>{task.status || "pending"}</span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            ) : (
                                <p className="node-details-empty">This project has no tasks yet.</p>
                            )}
                        </section>
                    </>
                )}
            </div>

            <button type="button" className="node-details-close-btn" onClick={closeModal}>
                Close
            </button>
        </div>
    );
};

// Each header stat gets an icon that depicts what it counts, replacing decorative CSS shapes
// that carried no meaning.
const STAT_ICONS = {
    conversations: "M2.5 4.2A1.7 1.7 0 0 1 4.2 2.5h9.6a1.7 1.7 0 0 1 1.7 1.7v6a1.7 1.7 0 0 1-1.7 1.7H7l-3.2 2.6a.5.5 0 0 1-.8-.4v-2.2a1.7 1.7 0 0 1-.5-1.2Z",
    connections: "M5.6 10.4 10.4 5.6M4 12.5a2.2 2.2 0 1 0 0-4.4 2.2 2.2 0 0 0 0 4.4ZM12 7.9a2.2 2.2 0 1 0 0-4.4 2.2 2.2 0 0 0 0 4.4Z",
    connected: "M8 1.8a6.2 6.2 0 1 1 0 12.4A6.2 6.2 0 0 1 8 1.8Zm-2.6 6.4 1.9 1.9 3.4-3.6",
    projects: "M2 4.4A1.4 1.4 0 0 1 3.4 3h2.7l1.4 1.7h5.1A1.4 1.4 0 0 1 14 6.1v5.5a1.4 1.4 0 0 1-1.4 1.4H3.4A1.4 1.4 0 0 1 2 11.6Z"
};

const StatIcon = ({ name, className }) => (
    <span className={className} aria-hidden="true">
        <svg viewBox="0 0 16 16" focusable="false">
            <path
                d={STAT_ICONS[name]}
                fill="none"
                stroke="currentColor"
                strokeWidth="1.4"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    </span>
);

const HomePage = () => {
    const [searchParams, setSearchParams] = useSearchParams();
    const navigate = useNavigate();
    const toast = useToast();
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [activePane, setActivePane] = useState("tree");

    const getTreePanelSizes = () => {
        const viewportHeight = typeof window === "undefined" ? 780 : window.innerHeight;

        return {
            collapsedHeight: Math.max(520, viewportHeight - 126),
            expandedHeight: viewportHeight
        };
    };

    const [treeHeight, setTreeHeight] = useState(() => getTreePanelSizes().collapsedHeight);

    // Jira lives in a modal owned by this page, so the sidebar links here with a query
    // parameter when the user is on another route.
    useEffect(() => {
        if (searchParams.get("integration") !== "jira") return;
        openModal("jira");
        setSearchParams({}, { replace: true });
    }, [searchParams, setSearchParams]);

    // The panel is bottom-anchored, so its height decides where its top edge lands. Sized
    // only at mount, it kept a height from the old viewport after any window resize and its
    // top edge crept up underneath the header.
    useEffect(() => {
        const resize = () => setTreeHeight(getTreePanelSizes().collapsedHeight);

        window.addEventListener("resize", resize);
        return () => window.removeEventListener("resize", resize);
    }, []);
    const [isLoading, setIsLoading] = useState(true);
    const [activeModal, setActiveModal] = useState(null);
    const [realProjects, setRealProjects] = useState([]);
    const [contextNodesMap, setContextNodesMap] = useState({});
    const [selectedProjectId, setSelectedProjectId] = useState(null);
    const [isProjectMenuOpen, setIsProjectMenuOpen] = useState(false);

    const [selectedNode, setSelectedNode] = useState(null);
    const [nodeTasks, setNodeTasks] = useState([]);
    const [subNodes, setSubNodes] = useState([]);
    const [nearPeers, setNearPeers] = useState([]);
    const [isModalDataLoading, setIsModalDataLoading] = useState(false);

    const [emailInput, setEmailInput] = useState("");
    const [tokenInput, setTokenInput] = useState("");

    const [isJiraLoading, setIsJiraLoading] = useState(false);
    const [jiraProjects, setJiraProjects] = useState([]);

    const [chatMessages, setChatMessages] = useState([]);
    const [chatInput, setChatInput] = useState("");
    const [conversationId, setConversationId] = useState(null);

    // Indexing is debounced server-side, so the last message or two of a conversation stay
    // unsearchable until the conversation is flushed. Flush whenever the user walks away from
    // it, which is exactly when they are about to ask about it from somewhere else. The
    // server also flushes on idle; this makes it immediate.
    const flushConversationIndex = (id, { onUnload = false } = {}) => {
        if (!id) return;
        const url = `${aiApi.defaults.baseURL}/ai-conversations/context-retrieval/reindex/${id}`;
        if (onUnload) {
            // keepalive survives the page going away; a normal request would be cancelled.
            window.fetch(url, { method: "POST", keepalive: true }).catch(() => {});
            return;
        }
        aiApi.post(`/ai-conversations/context-retrieval/reindex/${id}`).catch(() => {});
    };

    const conversationIdRef = useRef(null);
    useEffect(() => {
        conversationIdRef.current = conversationId;
    }, [conversationId]);

    useEffect(() => {
        const onHidden = () => {
            if (document.visibilityState === "hidden") {
                flushConversationIndex(conversationIdRef.current, { onUnload: true });
            }
        };

        document.addEventListener("visibilitychange", onHidden);
        return () => document.removeEventListener("visibilitychange", onHidden);
    }, []);

    const [isChatLoading, setIsChatLoading] = useState(false);
    // The service answers in one shot, so the reply is typed out here instead: a wall of
    // text appearing at once gives no sense of progress and leaves the reader hunting for
    // where it started.
    const { revealedChars, reveal: revealReply, stop: stopReveal } = useRevealedText();
    // Node just created from a conversation, highlighted on the graph while its connections
    // are revealed.
    const [spotlightNodeId, setSpotlightNodeId] = useState(null);
    const [shareEmail, setShareEmail] = useState("");
    const [members, setMembers] = useState({ members: [], pending_invites: [] });
    const [isSharing, setIsSharing] = useState(false);
    const {
        containerRef: chatBodyRef,
        scrollToBottom: scrollChatToBottom
    } = useChatScroll([chatMessages, revealedChars, isChatLoading]);

    // Disabling the input while a reply was in flight made the browser blur it, so
    // every message needed a fresh click on the box. It stays enabled and keeps focus;
    // only the send button is gated, and handleSendMessage ignores a repeat submit.
    const chatInputRef = useRef(null);

    const projectGraph = useMemo(
        () => deriveGraph(selectedProjectId ? contextNodesMap[selectedProjectId] || [] : []),
        [contextNodesMap, selectedProjectId]
    );

    const resolveProjectId = (proj) => {
        if (!proj) return null;
        if (typeof proj === "string") return proj;
        if (proj.id) return proj.id;
        if (proj._id && proj._id.$oid) return proj._id.$oid;
        if (proj._id) return proj._id;
        return null;
    };

    const fetchProjects = async () => {
        setIsLoading(true);
        try {
            const response = await projectsApi.get("/projects/");
            const projects = response.data || [];
            setRealProjects(projects);

            if (projects.length === 0) {
                setSelectedProjectId(null);
                setContextNodesMap({});
                return;
            }

            const projectIds = projects.map((proj) => String(resolveProjectId(proj))).filter(Boolean);
            const hasCurrent = selectedProjectId && projectIds.includes(String(selectedProjectId));
            const nextSelectedProjectId = hasCurrent ? selectedProjectId : projectIds[0];

            setSelectedProjectId(nextSelectedProjectId);
            if (nextSelectedProjectId) {
                await fetchContextNodes(nextSelectedProjectId);
            }
        } catch (error) {
            console.error("Failed to fetch projects:", error);
        } finally {
            setIsLoading(false);
        }
    };

    const fetchContextNodes = async (projectId) => {
        if (!projectId) return;
        try {
            const resp = await projectsApi.get(`/context-tree/projects/${projectId}/nodes`);
            if (resp && resp.data) {
                setContextNodesMap((m) => {
                    const next = { ...m, [projectId]: resp.data };

                    // If a node is currently selected and belongs to this project,
                    // refresh the selectedNode object with the latest data so the
                    // node preview reflects backend changes without a full reload.
                    try {
                        if (selectedNode) {
                            const selProj = selectedNode.project_id || selectedNode.projectId || selectedNode.project || null;
                            const normalizedSelProj = selProj;
                            if (normalizedSelProj && String(normalizedSelProj) === String(projectId)) {
                                const selId = selectedNode.id || selectedNode._id || (selectedNode._id && selectedNode._id.$oid) || null;
                                if (selId) {
                                    const updated = resp.data.find((n) => String(n.id || n._id || (n._id && n._id.$oid) || n._id) === String(selId));
                                    if (updated) {
                                        // update selectedNode to the fresh object
                                        setSelectedNode({
                                            id: updated.id || updated._id,
                                            name: updated.header || updated.name || 'Context Node',
                                            color: updated.color,
                                            status: updated.node_type || updated.status,
                                            goal: updated.summary || updated.header,
                                            conversation_id: updated.conversation_id || updated.conversationId || null,
                                            sibling_links: updated.sibling_links || [],
                                            project_id: projectId,
                                            nodeKind: 'context',
                                            header: updated.header,
                                            summary: updated.summary,
                                            topics: updated.topics,
                                        });
                                    }
                                }
                            }
                        }
                    } catch (e) {
                        console.warn('Failed to refresh selectedNode after context nodes fetch', e);
                    }

                    return next;
                });
                return resp.data;
            }
        } catch (err) {
            console.error('Failed to fetch context nodes for', projectId, err);
        }
        return null;
    };

    const handleCreateProject = async (e) => {
        e.preventDefault();
        if (!emailInput) {
            toast.error("Please enter a project name.");
            return;
        }
        setIsLoading(true);
        try {
            const response = await projectsApi.post("/projects/", {
                name: emailInput,
                goal: tokenInput || "No goal defined",
                status: "active",
            });
            const newProjectId = resolveProjectId(response.data);
            toast.success(`Project "${emailInput}" created.`);
            await fetchProjects();
            if (newProjectId) {
                await handleProjectSelect(newProjectId);
            }
            closeModal();
        } catch (error) {
            if (error.response) {
                console.error("Server Error Data:", error.response.data);
                toast.error("The server rejected the request. See the console for details.");
            } else {
                console.error("Connection Error:", error.message);
                toast.error("Could not reach the server. Check that the backend is running.");
            }
        } finally {
            setIsLoading(false);
        }
    };

    const handleNodeColorChange = async (node, color) => {
        if (!node || !color || node.id === "root") return;

        const nodeId = node.id || node._id || (node._id && node._id.$oid) || null;
        if (!nodeId) {
            toast.error("Could not update the colour: this node has no id.");
            return;
        }

        const isContextNode = node.nodeKind === "context" || Boolean(node.project_id) || node.status === "context";

        const projectPath = `/projects/${nodeId}`;
        const contextPath = `/context-tree/nodes/${nodeId}`;

        const candidatePaths = isContextNode
            ? [contextPath, `${contextPath}/`, projectPath, `${projectPath}/`]
            : [projectPath, `${projectPath}/`, contextPath, `${contextPath}/`];

        const applyLocalColor = () => {
            const updatedNode = { ...node, color };
            setSelectedNode(updatedNode);

            setRealProjects((previousProjects) => previousProjects.map((project) => {
                const projectId = project.id || project._id || (project._id && project._id.$oid) || String(project._id);
                if (String(projectId) !== String(nodeId)) return project;
                return { ...project, color };
            }));

            setContextNodesMap((previousMap) => {
                const nextMap = {};
                Object.keys(previousMap).forEach((projectId) => {
                    nextMap[projectId] = (previousMap[projectId] || []).map((contextNode) => {
                        const contextNodeId = contextNode.id || contextNode._id || (contextNode._id && contextNode._id.$oid) || String(contextNode._id);
                        if (String(contextNodeId) !== String(nodeId)) return contextNode;
                        return { ...contextNode, color };
                    });
                });
                return nextMap;
            });
        };

        applyLocalColor();

        const errors = [];

        for (const candidatePath of candidatePaths) {
            try {
                await projectsApi.put(candidatePath, { color });

                if (node.project_id) {
                    await fetchContextNodes(node.project_id);
                } else {
                    await fetchProjects();
                }

                return;
            } catch (error) {
                const status = error && error.response ? error.response.status : "NO_RESPONSE";
                const details = error && error.response ? error.response.data : (error && error.message ? error.message : error);
                errors.push({ path: candidatePath, status, details });

                if (!(status === 404 || status === 405 || status === 307 || status === 308)) {
                    break;
                }
            }
        }

        console.error("Failed to persist node color. Tried paths:", errors);
        toast.error("Colour changed on screen but could not be saved. It will reset on reload.");
    };

    useEffect(() => {
        fetchProjects();
    }, []);

    useEffect(() => {
        if (!selectedProjectId) return;
        if (contextNodesMap[selectedProjectId]) return;
        fetchContextNodes(selectedProjectId);
    }, [selectedProjectId, contextNodesMap]);

    // Keep selectedNode in-sync with the freshest data from contextNodesMap.
    // Sometimes the selectedNode object is an earlier snapshot (from the tree),
    // so when nodes are re-fetched we should replace the selectedNode with the
    // authoritative server copy to avoid stale previews.
    useEffect(() => {
        try {
            if (!selectedNode) return;
            // look for a matching node across all projects in the map
            const allNodes = Object.values(contextNodesMap).flat();
            if (!allNodes || allNodes.length === 0) return;
            const selId = selectedNode.id || selectedNode._id || (selectedNode._id && selectedNode._id.$oid) || null;
            if (!selId) return;
            const found = allNodes.find((n) => String(n.id || n._id || (n._id && n._id.$oid) || n._id) === String(selId));
            if (found) {
                // Merge but prefer fresh server values
                setSelectedNode((prev) => ({
                    ...prev,
                    id: found.id || found._id,
                    name: found.header || found.name || prev.name,
                    color: found.color || prev.color,
                    status: found.node_type || found.status || prev.status,
                    goal: found.summary || found.header || prev.goal,
                    conversation_id: found.conversation_id || found.conversationId || prev.conversation_id,
                    project_id: found.project_id || prev.project_id,
                    header: found.header || prev.header,
                    summary: found.summary || prev.summary,
                    topics: found.topics || prev.topics || [],
                }));
            }
        } catch (e) {
            console.warn('Error reconciling selectedNode with contextNodesMap', e);
        }
    }, [contextNodesMap]);

    const createAIConversation = async () => {
        try {
            const fallbackProjectId = realProjects.length > 0 ? resolveProjectId(realProjects[0]) : null;
            const projectId = selectedProjectId || fallbackProjectId || "general";
            const contextNodeId = "chat-session-" + Date.now();
            const response = await aiApi.post(`/ai-conversations/`, {
                context_node_id: contextNodeId,
                project_id: projectId,
                title: "PAMI Chat Session",
            });
            if (response.data && (response.data.conversation_id || response.data.id)) {
                const id = response.data.conversation_id || response.data.id;
                setConversationId(id);
                return id;
            }
        } catch (err) {
            console.error("Failed to create AI conversation:", err);
        }
        return null;
    };

    const handleSendMessage = async () => {
        if (!chatInput || !chatInput.trim() || isChatLoading) return;
        const userMessage = chatInput.trim();
        setChatInput("");
        setChatMessages((p) => [...p, { role: "user", content: userMessage }]);
        // Sending is an explicit action, so follow it down even if the user had scrolled up.
        scrollChatToBottom();
        setIsChatLoading(true);
        try {
            let convId = conversationId;
            if (!convId) {
                convId = await createAIConversation();
                if (!convId) throw new Error("Could not create conversation");
            }

            const resp = await aiApi.post(`/ai-conversations/${convId}/messages`, {
                message: userMessage,
            });

            const aiText = resp.data && (resp.data.response || resp.data.text || resp.data.message);
            setChatMessages((p) => [
                ...p,
                {
                    role: "assistant",
                    content: aiText || "(no response)",
                    // The service reports which other conversations it drew on. Showing them is
                    // the whole promise of the feature: without it the user cannot tell that an
                    // answer came from somewhere else, or check where.
                    consulted: (resp.data && resp.data.consulted) || [],
                    jiraDraft: (resp.data && resp.data.jira_draft) || null
                }
            ]);

            // The model decided to draft a ticket, so hand it to the Jira workspace and go
            // there. Asking for a ticket is asking to be in the ticket editor, and the reply is
            // not lost by leaving: the conversation is saved, and the Jira window carries a
            // link back to it.
            const drafted = resp.data && resp.data.jira_draft;
            if (drafted) {
                stashDraft(draftFromApi(drafted), {
                    conversationId: convId,
                    projectId: selectedProjectId || null
                });
                toast.success("Ticket drafted - opening the Jira workspace.");
                navigate("/jira");
                return;
            }
            revealReply((aiText || "(no response)").length);
        } catch (err) {
            console.error("Failed to send message to AI:", err);
            setChatMessages((p) => [...p, { role: "assistant", content: "I'm having trouble connecting right now. Please try again." }]);
        } finally {
            setIsChatLoading(false);
            // Back to the box, so the next message is just typing.
            chatInputRef.current?.focus();
        }
    };

    const getProjectTreeNodes = () => {
        if (!selectedProjectId) return [];

        const ctxNodes = contextNodesMap[selectedProjectId] || [];
        return ctxNodes.map((n) => ({
            id: n.id || n._id || (n._id && n._id.$oid) || String(n._id),
            name: n.header ? (n.header.length > 40 ? n.header.slice(0, 40) + '…' : n.header) : 'Context Node',
            color: n.color || '#8b5cf6',
            status: n.node_type || 'context',
            goal: n.summary || n.header || 'No snapshot description available.',
            conversation_id: n.conversation_id || n.conversationId || n.conversation || null,
            sibling_links: n.sibling_links || [],
            project_id: selectedProjectId,
            nodeKind: "context"
        }));
    };

    const closeModal = () => {
        setActiveModal(null);
        setSelectedNode(null);
        setNodeTasks([]);
        setSubNodes([]);
        setNearPeers([]);
        setEmailInput("");
        setTokenInput("");
    };

    const openConversationById = async (convId) => {
        if (!convId) return false;
        flushConversationIndex(conversationId);
        stopReveal();

        try {
            // Fetch conversation history from AI service
            const resp = await aiApi.get(`/ai-conversations/${convId}`);
            if (resp && resp.data && resp.data.messages) {
                // Map messages into chat format
                const msgs = resp.data.messages.map((m) => ({ role: m.role, content: m.content }));
                setChatMessages(msgs);
            }
            setConversationId(convId);
            setActivePane('chat');
            // Close modal and focus chat
            closeModal();
            setTimeout(() => {
                const input = document.querySelector('textarea, input[type=text]');
                if (input) input.focus();
            }, 150);
            return true;
        } catch (err) {
            console.error('Failed to load conversation:', err);
            toast.error('Could not load the conversation. Please try again.');
            return false;
        }
    };

    const goToNodeConversation = async (node) => {
        if (!node) return;
        const convId = node.conversation_id || node.conversationId || node.conversation || null;
        if (!convId) {
            toast.notify('This node has no associated conversation.');
            return;
        }
        await openConversationById(convId);
    };

    // Chat View lists conversations on its own route and links back here, because the chat
    // pane and everything it needs - the project, the graph, the node modal - live on this
    // page. The parameter is cleared so a later reload does not reopen it.
    useEffect(() => {
        const requested = searchParams.get("conversation");
        if (!requested) return;
        setSearchParams({}, { replace: true });
        openConversationById(requested);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [searchParams]);

    const modalRef = useRef(null);

    // Without these the dialog was unreachable and inescapable by keyboard: no role, no
    // Escape handler, and focus stayed behind it on the page.
    useEffect(() => {
        if (!activeModal) return undefined;

        const onKeyDown = (event) => {
            if (event.key === "Escape") closeModal();
        };

        window.addEventListener("keydown", onKeyDown);
        modalRef.current?.focus();
        return () => window.removeEventListener("keydown", onKeyDown);
    }, [activeModal]);

    const openModal = (type) => {
        setActiveModal(type);
    };

    const handleProjectSelect = async (projectId) => {
        if (!projectId) return;
        setSelectedProjectId(projectId);
        setIsProjectMenuOpen(false);
        setSelectedNode(null);
        setNodeTasks([]);
        setSubNodes([]);
        if (!contextNodesMap[projectId]) {
            await fetchContextNodes(projectId);
        }
    };

    const openNodeDetails = (graphNode) => {
        const legacyNode = getProjectTreeNodes().find((candidate) => candidate.id === graphNode.id);
        if (legacyNode) handleNodeClick(legacyNode);
    };

    const handleNodeClick = async (node) => {
        setSelectedNode(node);
        setActiveModal("viewNodeDetails");
        setIsModalDataLoading(true);

        try {
            const targetProjectId = node.nodeKind === "context"
                ? (node.project_id || node.projectId || node.project || node.id)
                : node.id;

            const [tasksRes, nodesRes] = await Promise.all([
                projectsApi.get(`/tasks/projects/${targetProjectId}/tasks`).catch(() => ({ data: [] })),
                projectsApi.get(`/context-tree/projects/${targetProjectId}/nodes`).catch(() => ({ data: [] }))
            ]);

            setNodeTasks(tasksRes.data || []);
            const allNodes = nodesRes.data || [];
            if (node.nodeKind === "context") {
                const selectedNodeId = String(node.id || node._id || (node._id && node._id.$oid) || "");
                const selectedServerNode = allNodes.find(
                    (n) => String(n.id || n._id || (n._id && n._id.$oid) || n._id) === selectedNodeId
                );
                const siblingIds = new Set(
                    (selectedServerNode?.sibling_links || node.sibling_links || []).map((link) =>
                        String(link?.sibling_id || "")
                    )
                );
                const siblingNodes = allNodes.filter((n) =>
                    siblingIds.has(String(n.id || n._id || (n._id && n._id.$oid) || n._id))
                );
                setSubNodes(siblingNodes);

                const idOf = (n) => String(n.id || n._id || (n._id && n._id.$oid) || n._id);
                setNearPeers(
                    ((selectedServerNode || node).near_peers || [])
                        .map((peer) => {
                            const match = allNodes.find(
                                (candidate) => idOf(candidate) === String(peer.sibling_id)
                            );
                            return match
                                ? { header: match.header || "Untitled node", similarity: peer.similarity }
                                : null;
                        })
                        .filter(Boolean)
                );
            } else {
                setSubNodes(allNodes);
                setNearPeers([]);
            }
        } catch (error) {
            console.error("Failed to fetch node sub-resources:", error);
        } finally {
            setIsModalDataLoading(false);
        }
    };


    const fetchJiraProjects = async () => {
        const response = await jiraApi.get("/list-projects");
        if (!response.data || response.data.ok !== true) {
            throw new Error("Failed to fetch Jira projects.");
        }
        return response.data.projects || [];
    };

    const handleJiraConnect = async () => {
        setIsJiraLoading(true);
        try {
            const response = await jiraApi.post("/connection-check");
            if (!response.data || response.data.ok !== true) {
                throw new Error("Jira connection check failed.");
            }
            const projects = await fetchJiraProjects();
            setJiraProjects(projects);
            toast.success("Connected successfully to Jira.");
            setActiveModal("jiraActions");
        } catch (error) {
            console.error("Jira connection failed:", error);
            toast.error("Could not connect to Jira. Check the Jira service configuration.");
        } finally {
            setIsJiraLoading(false);
        }
    };

    const handleJiraTestConnection = async () => {
        setIsJiraLoading(true);
        try {
            const response = await jiraApi.post("/connection-check");
            if (!response.data || response.data.ok !== true) {
                throw new Error("Jira connection check failed.");
            }
            toast.success("Jira connection is healthy.");
        } catch (error) {
            console.error("Jira test connection failed:", error);
            toast.error("Jira test connection failed.");
        } finally {
            setIsJiraLoading(false);
        }
    };

    const handleListJiraProjects = async () => {
        setIsJiraLoading(true);
        try {
            const projects = await fetchJiraProjects();
            setJiraProjects(projects);
            toast.notify(
                projects.length > 0
                    ? `Found ${projects.length} Jira project${projects.length === 1 ? "" : "s"}.`
                    : "No Jira projects found."
            );
        } catch (error) {
            console.error("Failed to fetch Jira projects:", error);
            toast.error("Failed to fetch Jira projects.");
        } finally {
            setIsJiraLoading(false);
        }
    };

    const handleCreateJiraTestIssue = async () => {
        setIsJiraLoading(true);
        try {
            const projects = jiraProjects.length > 0 ? jiraProjects : await fetchJiraProjects();
            setJiraProjects(projects);
            const projectKey = projects[0] && projects[0].key;
            if (!projectKey) {
                toast.error("No Jira project is available to create a test issue in.");
                return;
            }

            const response = await jiraApi.post("/issues", {
                project_key: projectKey,
                summary: "PAMI frontend Jira integration test",
                description: "Created from the PAMI frontend through the Jira service.",
                issue_type: "Task",
                labels: ["pami", "frontend", "integration"],
            });

            if (!response.data || response.data.ok !== true) {
                throw new Error("Failed to create Jira issue.");
            }
            toast.success(`Jira issue created: ${response.data.issue_key}`);
        } catch (error) {
            console.error("Failed to create Jira issue:", error);
            toast.error("Failed to create Jira issue.");
        } finally {
            setIsJiraLoading(false);
        }
    };

    // Polls briefly for the node the AI organizer is still filling in. Bounded, and stops as
    // soon as the node has either links or a generated title.
    const refetchNodesUntilLinked = async (projectId, nodeId) => {
        let latest = null;
        for (const delay of [1200, 1800, 2500]) {
            await new Promise((resolve) => setTimeout(resolve, delay));
            const nodes = await fetchContextNodes(projectId);
            const node = (nodes || []).find(
                (candidate) => String(candidate.id || candidate._id) === String(nodeId)
            );
            if (node) latest = node;
            if (node && (node.sibling_links || []).length > 0) return node;
        }
        // Returned even without links so the caller can tell the user why there are none.
        return latest;
    };

    // useCallback so the canvas effect that owns the reveal timers is not torn down and
    // restarted on every render of this page.
    const clearSpotlight = useCallback(() => setSpotlightNodeId(null), []);

    // A node with no links is a legitimate outcome - nothing in the project was close
    // enough - but silently dropping it on the graph as an island looks like a failure. The
    // service reports the nearest peers it considered, so say what they were.
    const announceIfUnlinked = (node, projectId) => {
        if (!node || (node.sibling_links || []).length > 0) return;

        const nearby = node.near_peers || [];
        if (!nearby.length) {
            toast.notify('Added to the graph. Nothing in this project was close enough to link to it yet.');
            return;
        }

        const others = contextNodesMap[projectId] || [];
        const names = nearby
            .map((peer) => {
                const match = others.find(
                    (candidate) => String(candidate.id || candidate._id) === String(peer.sibling_id)
                );
                return match?.header;
            })
            .filter(Boolean)
            .slice(0, 3);

        toast.notify(
            names.length
                ? `Added to the graph, but nothing was close enough to link. Nearest: ${names.join(', ')}.`
                : 'Added to the graph. Nothing in this project was close enough to link to it yet.',
            { duration: 9000 }
        );
    };

    const openShareProject = async () => {
        if (!selectedProjectId) return;
        setShareEmail("");
        setMembers({ members: [], pending_invites: [] });
        openModal("shareProject");
        try {
            const response = await projectsApi.get(`/projects/${selectedProjectId}/members`);
            setMembers(response.data || { members: [], pending_invites: [] });
        } catch (err) {
            console.error("Failed to load project members:", err);
            toast.error("Could not load who this project is shared with.");
        }
    };

    const handleShareProject = async (event) => {
        event.preventDefault();
        const email = shareEmail.trim().toLowerCase();
        if (!email) {
            toast.error("Enter the email address to share with.");
            return;
        }

        setIsSharing(true);
        try {
            const response = await projectsApi.post(
                `/projects/${selectedProjectId}/members`,
                { email }
            );
            const status = response.data?.status;
            // "invited" is not a failure: the address has no account yet, and the invite is
            // claimed the first time they sign in. Saying so is the difference between the
            // user thinking it worked and the user thinking nothing happened.
            if (status === "added") {
                toast.success(`${email} can now see this project.`);
            } else if (status === "invited") {
                toast.notify(
                    `${email} has no PAMI account yet. They will get this project the first time they sign in.`,
                    { duration: 9000 }
                );
            } else if (status === "already_member") {
                toast.notify(`${email} already has access.`);
            } else {
                toast.notify(`${email} has already been invited.`);
            }

            setShareEmail("");
            const refreshed = await projectsApi.get(`/projects/${selectedProjectId}/members`);
            setMembers(refreshed.data || { members: [], pending_invites: [] });
        } catch (err) {
            console.error("Failed to share the project:", err);
            const status = err?.response?.status;
            toast.error(
                status === 403
                    ? "Only the project owner can share it."
                    : "Could not share this project. Please try again."
            );
        } finally {
            setIsSharing(false);
        }
    };

    const handleRemoveMember = async (memberId, label) => {
        try {
            await projectsApi.delete(`/projects/${selectedProjectId}/members/${memberId}`);
            toast.success(`${label} no longer has access.`);
            const refreshed = await projectsApi.get(`/projects/${selectedProjectId}/members`);
            setMembers(refreshed.data || { members: [], pending_invites: [] });
        } catch (err) {
            console.error("Failed to remove the member:", err);
            toast.error("Could not remove that person. Please try again.");
        }
    };

    const handleCreateNodeFromConversation = async () => {
        try {
            if (realProjects.length === 0) {
                toast.error('No project is available to attach this node to.');
                return;
            }
            const projectRaw = realProjects.find((proj) => String(resolveProjectId(proj)) === String(selectedProjectId)) || realProjects[0];
            const projectId = resolveProjectId(projectRaw);
            if (!projectId) {
                toast.error('Could not determine which project this node belongs to.');
                return;
            }

            const latestUserMessage = [...chatMessages]
                .reverse()
                .find((m) => (m.role || "").toLowerCase() === "user")?.content;
            const body = {
                sibling_links: [],
                header: (latestUserMessage || "Conversation Snapshot").slice(0, 80),
                summary: (chatMessages.length > 0 ? chatMessages[chatMessages.length - 1].content : '').slice(0, 300),
                conversation_id: conversationId,
                messages: chatMessages,
                topics: [],
                node_type: 'conversation',
            };

            const resp = await projectsApi.post(`/context-tree/projects/${projectId}/nodes`, body);
            if (resp && resp.data && resp.data.id) {
                // Straight to the graph, before the refetch: the point of creating a node is
                // to see where it lands, and waiting for the links would leave the user on
                // the chat pane for the several seconds the background task takes.
                flushConversationIndex(conversationId);
                setSpotlightNodeId(String(resp.data.id));
                setActivePane("tree");
                await fetchProjects();
                // The title and the sibling links are produced by a background task that
                // finishes a second or two after this responds, so a single refetch here
                // stores a stub with no links - which is also what pushes it off-screen.
                const settled = await refetchNodesUntilLinked(projectId, resp.data.id);
                announceIfUnlinked(settled, projectId);
            } else if (resp && resp.status && resp.status >= 200 && resp.status < 300) {
                await fetchProjects();
            } else {
                toast.error('The server did not confirm the new node. Please try again.');
            }
        } catch (err) {
            console.error('Failed to create node from conversation', err);
            if (err && err.response) console.error('Response data:', err.response.data);
            toast.error('Could not create a node from this conversation. Please try again.');
        }
    };


    const renderDefaultIntegrationModal = () => {
        return (
            <>
                <div className="modal-header" style={{ textAlign: "center", marginBottom: "20px" }}>
                    <img src="https://cdn.worldvectorlogo.com/logos/jira-1.svg" alt="Jira" style={{ height: "50px", marginBottom: "10px" }} />
                    <h2>Connect to Jira</h2>
                    <p className="modal-subtitle">
                        Jira credentials are configured on the Jira service. Connect to verify it can
                        reach your Jira workspace.
                    </p>
                </div>
                <button
                    type="button"
                    className="login-submit-btn"
                    onClick={handleJiraConnect}
                    disabled={isJiraLoading}
                    style={{ width: "100%", padding: "12px", background: "#0052cc", color: "white", border: "none", borderRadius: "12px", fontWeight: "bold" }}
                >
                    {isJiraLoading ? "Connecting..." : "Connect Jira"}
                </button>
            </>
        );
    };

    const renderJiraActionsModal = () => {
        return (
            <>
                <div className="modal-header" style={{ textAlign: "center", marginBottom: "20px" }}>
                    <img src="https://cdn.worldvectorlogo.com/logos/jira-1.svg" alt="Jira" style={{ height: "50px", marginBottom: "10px" }} />
                    <h2>Jira Actions</h2>
                    <p className="modal-subtitle">
                        Test the connection, list projects, or create a test issue.
                    </p>
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                    <button
                        type="button"
                        onClick={handleJiraTestConnection}
                        disabled={isJiraLoading}
                        style={{ width: "100%", padding: "12px", background: "#0052cc", color: "white", border: "none", borderRadius: "12px", fontWeight: "bold" }}
                    >
                        Test Jira Connection
                    </button>

                    <button
                        type="button"
                        onClick={handleListJiraProjects}
                        disabled={isJiraLoading}
                        style={{ width: "100%", padding: "12px", background: "#172b4d", color: "white", border: "none", borderRadius: "12px", fontWeight: "bold" }}
                    >
                        List Jira Projects
                    </button>

                    <button
                        type="button"
                        onClick={handleCreateJiraTestIssue}
                        disabled={isJiraLoading}
                        style={{ width: "100%", padding: "12px", background: "#0f9d58", color: "white", border: "none", borderRadius: "12px", fontWeight: "bold" }}
                    >
                        Create Test Issue
                    </button>

                    {jiraProjects.length > 0 && (
                        <div style={{ marginTop: "8px", padding: "12px", background: "#f5f7fb", borderRadius: "12px", border: "1px solid #e5e7eb" }}>
                            <strong>Projects:</strong>
                            <ul style={{ margin: "8px 0 0 18px", padding: 0 }}>
                                {jiraProjects.map((project) => (
                                    <li key={project.id || project.key}>
                                        {project.name} ({project.key})
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                </div>
            </>
        );
    };

    const renderModalContent = () => {
        if (activeModal === "shareProject") {
            const owner = (members.members || []).find((m) => m.role === "owner");
            const others = (members.members || []).filter((m) => m.role !== "owner");

            return (
                <>
                    <div className="modal-icon" aria-hidden="true">🤝</div>
                    <h2>Share this project</h2>
                    <p className="modal-subtitle">
                        Add someone by email and this project appears in their list too. If they
                        have no account yet, they will get it when they first sign in.
                    </p>

                    <form onSubmit={handleShareProject} className="modal-form">
                        <div className="input-group" style={{ marginBottom: "15px" }}>
                            <label htmlFor="share-email" style={{ display: "block", marginBottom: "5px" }}>
                                Their email
                            </label>
                            <input
                                id="share-email"
                                type="email"
                                placeholder="teammate@example.com"
                                value={shareEmail}
                                onChange={(e) => setShareEmail(e.target.value)}
                                required
                                style={{ width: "100%", padding: "10px", borderRadius: "8px", border: "1px solid #ddd" }}
                            />
                        </div>
                        <button
                            type="submit"
                            className="login-submit-btn"
                            disabled={isSharing}
                            style={{ width: "100%", padding: "12px", background: "#f06292", color: "white", border: "none", borderRadius: "12px", fontWeight: "bold" }}
                        >
                            {isSharing ? "Sharing..." : "Share project"}
                        </button>
                    </form>

                    <div className="share-members">
                        <span className="share-members-label">Who has access</span>
                        <ul>
                            {owner && (
                                <li>
                                    <span>{owner.email || owner.user_id}</span>
                                    <span className="share-role">Owner</span>
                                </li>
                            )}
                            {others.map((member) => (
                                <li key={member.user_id}>
                                    <span>{member.email || member.user_id}</span>
                                    <button
                                        type="button"
                                        className="share-remove"
                                        onClick={() => handleRemoveMember(member.user_id, member.email || "They")}
                                    >
                                        Remove
                                    </button>
                                </li>
                            ))}
                            {(members.pending_invites || []).map((invite) => (
                                <li key={invite.email}>
                                    <span>{invite.email}</span>
                                    <span className="share-role">Invited</span>
                                </li>
                            ))}
                            {!owner && !others.length && !(members.pending_invites || []).length && (
                                <li className="share-empty">Only you, so far.</li>
                            )}
                        </ul>
                    </div>
                </>
            );
        }

        if (activeModal === "createProject") {
            return (
                <>
                    <div className="modal-header" style={{ textAlign: "center", marginBottom: "20px" }}>
                        <span style={{ fontSize: "40px" }}>📁</span>
                        <h2>Create New Project</h2>
                    </div>
                    <form className="modal-form" onSubmit={handleCreateProject}>
                        <div className="input-group" style={{ marginBottom: "15px" }}>
                            <label style={{ display: "block", marginBottom: "5px" }}>Project Name</label>
                            <input type="text" placeholder="e.g. Neural Alpha" required value={emailInput} onChange={(e) => setEmailInput(e.target.value)} style={{ width: "100%", padding: "10px", borderRadius: "8px", border: "1px solid #ddd" }} />
                        </div>
                        <div className="input-group" style={{ marginBottom: "20px" }}>
                            <label style={{ display: "block", marginBottom: "5px" }}>Description (Optional)</label>
                            <input type="text" placeholder="Project goals..." value={tokenInput} onChange={(e) => setTokenInput(e.target.value)} style={{ width: "100%", padding: "10px", borderRadius: "8px", border: "1px solid #ddd" }} />
                        </div>
                        <button type="submit" className="login-submit-btn" disabled={isLoading} style={{ width: "100%", padding: "12px", background: "#f06292", color: "white", border: "none", borderRadius: "12px", fontWeight: "bold" }}>
                            {isLoading ? "Processing..." : "Create Project"}
                        </button>
                    </form>
                </>
            );
        }
        if (activeModal === "jiraActions") return renderJiraActionsModal();
        if (activeModal === "viewNodeDetails") return (
            <NodeDetailsModal
                selectedNode={selectedNode}
                nodeTasks={nodeTasks}
                nearPeers={nearPeers}
                subNodes={subNodes}
                isModalDataLoading={isModalDataLoading}
                closeModal={closeModal}
                fetchProjects={fetchProjects}
                onNodeColorChange={handleNodeColorChange}
                onOpenConversation={goToNodeConversation}
            />
        );
        return renderDefaultIntegrationModal();
    };

    const selectedProject = realProjects.find(
        (project) => String(resolveProjectId(project)) === String(selectedProjectId)
    ) || null;
    const selectedProjectName = selectedProject ? (selectedProject.name || "Untitled Project") : "Select Project";
    const selectedProjectNodeCount = selectedProjectId ? (contextNodesMap[selectedProjectId] || []).length : 0;
    const selectedProjectConnectionCount = projectGraph.links.length;

    // Share of conversations that reached at least one sibling. This is the metric the
    // product actually lives or dies on, and it replaces two hardcoded numbers that were
    // presented as live telemetry.
    const selectedProjectLinkedShare = projectGraph.nodes.length
        ? `${Math.round(
              (projectGraph.nodes.filter((node) => node.degree > 0).length /
                  projectGraph.nodes.length) *
                  100
          )}%`
        : "—";

    // Lives in the graph's floating control bar in tree mode and in the chat header in chat
    // mode, so the panel needs no header row of its own.
    const paneToggle = (
        <div className="pane-toggle" role="tablist" aria-label="Panel">
            <button
                type="button"
                role="tab"
                aria-selected={activePane === "tree"}
                className={`pane-toggle-btn ${activePane === "tree" ? "active" : ""}`}
                onClick={async () => {
                    if (activePane === "tree") return;
                    flushConversationIndex(conversationId);
                    setActivePane("tree");
                    try {
                        await fetchProjects();
                    } catch (e) {
                        console.error("Failed to refresh projects on tab switch", e);
                    }
                }}
            >
                Graph
            </button>
            <button
                type="button"
                role="tab"
                aria-selected={activePane === "chat"}
                className={`pane-toggle-btn ${activePane === "chat" ? "active" : ""}`}
                onClick={() => {
                    // Switching to Chat starts a fresh conversation; clicking it while
                    // already there does nothing, so a live chat is never wiped by a
                    // stray click. Past conversations are reopened from their graph node.
                    if (activePane === "chat") return;
                    flushConversationIndex(conversationId);
                    stopReveal();
                    setConversationId(null);
                    setChatMessages([]);
                    setActivePane("chat");
                }}
            >
                Chat
            </button>
        </div>
    );

    return (
        <div className={`dashboard-container ${isSidebarOpen ? "sidebar-open" : "sidebar-closed"}`}>
            <AppSidebar active="dashboard" />

            <main className={`main-content ${isSidebarOpen ? "sidebar-open" : "sidebar-closed"}`}>
                <header className="top-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", boxSizing: "border-box", flexShrink: 0 }}>
                    <div className="header-left" style={{ display: "flex", alignItems: "center", flex: "0 0 auto" }}>
                        <button className="menu-toggle" onClick={() => setIsSidebarOpen(!isSidebarOpen)}>☰</button>
                    </div>

                    <div className="header-stats-wrapper" style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "22px",
                        background: "transparent",
                        padding: "0",
                        borderRadius: "0",
                        border: "none",
                        margin: "0 20px",
                        flex: "1 1 auto",
                        minWidth: 0,
                        justifyContent: "center",
                        overflowX: "visible"
                    }}>
                        <div className="header-stat-item" style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "14px", whiteSpace: "nowrap", flexShrink: 0 }}>
                            <StatIcon name="conversations" className="header-stat-icon header-stat-icon-nodes" /><strong className="header-stat-value">{selectedProjectNodeCount}</strong><span className="header-stat-label">CONVERSATIONS</span>
                        </div>
                        <div className="header-stat-separator" style={{ width: "1px", height: "18px", background: "rgba(143, 109, 242, 0.16)", flexShrink: 0 }} />
                        <div className="header-stat-item" style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "14px", whiteSpace: "nowrap", flexShrink: 0 }}>
                            <StatIcon name="connections" className="header-stat-icon header-stat-icon-workers" /><strong className="header-stat-value">{selectedProjectConnectionCount}</strong><span className="header-stat-label">CONNECTIONS</span>
                        </div>
                        <div className="header-stat-separator" style={{ width: "1px", height: "18px", background: "rgba(143, 109, 242, 0.16)", flexShrink: 0 }} />
                        <div className="header-stat-item" style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "14px", whiteSpace: "nowrap", flexShrink: 0 }}>
                            <StatIcon name="connected" className="header-stat-icon header-stat-icon-velocity" /><strong className="header-stat-value">{selectedProjectLinkedShare}</strong><span className="header-stat-label">CONNECTED</span>
                        </div>
                        <div className="header-stat-separator" style={{ width: "1px", height: "18px", background: "rgba(143, 109, 242, 0.16)", flexShrink: 0 }} />
                        <div className="header-stat-item" style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "14px", whiteSpace: "nowrap", flexShrink: 0 }}>
                            <StatIcon name="projects" className="header-stat-icon header-stat-icon-uptime" /><strong className="header-stat-value">{realProjects.length}</strong><span className="header-stat-label">PROJECTS</span>
                        </div>
                    </div>

                    <div className="header-right" style={{ display: "flex", alignItems: "center", gap: "15px", flex: "0 0 auto" }}>
                        <button className="new-node-btn" onClick={() => openModal("createProject")}>+ New Project</button>
                        <button
                            type="button"
                            className="share-project-btn"
                            onClick={openShareProject}
                            disabled={!selectedProjectId}
                            title="Share this project with someone by email"
                        >
                            Share
                        </button>
                        <div className="project-switcher">
                            <button
                                type="button"
                                className="project-switcher-btn"
                                onClick={() => setIsProjectMenuOpen((open) => !open)}
                                disabled={realProjects.length === 0}
                            >
                                {selectedProjectName}
                                <span className="project-switcher-caret">▾</span>
                            </button>

                            {isProjectMenuOpen && realProjects.length > 0 && (
                                <div className="project-switcher-menu">
                                    {realProjects.map((project) => {
                                        const projectId = resolveProjectId(project);
                                        const isActive = String(projectId) === String(selectedProjectId);

                                        return (
                                            <button
                                                key={projectId}
                                                type="button"
                                                className={`project-switcher-item ${isActive ? "active" : ""}`}
                                                onClick={() => handleProjectSelect(projectId)}
                                            >
                                                {project.name || "Untitled Project"}
                                            </button>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    </div>
                </header>

                <div className="dashboard-grid dashboard-grid-anchored" style={{
                    height: `${treeHeight}px`,
                    "--tree-panel-height": `${treeHeight}px`
                }}>
                    <div className="project-tree-container">
                        <div
                            className="project-tree-canvas tree-resizable-canvas"
                            style={{ flex: 1, minHeight: 0 }}
                        >
                            {activePane === "tree" ? (
                                realProjects.length > 0 || isLoading ? (
                                    <GraphCanvas
                                        contextNodes={selectedProjectId ? contextNodesMap[selectedProjectId] || [] : []}
                                        projectId={selectedProjectId}
                                        isLoading={isLoading && realProjects.length === 0}
                                        error={null}
                                        onRetry={fetchProjects}
                                        onOpenNode={openNodeDetails}
                                        spotlightId={spotlightNodeId}
                                        onSpotlightDone={clearSpotlight}
                                        toggle={paneToggle}
                                    />
                                ) : (
                                    <div className="empty-tree-state">
                                        <p>No active nodes found on server.</p>
                                        <button className="create-first-btn" onClick={() => openModal("createProject")}>+ Create First Project</button>
                                    </div>
                                )
                            ) : (
                                <div className="pami-chat-pane" style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0, overflow: "hidden" }}>
                                    <div className="chat-header chat-header-row">
                                        <div className="chat-header-title">
                                            {paneToggle}
                                            <span>{selectedProjectName}</span>
                                        </div>
                                        <div className="chat-header-actions">
                                            <button type="button" className="create-node-btn" title="Turn this conversation into a node on the graph" onClick={handleCreateNodeFromConversation} disabled={realProjects.length === 0 || chatMessages.length === 0}>
                                                <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
                                                    <path d="M8 3.4v9.2M3.4 8h9.2" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                                                </svg>
                                                Create Node
                                            </button>
                                        </div>
                                    </div>
                                    <div ref={chatBodyRef} className="chat-body" style={{ padding: "16px", overflowY: "auto", overflowX: "hidden", flex: 1, minHeight: 0 }}>
                                        {chatMessages.length === 0 ? (
                                            <div className="chat-empty-state">
                                                <p>Ask PAMI about this project</p>
                                                <span>
                                                    It can pull in what you discussed in your other
                                                    conversations, and will tell you which ones it used.
                                                </span>
                                            </div>
                                        ) : (
                                            chatMessages.map((msg, idx) => {
                                                const isUser = (msg.role === "user");
                                                const roleClass = isUser ? "user" : "assistant";
                                                const isRevealing = !isUser
                                                    && revealedChars !== null
                                                    && idx === chatMessages.length - 1;
                                                const shownText = isRevealing
                                                    ? msg.content.slice(0, revealedChars)
                                                    : msg.content;
                                                return (
                                                    <div key={idx} className={`chat-message ${roleClass}`}>
                                                        {isUser ? (
                                                            <div className="message-avatar user-avatar"><img src="/mario.png" alt="user" /></div>
                                                        ) : (
                                                            <div className="message-avatar assistant" style={{ backgroundImage: 'url("/pami_ai_avatar.png")' }} />
                                                        )}
                                                        <div className="message-content">
                                                            <p>
                                                                {shownText}
                                                                {isRevealing && <span className="reveal-caret" aria-hidden="true" />}
                                                            </p>
                                                            {!isUser && !isRevealing && msg.jiraDraft && (
                                                                <a
                                                                    className="jira-draft-chip"
                                                                    href="/jira"
                                                                    title={msg.jiraDraft.summary}
                                                                >
                                                                    Open the drafted ticket in Jira &rarr;
                                                                </a>
                                                            )}
                                                            {/* Held back until the text is fully out: chips appearing beside half a
                                                                sentence read as part of the answer. */}
                                                            {!isUser && !isRevealing && (msg.consulted || []).length > 0 && (
                                                                <div className="message-sources">
                                                                    <span className="message-sources-label">
                                                                        Answered using
                                                                    </span>
                                                                    {msg.consulted.map((source) => (
                                                                        <button
                                                                            key={source.conversation_id}
                                                                            type="button"
                                                                            className={`message-source${source.read ? " message-source-read" : ""}`}
                                                                            title={
                                                                                source.read
                                                                                    ? `Read in full: "${source.header || "this conversation"}"`
                                                                                    : `Matched a passage in "${source.header || "this conversation"}"`
                                                                            }
                                                                            onClick={() =>
                                                                                goToNodeConversation({
                                                                                    conversation_id: source.conversation_id
                                                                                })
                                                                            }
                                                                        >
                                                                            {source.header || "Untitled conversation"}
                                                                        </button>
                                                                    ))}
                                                                </div>
                                                            )}
                                                        </div>
                                                    </div>
                                                );
                                            })
                                        )}
                                        {isChatLoading && (
                                            <div className="chat-message assistant">
                                                <div className="message-avatar assistant" style={{ backgroundImage: 'url("/pami_ai_avatar.png")' }} />
                                                <div className="message-content">
                                                    <div className="typing-indicator"><span></span><span></span><span></span></div>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                    <div className="chat-input chat-input-row">
                                        <input
                                            type="text"
                                            className="chat-text-input"
                                            placeholder="Ask PAMI anything..."
                                            value={chatInput}
                                            onChange={(e) => setChatInput(e.target.value)}
                                            onKeyDown={(e) => e.key === "Enter" && handleSendMessage()}
                                            ref={chatInputRef}
                                        />
                                        <button
                                            type="button"
                                            className="chat-send-btn"
                                            onClick={handleSendMessage}
                                            disabled={isChatLoading || !chatInput.trim()}
                                        >
                                            {isChatLoading ? "Sending" : "Send"}
                                        </button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </main>


            {activeModal && (
                <div className="modal-overlay" onClick={closeModal} style={{ position: "fixed", top: 0, left: 0, width: "100%", height: "100%", background: "rgba(0,0,0,0.5)", display: "flex", justifyContent: "center", alignItems: "center", zIndex: 10000 }}>
                    <div
                        className="modal-content"
                        role="dialog"
                        aria-modal="true"
                        aria-label={MODAL_LABELS[activeModal] || "Dialog"}
                        ref={modalRef}
                        tabIndex={-1}
                        onClick={(e) => e.stopPropagation()}
                        style={{ background: "white", padding: "40px", borderRadius: "30px", width: "min(450px, calc(100vw - 32px))", maxHeight: "calc(100vh - 32px)", overflowY: "auto", boxSizing: "border-box", position: "relative" }}
                    >
                        <button
                            className="close-modal-btn"
                            onClick={closeModal}
                            aria-label="Close dialog"
                            style={{ position: "absolute", top: "20px", right: "20px", border: "none", background: "none", fontSize: "24px", cursor: "pointer" }}
                        >
                            &times;
                        </button>
                        {renderModalContent()}
                    </div>
                </div>
            )}
        </div>
    );
};

export default HomePage;