import React, { useState, useEffect, useRef, useMemo, useCallback } from "react";
import "./HomePage.css";
import pamiLogo from "../assets/pami-logo.png";
import api, { projectsApi, slackApi, aiApi } from "../api/axios";

const NodeDetailsModal = ({ selectedNode, nodeTasks, subNodes, isModalDataLoading, closeModal, fetchProjects, drawConnections, onNodeColorChange, onOpenConversation }) => {
    const [isDeleting, setIsDeleting] = useState(false);
    const [isSavingColor, setIsSavingColor] = useState(false);
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
        const ok = window.confirm(`Delete node "${selectedNode.name}"? This will reparent its children.`);
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
            alert(`${selectedNode.name} deleted.`);
            closeModal();
            await fetchProjects();
            setTimeout(() => {
                try { drawConnections(); } catch (e) { console.error('drawConnections error', e); }
            }, 150);
        } catch (err) {
            if (err && err.response) {
                console.error('Delete failed, status=', err.response.status, err.response.data);
                alert(`Delete failed: ${err.response.status} ${JSON.stringify(err.response.data)}`);
            } else {
                console.error('Failed to delete node:', err);
                alert(`Failed to delete node: ${err && err.message ? err.message : err}`);
            }
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
                            <span>Tasks</span>
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
                        </section>

                        <section className="node-details-section">
                            <div className="node-details-section-header">
                                <div>
                                    <span className="node-details-section-kicker">Execution</span>
                                    <h3>Attached tasks</h3>
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
                                <p className="node-details-empty">No direct active operational tasks are configured for this node.</p>
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

const HomePage = () => {
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [activePane, setActivePane] = useState("tree");
    const [treeZoom, setTreeZoom] = useState(1);
    const [connectionForce, setConnectionForce] = useState(58);
    const [repulsionForce, setRepulsionForce] = useState(34);
    const [forceSimulationNonce, setForceSimulationNonce] = useState(0);

    const getTreePanelSizes = () => {
        const viewportHeight = typeof window === "undefined" ? 780 : window.innerHeight;

        return {
            collapsedHeight: Math.max(520, viewportHeight - 172),
            expandedHeight: viewportHeight
        };
    };

    const [treeHeight, setTreeHeight] = useState(() => getTreePanelSizes().collapsedHeight);
    const [treePan, setTreePan] = useState({ x: 0, y: 0 });
    const [isTreePanning, setIsTreePanning] = useState(false);
    const [isBoardDragArmed, setIsBoardDragArmed] = useState(false);
    const [isLoading, setIsLoading] = useState(true);
    const [activeModal, setActiveModal] = useState(null);
    const [realProjects, setRealProjects] = useState([]);
    const [contextNodesMap, setContextNodesMap] = useState({});

    const [selectedNode, setSelectedNode] = useState(null);
    const [nodeTasks, setNodeTasks] = useState([]);
    const [subNodes, setSubNodes] = useState([]);
    const [isModalDataLoading, setIsModalDataLoading] = useState(false);

    const [emailInput, setEmailInput] = useState("");
    const [tokenInput, setTokenInput] = useState("");

    const [slackConnected, setSlackConnected] = useState(false);
    const [slackChannels, setSlackChannels] = useState([]);
    const [channelNameInput, setChannelNameInput] = useState("");
    const [messageChannelInput, setMessageChannelInput] = useState("");
    const [messageTextInput, setMessageTextInput] = useState("");

    const [chatMessages, setChatMessages] = useState([]);
    const [chatInput, setChatInput] = useState("");
    const [conversationId, setConversationId] = useState(null);
    const [isChatLoading, setIsChatLoading] = useState(false);
    const [assistantAvatarUrl, setAssistantAvatarUrl] = useState(null);

    const pamiAssistantRecommendations = [
        {
            title: "Recommendation 1",
            summary: "Several project tasks are moving slower than expected. Review blockers and ownership to keep the timeline stable.",
            bullets: [
                "12 tasks may miss due dates.",
                "3 blockers need approval.",
                "Reassign 2 developers."
            ]
        },
        {
            title: "Recommendation 2",
            summary: "Jira sync looks healthy, but some tasks are missing ownership details.",
            bullets: [
                "5 tasks have no owner.",
                "2 tasks miss priority.",
                "1 task has no context node."
            ]
        },
        {
            title: "Recommendation 3",
            summary: "Everything looks stable right now. No critical project changes are required.",
            bullets: [
                "No urgent risks detected.",
                "Velocity looks consistent.",
                "No action is required."
            ]
        }
    ];

    const [pamiAssistantIndex, setPamiAssistantIndex] = useState(0);
    const currentPamiAssistantRecommendation = pamiAssistantRecommendations[pamiAssistantIndex] || pamiAssistantRecommendations[0];
    const pamiSidebarAssistantImage = "/pami-assistant.png";

    const goToPreviousPamiRecommendation = () => {
        setPamiAssistantIndex((currentIndex) => {
            if (currentIndex <= 0) return pamiAssistantRecommendations.length - 1;
            return currentIndex - 1;
        });
    };

    const goToNextPamiRecommendation = () => {
        setPamiAssistantIndex((currentIndex) => {
            if (currentIndex >= pamiAssistantRecommendations.length - 1) return 0;
            return currentIndex + 1;
        });
    };
    const treeContainerRef = useRef(null);
    const fileInputRef = useRef(null);
    const forceStateRef = useRef(new Map());

    const siblingPairScores = useMemo(() => {
        const pairToWeight = new Map();

        Object.values(contextNodesMap || {}).forEach((projectNodes) => {
            (projectNodes || []).forEach((node) => {
                const sourceId = String(node.id || node._id || (node._id && node._id.$oid) || node._id || '');
                if (!sourceId) return;

                (node.sibling_links || []).forEach((link) => {
                    const targetId = String(link?.sibling_id || '');
                    const score = Number(link?.correlation_score || 0);
                    if (!targetId || targetId === sourceId || score < 30) return;

                    const pairKey = [sourceId, targetId].sort().join('::');
                    const previous = pairToWeight.get(pairKey);
                    if (!previous || score > previous) {
                        pairToWeight.set(pairKey, score);
                    }
                });
            });
        });

        return Array.from(pairToWeight.entries()).map(([pairKey, score]) => {
            const [leftId, rightId] = pairKey.split('::');
            return { leftId, rightId, score };
        });
    }, [contextNodesMap]);

    const restartForceSimulation = () => {
        setForceSimulationNonce((currentNonce) => currentNonce + 1);
    };

    const fetchProjects = async () => {
        setIsLoading(true);
        try {
            const response = await projectsApi.get("/projects/");
            console.log("Projects fetched:", response.data);
            setRealProjects(response.data);
            if (response.data && response.data.length > 0) {
                const pid = response.data[0].id || response.data[0]._id || (response.data[0]._id && response.data[0]._id.$oid) || null;
                if (pid) fetchContextNodes(pid);
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
                console.log('Fetched context nodes for', projectId, resp.data);
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
            }
        } catch (err) {
            console.error('Failed to fetch context nodes for', projectId, err);
        }
    };

    const handleCreateProject = async (e) => {
        e.preventDefault();
        if (!emailInput) {
            alert("Please enter a project name");
            return;
        }
        setIsLoading(true);
        try {
            const response = await projectsApi.post("/projects/", {
                name: emailInput,
                goal: tokenInput || "No goal defined",
                status: "active",
            });
            console.log("Project created successfully:", response.data);
            alert(`Project "${emailInput}" deployed!`);
            await fetchProjects();
            closeModal();
        } catch (error) {
            if (error.response) {
                console.error("Server Error Data:", error.response.data);
                alert("Server says: " + JSON.stringify(error.response.data));
            } else {
                console.error("Connection Error:", error.message);
                alert("Check your frontend .env and backend server.");
            }
        } finally {
            setIsLoading(false);
        }
    };

    const handleNodeColorChange = async (node, color) => {
        if (!node || !color || node.id === "root") return;

        const nodeId = node.id || node._id || (node._id && node._id.$oid) || null;
        if (!nodeId) {
            alert("Could not update color: selected node has no id.");
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

                setTimeout(() => {
                    try { drawConnections(); } catch (e) { console.error("drawConnections error", e); }
                }, 150);

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
        alert("Color changed visually, but failed to save to backend. Open the console to see the tried paths.");
    };

    useEffect(() => {
        fetchProjects();
        try {
            const saved = localStorage.getItem('pami.assistantAvatar');
            if (saved) setAssistantAvatarUrl(saved);
        } catch (e) { }
    }, []);

    useEffect(() => {
        if (realProjects && realProjects.length > 0) {
            const pid = realProjects[0].id || realProjects[0]._id || (realProjects[0]._id && realProjects[0]._id.$oid) || realProjects[0]._id || null;
            if (pid) fetchContextNodes(pid);
        }
    }, [realProjects]);

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
            const projectId = realProjects.length > 0 ? realProjects[0].id || realProjects[0]._id : "general";
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
        setIsChatLoading(true);
        try {
            let convId = conversationId;
            if (!convId) {
                convId = await createAIConversation();
                if (!convId) throw new Error("Could not create conversation");
            }

            const resp = await aiApi.post(`/ai-conversations/${convId}/messages`, {
                message: userMessage,
                context_snapshot: {
                    projects: realProjects.map((p) => ({ id: p.id || p._id, name: p.name })),
                    project_count: realProjects.length,
                },
            });

            const aiText = resp.data && (resp.data.response || resp.data.text || resp.data.message);
            setChatMessages((p) => [...p, { role: "assistant", content: aiText || "(no response)" }]);
        } catch (err) {
            console.error("Failed to send message to AI:", err);
            setChatMessages((p) => [...p, { role: "assistant", content: "I'm having trouble connecting right now. Please try again." }]);
        } finally {
            setIsChatLoading(false);
        }
    };

    const handleAvatarFile = (file) => {
        if (!file) return;
        const reader = new FileReader();
        reader.onload = (ev) => {
            const data = ev.target.result;
            try { localStorage.setItem('pami.assistantAvatar', data); } catch (e) { }
            setAssistantAvatarUrl(data);
        };
        reader.readAsDataURL(file);
    };

    const triggerAvatarUpload = () => fileInputRef.current && fileInputRef.current.click();

    const clearAssistantAvatar = () => {
        try { localStorage.removeItem('pami.assistantAvatar'); } catch (e) { }
        setAssistantAvatarUrl(null);
    };

    const getTreeStructure = () => {
        if (realProjects.length === 0) return null;
                const rootChildren = realProjects.map((proj) => {
            const pid = proj.id || proj._id || (proj._id && proj._id.$oid) || proj._id || 'unknown';
            const ctxNodes = contextNodesMap[pid] || [];

            const children = ctxNodes.map((n) => ({
                id: n.id || n._id || (n._id && n._id.$oid) || String(n._id),
                name: n.header ? (n.header.length > 40 ? n.header.slice(0, 40) + '…' : n.header) : 'Context Node',
                color: n.color || '#8b5cf6',
                status: n.node_type || 'context',
                goal: n.summary || n.header || 'No snapshot description available.',
                conversation_id: n.conversation_id || n.conversationId || n.conversation || null,
                sibling_links: n.sibling_links || [],
                project_id: pid,
                nodeKind: "context"
            }));

            return {
                id: pid,
                name: proj.name || 'Untitled Project',
                color: proj.color || '#2196f3',
                status: proj.status || 'Active',
                goal: proj.goal || 'No goal defined',
                nodeKind: "project",
                children,
            };
        });

        return {
            id: 'root',
            name: 'PAMI Global Core',
            color: '#f06292',
            status: 'Root',
            goal: 'Central orchestration system engine core.',
            nodeKind: "root",
            children: rootChildren,
        };
    };

    const closeModal = () => {
        setActiveModal(null);
        setSelectedNode(null);
        setNodeTasks([]);
        setSubNodes([]);
        setEmailInput("");
        setTokenInput("");
        setChannelNameInput("");
        setMessageChannelInput("");
        setMessageTextInput("");
    };

    const goToNodeConversation = async (node) => {
        if (!node) return;
        const convId = node.conversation_id || node.conversationId || node.conversation || null;
        if (!convId) {
            alert('This node has no associated conversation.');
            return;
        }

        try {
            // Fetch conversation history from AI service
            const resp = await aiApi.get(`/ai-conversations/${convId}`);
            if (resp && resp.data && resp.data.messages) {
                // Map messages into chat format
                const msgs = resp.data.messages.map((m) => ({ role: m.role || m.role, content: m.content || m.content }));
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
        } catch (err) {
            console.error('Failed to load conversation:', err);
            alert('Failed to load conversation. Check console for details.');
        }
    };

    const openModal = (type) => {
        if (type === "slack") {
            setActiveModal(slackConnected ? "slackActions" : "slack");
            return;
        }
        setActiveModal(type);
    };

    const handleNodeClick = async (node) => {
        if (node.id === "root") return;

        setSelectedNode(node);
        setActiveModal("viewNodeDetails");
        setIsModalDataLoading(true);

        try {
            const targetProjectId = node.nodeKind === "context"
                ? (node.project_id || node.projectId || node.project || node.id)
                : node.id;

            console.log(`Fetching live connected data for project: ${targetProjectId}`);
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
            } else {
                setSubNodes(allNodes);
            }
        } catch (error) {
            console.error("Failed to fetch node sub-resources:", error);
        } finally {
            setIsModalDataLoading(false);
        }
    };

    const fetchSlackChannels = async () => {
        const response = await slackApi.get("/list-channels");
        if (!response.data || response.data.ok !== true) {
            throw new Error(
                response.data && response.data.error ? response.data.error : "Failed to fetch Slack channels."
            );
        }
        return response.data.channels || [];
    };

    const handleConnect = async (e) => {
        e.preventDefault();
        setIsLoading(true);
        try {
            if (activeModal === "slack") {
                const channels = await fetchSlackChannels();
                setSlackConnected(true);
                setSlackChannels(channels);
                alert("Connected successfully to Slack!");
                setActiveModal("slackActions");
                return;
            }
            await api.post(`/integrate/${activeModal}`, {
                email: emailInput,
                token: tokenInput,
            });
            alert(`Connected successfully to ${activeModal}!`);
            closeModal();
        } catch (error) {
            console.error("Connection failed:", error);
            alert("Connection failed.");
        } finally {
            setIsLoading(false);
        }
    };

    const handleSlackTestConnection = async () => {
        setIsLoading(true);
        try {
            const response = await slackApi.post("/connection-check");
            if (!response.data || response.data.ok !== true) {
                throw new Error(response.data && response.data.error ? response.data.error : "Slack connection check failed.");
            }
            alert("Slack connection is healthy.");
        } catch (error) {
            console.error("Slack test connection failed:", error);
            alert("Slack test connection failed.");
        } finally {
            setIsLoading(false);
        }
    };

    const handleListChannels = async () => {
        setIsLoading(true);
        try {
            const channels = await fetchSlackChannels();
            setSlackChannels(channels);
            if (channels.length === 0) alert("No channels found.");
        } catch (error) {
            console.error("Failed to fetch channels:", error);
            alert("Failed to fetch Slack channels.");
        } finally {
            setIsLoading(false);
        }
    };

    const normalizeProjectId = (proj) => {
        if (!proj) return null;
        if (typeof proj === 'string') return proj;
        if (proj.id) return proj.id;
        if (proj._id) return proj._id && (proj._id.$oid || proj._id) ? (proj._id.$oid || proj._id) : proj._id;
        if (proj._id && proj._id.$oid) return proj._id.$oid;
        return null;
    };

    const handleCreateNodeFromConversation = async () => {
        console.log('Create node from conversation triggered');
        try {
            if (realProjects.length === 0) {
                alert('No project available to attach node to.');
                return;
            }
            const projectRaw = realProjects[0];
            const projectId = normalizeProjectId(projectRaw);
            console.log('Using project id:', projectId, projectRaw);
            if (!projectId) {
                alert('Could not determine project id for node creation.');
                return;
            }

            const recent = chatMessages.slice(-10).map((m) => `${m.role.toUpperCase()}: ${m.content}`).join('\n\n');
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

            console.log('POST body for create-node:', body);
            const resp = await projectsApi.post(`/context-tree/projects/${projectId}/nodes`, body);
            console.log('Create node response:', resp && resp.data ? resp.data : resp);
            if (resp && resp.data && resp.data.id) {
                alert('Node created from conversation: ' + (resp.data.name || resp.data.id));
                await fetchProjects();
                setTimeout(() => {
                    try {
                        drawConnections();
                    } catch (e) { }
                }, 200);
            } else if (resp && resp.status && resp.status >= 200 && resp.status < 300) {
                alert('Node created (no id returned).');
                await fetchProjects();
            } else {
                alert('Unexpected response from server. See console.');
            }
        } catch (err) {
            console.error('Failed to create node from conversation', err);
            if (err && err.response) console.error('Response data:', err.response.data);
            alert('Failed to create node from conversation. Check console/network for details.');
        }
    };

    const handleCreateSlackChannel = async (e) => {
        e.preventDefault();
        if (!channelNameInput) {
            alert("Please enter a channel name.");
            return;
        }
        setIsLoading(true);
        try {
            const response = await slackApi.post("/channels", { name: channelNameInput });
            if (!response.data || response.data.ok !== true) {
                throw new Error(response.data && response.data.error ? response.data.error : "Failed to create Slack channel.");
            }
            const channelName = response.data.channel_name ? response.data.channel_name : channelNameInput;
            if (response.data.already_exists === true) {
                alert(`Channel already exists: #${channelName}`);
            } else {
                alert(`Channel created successfully: #${channelName}`);
            }
            setChannelNameInput("");
            setActiveModal("slackActions");
            const channels = await fetchSlackChannels();
            setSlackChannels(channels);
        } catch (error) {
            console.error("Failed to create channel:", error);
            alert("Failed to create Slack channel.");
        } finally {
            setIsLoading(false);
        }
    };

    const handleSendSlackMessage = async (e) => {
        e.preventDefault();
        if (!messageChannelInput || !messageTextInput) {
            alert("Please enter both channel and message.");
            return;
        }
        setIsLoading(true);
        try {
            const response = await slackApi.post("/messages", {
                channel: messageChannelInput,
                text: messageTextInput,
            });
            if (!response.data || response.data.ok !== true) {
                throw new Error(response.data && response.data.error ? response.data.error : "Failed to send Slack message.");
            }
            alert(`Message sent successfully to ${messageChannelInput}`);
            setMessageChannelInput("");
            setMessageTextInput("");
            setActiveModal("slackActions");
        } catch (error) {
            console.error("Failed to send message:", error);
            alert("Failed to send Slack message.");
        } finally {
            setIsLoading(false);
        }
    };

    const renderTree = (node, parentId = null) => {
        if (!node) return null;
        return (
            <div className="tree-branch" key={node.id || node.name}>
                <div className="tree-node-wrapper" data-node-id={node.id} data-parent-id={parentId || ""}>
                    <div
                        className="neural-node-v2"
                        style={{
                            borderColor: node.color || "#2196f3",
                            "--node-color": node.color || "#2196f3",
                            cursor: node.id === "root" ? "default" : "pointer"
                        }}
                        onDoubleClick={() => handleNodeClick(node)}
                    >
                        <div className="node-dot" style={{ backgroundColor: node.color || "#2196f3", boxShadow: `0 0 0 3px ${node.color || "#2196f3"}22` }}></div>
                        <div className="node-content-v2">
                            <span className="node-name-v2">{node.name}</span>
                            <span className="node-status-v2">{node.status}</span>
                        </div>
                    </div>
                </div>
                {node.children && node.children.length > 0 && (
                    <div className="tree-children">
                        {node.children.map((child) => renderTree(child, node.id))}
                    </div>
                )}
            </div>
        );
    };

    const drawConnections = useCallback(() => {
        const container = treeContainerRef.current;
        if (!container) return;
        const svg = container.querySelector('svg.tree-svg-overlay');
        if (!svg) return;
        while (svg.firstChild) svg.removeChild(svg.firstChild);

        const nodes = Array.from(container.querySelectorAll('.tree-node-wrapper[data-node-id]'));
        const idToEl = {};
        nodes.forEach((el) => {
            const id = el.getAttribute('data-node-id');
            idToEl[id] = el;
        });

        const containerRect = container.getBoundingClientRect();

        const centers = new Map();
        Object.entries(idToEl).forEach(([id, el]) => {
            const visual = el.querySelector('.neural-node-v2') || el;
            const rect = visual.getBoundingClientRect();
            centers.set(id, {
                x: rect.left + rect.width / 2 - containerRect.left,
                y: rect.top + rect.height / 2 - containerRect.top,
            });
        });

        const getStrokeWidthForCorrelation = (score) => {
            const correlation = Number(score || 0);
            if (correlation < 30) return 0;
            if (correlation >= 100) return 8.0;
            const normalized = (correlation - 30) / 70;
            return Number((1.0 + normalized * 7.0).toFixed(2));
        };

        const getStrokeOpacityForCorrelation = (score) => {
            const correlation = Number(score || 0);
            if (correlation < 30) return 0;
            if (correlation >= 100) return 1;
            const normalized = (correlation - 30) / 70;
            return Number((0.18 + normalized * 0.82).toFixed(2));
        };
        const vw = Math.max(1, Math.round(containerRect.width));
        const vh = Math.max(1, Math.round(containerRect.height));
        svg.setAttribute('viewBox', `0 0 ${vw} ${vh}`);
        svg.setAttribute('preserveAspectRatio', 'none');
        svg.setAttribute('width', `${vw}`);
        svg.setAttribute('height', `${vh}`);

        siblingPairScores.forEach(({ leftId, rightId, score }) => {
            const leftCenter = centers.get(leftId);
            const rightCenter = centers.get(rightId);
            if (!leftCenter || !rightCenter) return;

            const startX = leftCenter.x;
            const startY = leftCenter.y;
            const endX = rightCenter.x;
            const endY = rightCenter.y;
            const correlationScore = score;

            const dx = endX - startX;
            const dy = endY - startY;
            const distance = Math.hypot(dx, dy) || 1;
            const normalX = -dy / distance;
            const normalY = dx / distance;
            const bow = Math.min(48, Math.max(18, distance * 0.08));
            const controlX = (startX + endX) / 2 + normalX * bow;
            const controlY = (startY + endY) / 2 + normalY * bow;

            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            const d = `M ${startX} ${startY} Q ${controlX} ${controlY} ${endX} ${endY}`;
            path.setAttribute('d', d);
            path.setAttribute('stroke', '#9ca3af');
            path.setAttribute('stroke-width', `${getStrokeWidthForCorrelation(correlationScore)}`);
            path.setAttribute('fill', 'none');
            path.setAttribute('stroke-linecap', 'round');
            path.setAttribute('opacity', `${getStrokeOpacityForCorrelation(correlationScore)}`);

            const title = document.createElementNS('http://www.w3.org/2000/svg', 'title');
            title.textContent = `Correlation score: ${Math.round(correlationScore)}/100`;
            path.appendChild(title);

            svg.appendChild(path);
        });
    }, [siblingPairScores]);

    useEffect(() => {
        if (activePane !== "tree") return;

        const t = setTimeout(drawConnections, 80);
        window.addEventListener("resize", drawConnections);

        return () => {
            clearTimeout(t);
            window.removeEventListener("resize", drawConnections);
        };
    }, [realProjects, activePane, isLoading, treeZoom, treeHeight, treePan, drawConnections]);

    useEffect(() => {
        if (activePane !== "tree") return undefined;

        let animationFrameId = null;
        let isCancelled = false;
        let simulationStartTime = null;
        let calmFrames = 0;
        let frameCounter = 0;

        const settleDurationMs = 2400;
        const calmMotionThreshold = 0.11;
        const calmFramesRequired = 5;

        const runForceStep = (elapsedMs) => {
            const container = treeContainerRef.current;
            if (!container) return { maxMotion: 0 };

            const wrappers = Array.from(container.querySelectorAll('.tree-node-wrapper[data-node-id]'));
            if (wrappers.length === 0) return { maxMotion: 0 };

            const zoom = Math.max(0.1, Number(treeZoom) || 1);
            const normalizedElapsed = Math.min(1, Math.max(0, elapsedMs / settleDurationMs));
            const cooling = 1 - normalizedElapsed;
            const burstMultiplier = 1 + cooling * 0.16;
            const nodes = [];
            const idToNode = new Map();

            wrappers.forEach((wrapper) => {
                const id = String(wrapper.getAttribute('data-node-id') || '');
                if (!id) return;

                const visual = wrapper.querySelector('.neural-node-v2') || wrapper;
                const rect = visual.getBoundingClientRect();
                const centerX = rect.left + rect.width / 2;
                const centerY = rect.top + rect.height / 2;

                const currentTranslateX = Number(wrapper.dataset.translateX || 0) || 0;
                const currentTranslateY = Number(wrapper.dataset.translateY || 0) || 0;
                const locked = wrapper.dataset.dragLocked === '1';

                let state = forceStateRef.current.get(id);
                if (!state) {
                    state = { vx: 0, vy: 0 };
                    forceStateRef.current.set(id, state);
                }

                const node = {
                    id,
                    wrapper,
                    centerX,
                    centerY,
                    halfWidth: rect.width / 2,
                    halfHeight: rect.height / 2,
                    radius: Math.max(16, Math.max(rect.width, rect.height) / 2),
                    translateX: currentTranslateX,
                    translateY: currentTranslateY,
                    locked,
                    fx: 0,
                    fy: 0,
                    state,
                };

                nodes.push(node);
                idToNode.set(id, node);
            });

            if (nodes.length === 0) return { maxMotion: 0 };

            const activeIds = new Set(nodes.map((node) => node.id));
            forceStateRef.current.forEach((_, key) => {
                if (!activeIds.has(key)) {
                    forceStateRef.current.delete(key);
                }
            });

            const repelStrength = (Number(repulsionForce) || 0) / 100;
            const attractStrength = (Number(connectionForce) || 0) / 100;

            for (let i = 0; i < nodes.length; i += 1) {
                for (let j = i + 1; j < nodes.length; j += 1) {
                    const a = nodes[i];
                    const b = nodes[j];

                    const dx = b.centerX - a.centerX;
                    const dy = b.centerY - a.centerY;
                    const distanceSq = dx * dx + dy * dy + 0.01;
                    const distance = Math.sqrt(distanceSq);
                    const ux = dx / distance;
                    const uy = dy / distance;

                    const repulsion = repelStrength * burstMultiplier * 24000 / (distanceSq + 900);
                    a.fx -= ux * repulsion;
                    a.fy -= uy * repulsion;
                    b.fx += ux * repulsion;
                    b.fy += uy * repulsion;

                    const collisionGap = a.radius + b.radius + 14;
                    if (distance < collisionGap) {
                        const overlap = collisionGap - distance;
                        const collision = (0.045 + cooling * 0.04) * overlap;
                        a.fx -= ux * collision;
                        a.fy -= uy * collision;
                        b.fx += ux * collision;
                        b.fy += uy * collision;
                    }
                }
            }

            siblingPairScores.forEach(({ leftId, rightId, score }) => {
                const left = idToNode.get(leftId);
                const right = idToNode.get(rightId);
                if (!left || !right) return;

                const dx = right.centerX - left.centerX;
                const dy = right.centerY - left.centerY;
                const distance = Math.max(1, Math.hypot(dx, dy));
                const ux = dx / distance;
                const uy = dy / distance;

                const normalized = Math.min(1, Math.max(0, (score - 30) / 70));
                const normalizedBoost = normalized * normalized;
                const desiredDistance = 340 - normalizedBoost * 300;
                const stretch = Math.max(0, distance - desiredDistance);
                const springZone = Math.min(1, stretch / 42);
                const attraction = attractStrength * burstMultiplier * (0.001 + normalizedBoost * 0.045) * stretch * springZone;

                // Anti-overshoot brake: when already near/inside target distance,
                // damp inward relative velocity to prevent bounce.
                if (distance <= desiredDistance + 10) {
                    const relVx = (right.state.vx || 0) - (left.state.vx || 0);
                    const relVy = (right.state.vy || 0) - (left.state.vy || 0);
                    const inwardSpeed = -(relVx * ux + relVy * uy);
                    if (inwardSpeed > 0) {
                        const brake = Math.min(0.24, inwardSpeed * 0.2);
                        left.fx -= ux * brake;
                        left.fy -= uy * brake;
                        right.fx += ux * brake;
                        right.fy += uy * brake;
                    }
                }

                left.fx += ux * attraction;
                left.fy += uy * attraction;
                right.fx -= ux * attraction;
                right.fy -= uy * attraction;
            });

            const damping = 0.96 + cooling * 0.02;
            const maxSpeed = 0.42 + cooling * 0.95;
            const containerRect = container.getBoundingClientRect();
            let maxMotion = 0;

            nodes.forEach((node) => {
                if (node.locked) {
                    node.state.vx = 0;
                    node.state.vy = 0;
                    return;
                }

                const centerBiasX = 0;
                const centerBiasY = 0;

                const maxForce = 0.32 + cooling * 0.7;
                if (node.fx > maxForce) node.fx = maxForce;
                if (node.fx < -maxForce) node.fx = -maxForce;
                if (node.fy > maxForce) node.fy = maxForce;
                if (node.fy < -maxForce) node.fy = -maxForce;

                const prevVx = node.state.vx;
                const prevVy = node.state.vy;
                node.state.vx = node.state.vx * damping + (node.fx + centerBiasX) * 0.24;
                node.state.vy = node.state.vy * damping + (node.fy + centerBiasY) * 0.24;

                if (prevVx * node.state.vx < 0) {
                    node.state.vx *= 0.18;
                }
                if (prevVy * node.state.vy < 0) {
                    node.state.vy *= 0.18;
                }

                const speed = Math.hypot(node.state.vx, node.state.vy);
                if (speed > maxSpeed) {
                    const scale = maxSpeed / speed;
                    node.state.vx *= scale;
                    node.state.vy *= scale;
                }

                const edgePadding = 8;
                const minCenterX = containerRect.left + node.halfWidth + edgePadding;
                const maxCenterX = containerRect.right - node.halfWidth - edgePadding;
                const minCenterY = containerRect.top + node.halfHeight + edgePadding;
                const maxCenterY = containerRect.bottom - node.halfHeight - edgePadding;

                const projectedCenterX = node.centerX + node.state.vx;
                const projectedCenterY = node.centerY + node.state.vy;

                let correctedVx = node.state.vx;
                let correctedVy = node.state.vy;

                if (projectedCenterX < minCenterX) {
                    correctedVx = minCenterX - node.centerX;
                    node.state.vx = 0;
                } else if (projectedCenterX > maxCenterX) {
                    correctedVx = maxCenterX - node.centerX;
                    node.state.vx = 0;
                }

                if (projectedCenterY < minCenterY) {
                    correctedVy = minCenterY - node.centerY;
                    node.state.vy = 0;
                } else if (projectedCenterY > maxCenterY) {
                    correctedVy = maxCenterY - node.centerY;
                    node.state.vy = 0;
                }

                const nextX = node.translateX + correctedVx / zoom;
                const nextY = node.translateY + correctedVy / zoom;

                const frameMotion = Math.hypot(nextX - node.translateX, nextY - node.translateY);
                if (frameMotion > maxMotion) maxMotion = frameMotion;

                if (elapsedMs > settleDurationMs * 0.65 && frameMotion < 0.04) {
                    node.state.vx = 0;
                    node.state.vy = 0;
                }

                node.wrapper.style.transform = `translate(${nextX}px, ${nextY}px)`;
                node.wrapper.dataset.translateX = String(Number(nextX.toFixed(2)));
                node.wrapper.dataset.translateY = String(Number(nextY.toFixed(2)));
            });

            frameCounter += 1;
            if (maxMotion > 0.03 || frameCounter % 3 === 0) {
                drawConnections();
            }
            return { maxMotion };
        };

        const loop = (timestamp) => {
            if (isCancelled) return;

            if (simulationStartTime === null) {
                simulationStartTime = timestamp;
            }

            const elapsedMs = timestamp - simulationStartTime;
            const { maxMotion } = runForceStep(elapsedMs);

            if (elapsedMs >= settleDurationMs && maxMotion <= calmMotionThreshold) {
                calmFrames += 1;
            } else {
                calmFrames = 0;
            }

            if (calmFrames >= calmFramesRequired || elapsedMs >= settleDurationMs + 250) {
                nodesSettleAndStop();
                return;
            }

            animationFrameId = window.requestAnimationFrame(loop);
        };

        const nodesSettleAndStop = () => {
            const container = treeContainerRef.current;
            if (!container) return;

            const wrappers = Array.from(container.querySelectorAll('.tree-node-wrapper[data-node-id]'));
            wrappers.forEach((wrapper) => {
                const id = String(wrapper.getAttribute('data-node-id') || '');
                if (!id) return;

                const state = forceStateRef.current.get(id);
                if (state) {
                    state.vx = 0;
                    state.vy = 0;
                }
            });

            drawConnections();
        };

        animationFrameId = window.requestAnimationFrame(loop);

        return () => {
            isCancelled = true;
            if (animationFrameId !== null) {
                window.cancelAnimationFrame(animationFrameId);
            }
        };
    }, [activePane, treeZoom, connectionForce, repulsionForce, forceSimulationNonce, siblingPairScores, drawConnections]);

    useEffect(() => {
        const container = treeContainerRef.current;
        if (!container) return;

        let active = null;
        let startX = 0;
        let startY = 0;
        let origX = 0;
        let origY = 0;
        let dragDrawFrameId = null;

        const scheduleDragRedraw = () => {
            if (dragDrawFrameId !== null) return;
            dragDrawFrameId = window.requestAnimationFrame(() => {
                dragDrawFrameId = null;
                drawConnections();
            });
        };

        const onPointerMove = (e) => {
            if (!active) return;

            const zoom = treeZoom || 1;
            const dx = (e.clientX - startX) / zoom;
            const dy = (e.clientY - startY) / zoom;

            const nx = origX + dx;
            const ny = origY + dy;

            active.style.transform = `translate(${nx}px, ${ny}px)`;
            active.dataset.translateX = nx;
            active.dataset.translateY = ny;

            scheduleDragRedraw();
        };

        const onPointerUp = () => {
            if (!active) return;
            delete active.dataset.dragLocked;
            restartForceSimulation();
            active = null;
            window.removeEventListener("pointermove", onPointerMove);
            window.removeEventListener("pointerup", onPointerUp);
        };

        const nodeEls = Array.from(container.querySelectorAll(".neural-node-v2"));
        nodeEls.forEach((nodeEl) => {
            nodeEl.style.touchAction = "none";
            const down = (e) => {
                if (e.button !== 0) return;
                if (isBoardDragArmed || e.detail >= 2) return;

                const wrapper = nodeEl.closest(".tree-node-wrapper");
                if (!wrapper) return;

                e.stopPropagation();

                active = wrapper;
                wrapper.dataset.dragLocked = "1";
                startX = e.clientX;
                startY = e.clientY;
                origX = parseFloat(wrapper.dataset.translateX || 0) || 0;
                origY = parseFloat(wrapper.dataset.translateY || 0) || 0;

                window.addEventListener("pointermove", onPointerMove);
                window.addEventListener("pointerup", onPointerUp);
            };

            nodeEl.addEventListener("pointerdown", down);
            nodeEl.__pami_down = down;
        });

        return () => {
            nodeEls.forEach((nodeEl) => {
                if (nodeEl.__pami_down) {
                    nodeEl.removeEventListener("pointerdown", nodeEl.__pami_down);
                }
                delete nodeEl.__pami_down;
            });

            window.removeEventListener("pointermove", onPointerMove);
            window.removeEventListener("pointerup", onPointerUp);

            if (dragDrawFrameId !== null) {
                window.cancelAnimationFrame(dragDrawFrameId);
                dragDrawFrameId = null;
            }
        };
    }, [realProjects, contextNodesMap, activePane, isLoading, treeZoom, drawConnections, isBoardDragArmed]);

    const handleTreeWheel = (e) => {
        if (activePane !== "tree") return;
        e.preventDefault();
        setTreeZoom((prevZoom) => {
            const direction = e.deltaY < 0 ? 1 : -1;
            const nextZoom = prevZoom + direction * 0.05;
            const clampedZoom = Math.min(1, Math.max(0.15, nextZoom));
            return Number(clampedZoom.toFixed(2));
        });
    };

    const toggleTreePanelHeight = () => {
        const { collapsedHeight, expandedHeight } = getTreePanelSizes();

        setTreeHeight((previousHeight) => {
            const isExpanded = previousHeight >= expandedHeight - 5;
            return isExpanded ? collapsedHeight : expandedHeight;
        });

        setTimeout(drawConnections, 260);
    };

    const handleTreeResizePointerDown = (e) => {
        e.preventDefault();
        e.stopPropagation();

        const panelElement = e.currentTarget.closest(".dashboard-grid-anchored");
        const panelRect = panelElement ? panelElement.getBoundingClientRect() : null;

        const startY = e.clientY;
        const basePanelHeight = 590;
        const topScreenLimit = -90;
        const panelBottom = panelRect ? panelRect.bottom : window.innerHeight - 24;
        const expandedPanelHeight = Math.max(basePanelHeight, Math.floor(panelBottom - topScreenLimit));
        const startHeight = Math.min(expandedPanelHeight, Math.max(basePanelHeight, treeHeight));
        const dragThreshold = 4;
        let didDrag = false;

        const handlePointerMove = (moveEvent) => {
            const deltaY = startY - moveEvent.clientY;

            if (Math.abs(deltaY) >= dragThreshold) {
                didDrag = true;
            }

            if (!didDrag) return;

            const nextHeight = startHeight + deltaY;
            const clampedHeight = Math.min(expandedPanelHeight, Math.max(basePanelHeight, nextHeight));
            setTreeHeight(clampedHeight);
        };

        const handlePointerUp = () => {
            window.removeEventListener("pointermove", handlePointerMove);
            window.removeEventListener("pointerup", handlePointerUp);

            if (!didDrag) {
                setTreeHeight((previousHeight) => {
                    const isExpanded = previousHeight >= expandedPanelHeight - 5;
                    return isExpanded ? basePanelHeight : expandedPanelHeight;
                });
            }

            setTimeout(drawConnections, 160);
        };

        window.addEventListener("pointermove", handlePointerMove);
        window.addEventListener("pointerup", handlePointerUp);
    };

    const handleTreePanPointerDown = (e) => {
        if (activePane !== "tree") return;

        const isDoubleClickLeft = e.button === 0 && e.detail >= 2;
        const isMiddleMousePan = e.button === 1;
        const isArmedLeftPan = e.button === 0 && (isBoardDragArmed || isDoubleClickLeft);
        if (!isMiddleMousePan && !isArmedLeftPan) return;
        if (isArmedLeftPan) {
            setIsBoardDragArmed(false);
        }

        e.preventDefault();
        e.stopPropagation();

        const startX = e.clientX;
        const startY = e.clientY;
        const startPanX = treePan.x;
        const startPanY = treePan.y;

        let animationFrameId = null;

        const scheduleConnectionRedraw = () => {
            if (animationFrameId !== null) return;

            animationFrameId = window.requestAnimationFrame(() => {
                animationFrameId = null;
                try {
                    drawConnections();
                } catch (error) {
                    console.error("drawConnections during tree pan failed:", error);
                }
            });
        };

        setIsTreePanning(true);

        const handlePointerMove = (moveEvent) => {
            moveEvent.preventDefault();

            const deltaX = moveEvent.clientX - startX;
            const deltaY = moveEvent.clientY - startY;

            setTreePan({
                x: startPanX + deltaX,
                y: startPanY + deltaY
            });

            scheduleConnectionRedraw();
        };

        const handlePointerUp = () => {
            window.removeEventListener("pointermove", handlePointerMove);
            window.removeEventListener("pointerup", handlePointerUp);

            if (animationFrameId !== null) {
                window.cancelAnimationFrame(animationFrameId);
                animationFrameId = null;
            }

            setIsTreePanning(false);

            window.requestAnimationFrame(() => {
                try {
                    drawConnections();
                } catch (error) {
                    console.error("final drawConnections after tree pan failed:", error);
                }

                setTimeout(drawConnections, 80);
            });
        };

        window.addEventListener("pointermove", handlePointerMove);
        window.addEventListener("pointerup", handlePointerUp);
    };

    const handleTreeCanvasDoubleClick = (e) => {
        if (activePane !== "tree") return;

        const targetElement = e.target;
        if (targetElement && typeof targetElement.closest === "function" && targetElement.closest(".neural-node-v2")) {
            return;
        }

        setIsBoardDragArmed(true);
    };

    // הפונקציות המלאות והתקינות של סלאק שממוקמות בצורה נכונה
    const renderSlackActionsModal = () => {
        return (
            <>
                <div className="modal-header" style={{ textAlign: "center", marginBottom: "20px" }}>
                    <img src="https://a.slack-edge.com/80588/marketing/img/icons/icon_slack_hash_colored.png" alt="Slack" style={{ height: "50px", marginBottom: "10px" }} />
                    <h2>Slack Actions</h2>
                    <p style={{ color: "#666", marginTop: "10px" }}>Choose the Slack action you want to perform.</p>
                </div>
                <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
                    <button type="button" onClick={handleSlackTestConnection} disabled={isLoading} style={{ width: "100%", padding: "12px", background: "#4a154b", color: "white", border: "none", borderRadius: "12px", fontWeight: "bold" }}>
                        Test Connection
                    </button>
                    <button type="button" onClick={handleListChannels} disabled={isLoading} style={{ width: "100%", padding: "12px", background: "#2f6fed", color: "white", border: "none", borderRadius: "12px", fontWeight: "bold" }}>
                        List Channels
                    </button>
                    <button type="button" onClick={() => setActiveModal("slackCreateChannel")} disabled={isLoading} style={{ width: "100%", padding: "12px", background: "#0f9d58", color: "white", border: "none", borderRadius: "12px", fontWeight: "bold" }}>
                        Create Channel
                    </button>
                    <button type="button" onClick={() => setActiveModal("slackSendMessage")} disabled={isLoading} style={{ width: "100%", padding: "12px", background: "#f06292", color: "white", border: "none", borderRadius: "12px", fontWeight: "bold" }}>
                        Send Message
                    </button>
                </div>

                {slackChannels.length > 0 && (
                    <div style={{ marginTop: "20px" }}>
                        <h3 style={{ marginBottom: "10px" }}>Channels</h3>
                        <div style={{ maxHeight: "180px", overflowY: "auto", border: "1px solid #eee", borderRadius: "12px", padding: "12px", background: "#fafafa" }}>
                            {slackChannels.map((channel) => (
                                <div key={channel.id} style={{ padding: "8px 0", borderBottom: "1px solid #eee" }}>
                                    #{channel.name}
                                </div>
                            ))}
                        </div>
                    </div>
                )}
            </>
        );
    };

    const renderSlackCreateChannelModal = () => {
        return (
            <>
                <div className="modal-header" style={{ textAlign: "center", marginBottom: "20px" }}>
                    <img src="https://a.slack-edge.com/80588/marketing/img/icons/icon_slack_hash_colored.png" alt="Slack" style={{ height: "50px", marginBottom: "10px" }} />
                    <h2>Create Slack Channel</h2>
                </div>
                <form className="modal-form" onSubmit={handleCreateSlackChannel}>
                    <div className="input-group" style={{ marginBottom: "20px" }}>
                        <label style={{ display: "block", marginBottom: "5px" }}>Channel Name</label>
                        <input type="text" placeholder="e.g. pami-demo-channel" required value={channelNameInput} onChange={(e) => setChannelNameInput(e.target.value)} style={{ width: "100%", padding: "10px", borderRadius: "8px", border: "1px solid #ddd" }} />
                    </div>
                    <button type="submit" className="login-submit-btn" disabled={isLoading} style={{ width: "100%", padding: "12px", background: "#0f9d58", color: "white", border: "none", borderRadius: "12px", fontWeight: "bold", marginBottom: "10px" }}>
                        {isLoading ? "Processing..." : "Create Channel"}
                    </button>
                    <button type="button" onClick={() => setActiveModal("slackActions")} style={{ width: "100%", padding: "12px", background: "#ddd", color: "#333", border: "none", borderRadius: "12px", fontWeight: "bold", cursor: "pointer" }}>
                        Back
                    </button>
                </form>
            </>
        );
    };

    const renderSlackSendMessageModal = () => {
        return (
            <>
                <div className="modal-header" style={{ textAlign: "center", marginBottom: "20px" }}>
                    <img src="https://a.slack-edge.com/80588/marketing/img/icons/icon_slack_hash_colored.png" alt="Slack" style={{ height: "50px", marginBottom: "10px" }} />
                    <h2>Send Slack Message</h2>
                </div>
                <form className="modal-form" onSubmit={handleSendSlackMessage}>
                    <div className="input-group" style={{ marginBottom: "15px" }}>
                        <label style={{ display: "block", marginBottom: "5px" }}>Channel</label>
                        <input type="text" placeholder="e.g. social or #social" required value={messageChannelInput} onChange={(e) => setMessageChannelInput(e.target.value)} style={{ width: "100%", padding: "10px", borderRadius: "8px", border: "1px solid #ddd" }} />
                    </div>
                    <div className="input-group" style={{ marginBottom: "20px" }}>
                        <label style={{ display: "block", marginBottom: "5px" }}>Message</label>
                        <input type="text" placeholder="Write a Slack message..." required value={messageTextInput} onChange={(e) => setMessageTextInput(e.target.value)} style={{ width: "100%", padding: "10px", borderRadius: "8px", border: "1px solid #ddd" }} />
                    </div>
                    <button type="submit" className="login-submit-btn" disabled={isLoading} style={{ width: "100%", padding: "12px", background: "#f06292", color: "white", border: "none", borderRadius: "12px", fontWeight: "bold", marginBottom: "10px" }}>
                        {isLoading ? "Processing..." : "Send Message"}
                    </button>
                    <button type="button" onClick={() => setActiveModal("slackActions")} style={{ width: "100%", padding: "12px", background: "#ddd", color: "#333", border: "none", borderRadius: "12px", fontWeight: "bold", cursor: "pointer" }}>
                        Back
                    </button>
                </form>
            </>
        );
    };

    const renderDefaultIntegrationModal = () => {
        return (
            <>
                <div className="modal-header" style={{ textAlign: "center", marginBottom: "20px" }}>
                    <img src={activeModal === "slack" ? "https://a.slack-edge.com/80588/marketing/img/icons/icon_slack_hash_colored.png" : "https://cdn.worldvectorlogo.com/logos/jira-1.svg"} alt={activeModal} style={{ height: "50px", marginBottom: "10px" }} />
                    <h2>Connect to {activeModal === "slack" ? "Slack" : "Jira"}</h2>
                </div>
                <form className="modal-form" onSubmit={handleConnect}>
                    <div className="input-group" style={{ marginBottom: "15px" }}>
                        <label style={{ display: "block", marginBottom: "5px" }}>Workspace Email</label>
                        <input type="email" placeholder="name@company.com" required value={emailInput} onChange={(e) => setEmailInput(e.target.value)} style={{ width: "100%", padding: "10px", borderRadius: "8px", border: "1px solid #ddd" }} />
                    </div>
                    <div className="input-group" style={{ marginBottom: "20px" }}>
                        <label style={{ display: "block", marginBottom: "5px" }}>Password / API Token</label>
                        <input type="password" placeholder="••••••••" value={tokenInput} onChange={(e) => setTokenInput(e.target.value)} style={{ width: "100%", padding: "10px", borderRadius: "8px", border: "1px solid #ddd" }} />
                    </div>
                    <button type="submit" className="login-submit-btn" disabled={isLoading} style={{ width: "100%", padding: "12px", background: "#f06292", color: "white", border: "none", borderRadius: "12px", fontWeight: "bold" }}>
                        {isLoading ? "Processing..." : "Connect Account"}
                    </button>
                </form>
            </>
        );
    };

    const renderSlackConnectModal = () => (
        <>
            <div
                className="modal-header"
                style={{
                    textAlign: "center",
                    marginBottom: "24px"
                }}
            >
                <div
                    style={{
                        width: "82px",
                        height: "82px",
                        borderRadius: "24px",
                        margin: "0 auto 16px auto",
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "center",
                        background: "linear-gradient(135deg, rgba(74,21,75,0.10), rgba(240,98,146,0.12))",
                        border: "1px solid rgba(74,21,75,0.10)",
                        boxShadow: "0 14px 34px rgba(74,21,75,0.12)"
                    }}
                >
                    <img
                        src="https://a.slack-edge.com/80588/marketing/img/icons/icon_slack_hash_colored.png"
                        alt="Slack"
                        style={{
                            width: "48px",
                            height: "48px",
                            objectFit: "contain"
                        }}
                    />
                </div>

                <h2 style={{ margin: "0 0 8px 0", color: "#202124", fontSize: "26px" }}>
                    Connect Slack Workspace
                </h2>

                <p
                    style={{
                        color: "#6b7280",
                        margin: "0 auto",
                        maxWidth: "340px",
                        fontSize: "14px",
                        lineHeight: "1.55"
                    }}
                >
                    Connect PAMI to Slack so the dashboard can check channels, create project channels,
                    and send operational updates directly to your workspace.
                </p>
            </div>

            <div
                style={{
                    display: "grid",
                    gridTemplateColumns: "1fr",
                    gap: "10px",
                    marginBottom: "22px"
                }}
            >
                <div
                    style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                        padding: "12px 14px",
                        borderRadius: "16px",
                        background: "#faf7ff",
                        border: "1px solid rgba(139,92,246,0.12)"
                    }}
                >
                    <span style={{ fontSize: "18px" }}>#</span>
                    <div>
                        <div style={{ fontWeight: "700", color: "#2d2438", fontSize: "13px" }}>
                            Channel Management
                        </div>
                        <div style={{ color: "#7b7286", fontSize: "12px", marginTop: "2px" }}>
                            List channels and create new Slack channels from PAMI.
                        </div>
                    </div>
                </div>

                <div
                    style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "10px",
                        padding: "12px 14px",
                        borderRadius: "16px",
                        background: "#fff7fb",
                        border: "1px solid rgba(240,98,146,0.14)"
                    }}
                >
                    <span style={{ fontSize: "18px" }}>↗</span>
                    <div>
                        <div style={{ fontWeight: "700", color: "#2d2438", fontSize: "13px" }}>
                            Team Updates
                        </div>
                        <div style={{ color: "#7b7286", fontSize: "12px", marginTop: "2px" }}>
                            Send messages to selected Slack channels from the dashboard.
                        </div>
                    </div>
                </div>
            </div>

            <form className="modal-form" onSubmit={handleConnect}>
                <button
                    type="submit"
                    className="login-submit-btn"
                    disabled={isLoading}
                    style={{
                        width: "100%",
                        padding: "14px",
                        background: "linear-gradient(135deg, #4a154b 0%, #8b3f8f 45%, #f06292 100%)",
                        color: "white",
                        border: "none",
                        borderRadius: "16px",
                        fontWeight: "800",
                        letterSpacing: "0.2px",
                        cursor: isLoading ? "not-allowed" : "pointer",
                        boxShadow: "0 14px 30px rgba(240,98,146,0.24)",
                        opacity: isLoading ? 0.7 : 1
                    }}
                >
                    {isLoading ? "Connecting..." : "Connect Slack"}
                </button>

                <p
                    style={{
                        margin: "12px 0 0 0",
                        textAlign: "center",
                        color: "#9ca3af",
                        fontSize: "12px"
                    }}
                >
                    Uses the configured Slack backend service. No manual token entry is required here.
                </p>
            </form>
        </>
    );

    const renderModalContent = () => {
        if (activeModal === "createProject") {
            return (
                <>
                    <div className="modal-header" style={{ textAlign: "center", marginBottom: "20px" }}>
                        <span style={{ fontSize: "40px" }}>📁</span>
                        <h2>Initialize New Node</h2>
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
                            {isLoading ? "Processing..." : "Deploy Node"}
                        </button>
                    </form>
                </>
            );
        }
        if (activeModal === "slack") return renderSlackConnectModal();
        if (activeModal === "slackActions") return renderSlackActionsModal();
        if (activeModal === "slackCreateChannel") return renderSlackCreateChannelModal();
        if (activeModal === "slackSendMessage") return renderSlackSendMessageModal();
        if (activeModal === "viewNodeDetails") return (
            <NodeDetailsModal
                selectedNode={selectedNode}
                nodeTasks={nodeTasks}
                subNodes={subNodes}
                isModalDataLoading={isModalDataLoading}
                closeModal={closeModal}
                fetchProjects={fetchProjects}
                drawConnections={drawConnections}
                onNodeColorChange={handleNodeColorChange}
                onOpenConversation={goToNodeConversation}
            />
        );
        return renderDefaultIntegrationModal();
    };

    const { expandedHeight: currentTreeExpandedHeight } = getTreePanelSizes();
    const isTreePanelExpanded = treeHeight >= currentTreeExpandedHeight - 5;

    return (
        <div className={`dashboard-container ${isSidebarOpen ? "sidebar-open" : "sidebar-closed"}`}>
            <aside className="sidebar">
                <div className="sidebar-logo">
                    <img src={pamiLogo} alt="Pami Logo" className="logo-img" />
                </div>
                <nav className="sidebar-nav">
                    <ul>
                        <li className="active">Neural Dashboard</li>
                        <li>Context Brain</li>
                        <li>Health Monitor</li>
                        <li>Workers</li>
                        <li>Settings</li>
                        <li className="logout-item" onClick={() => alert("Logging out...")}>
                            <span>🚪 Log Out</span>
                        </li>
                    </ul>
                </nav>
            
                <div className="pami-sidebar-assistant-panel">
                    <div className="pami-assistant-panel-header">
                        <div className="pami-assistant-panel-title">
                            <span className="pami-assistant-spark" aria-hidden="true"></span>
                            <span>PAMI Assistant</span>
                        </div>
                        <div className="pami-assistant-online">
                            <span></span>
                            Online
                        </div>
                    </div>

                    <div className="pami-assistant-bubble">
                        <div className="pami-assistant-bubble-top">
                            <div className="pami-assistant-recommendation-title">
                                <span className="pami-assistant-mini-spark" aria-hidden="true"></span>
                                <span>{currentPamiAssistantRecommendation.title}</span>
                            </div>

                            <div className="pami-assistant-pager">
                                <button
                                    type="button"
                                    className="pami-assistant-page-btn"
                                    onClick={goToPreviousPamiRecommendation}
                                    aria-label="Previous PAMI recommendation"
                                >
                                    ‹
                                </button>
                                <span>{pamiAssistantIndex + 1} / {pamiAssistantRecommendations.length}</span>
                                <button
                                    type="button"
                                    className="pami-assistant-page-btn"
                                    onClick={goToNextPamiRecommendation}
                                    aria-label="Next PAMI recommendation"
                                >
                                    ›
                                </button>
                            </div>
                        </div>

                        <div className="pami-assistant-message">
                            <p>{currentPamiAssistantRecommendation.summary}</p>
                            <ul>
                                {currentPamiAssistantRecommendation.bullets.map((bullet, idx) => (
                                    <li key={idx}>{bullet}</li>
                                ))}
                            </ul>
                        </div>
                    </div>

                    <div className="pami-assistant-robot-wrap">
                        <img
                            src={assistantAvatarUrl || pamiSidebarAssistantImage}
                            alt="PAMI assistant avatar"
                            className="pami-assistant-avatar-image"
                        />
                    </div>

                    <div className="pami-assistant-actions">
                        <button type="button" className="pami-assistant-check-btn">
                            Check for new
                        </button>
                        <button type="button" className="pami-assistant-history-btn">
                            History
                        </button>
                    </div>
                </div>

</aside>

            <main className={`main-content ${isSidebarOpen ? "sidebar-open" : "sidebar-closed"}`}>
                <header className="top-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%", boxSizing: "border-box", flexShrink: 0 }}>
                    <div className="header-left" style={{ display: "flex", alignItems: "center", flex: "0 0 auto" }}>
                        <button className="menu-toggle" onClick={() => setIsSidebarOpen(!isSidebarOpen)}>☰</button>
                        <div className="search-bar">
                            <span className="search-icon">🔍</span>
                            <input type="text" placeholder="Search the machine memory..." />
                        </div>
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
                            <span className="header-stat-icon header-stat-icon-nodes" aria-hidden="true"></span><strong className="header-stat-value">{realProjects.length}</strong><span className="header-stat-label">NODES</span>
                        </div>
                        <div className="header-stat-separator" style={{ width: "1px", height: "18px", background: "rgba(143, 109, 242, 0.16)", flexShrink: 0 }} />
                        <div className="header-stat-item" style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "14px", whiteSpace: "nowrap", flexShrink: 0 }}>
                            <span className="header-stat-icon header-stat-icon-workers" aria-hidden="true"></span><strong className="header-stat-value">12</strong><span className="header-stat-label">WORKERS</span>
                        </div>
                        <div className="header-stat-separator" style={{ width: "1px", height: "18px", background: "rgba(143, 109, 242, 0.16)", flexShrink: 0 }} />
                        <div className="header-stat-item" style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "14px", whiteSpace: "nowrap", flexShrink: 0 }}>
                            <span className="header-stat-icon header-stat-icon-velocity" aria-hidden="true"></span><strong className="header-stat-value">84%</strong><span className="header-stat-label">VELOCITY</span>
                        </div>
                        <div className="header-stat-separator" style={{ width: "1px", height: "18px", background: "rgba(143, 109, 242, 0.16)", flexShrink: 0 }} />
                        <div className="header-stat-item" style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "14px", whiteSpace: "nowrap", flexShrink: 0 }}>
                            <span className="header-stat-icon header-stat-icon-uptime" aria-hidden="true"></span><strong className="header-stat-value">99.9%</strong><span className="header-stat-label">UPTIME</span>
                        </div>
                    </div>

                    <div className="header-right" style={{ display: "flex", alignItems: "center", gap: "15px", flex: "0 0 auto" }}>
                        <span className="notification">🔔</span>
                        <button className="new-node-btn" onClick={() => openModal("createProject")}>+ New Node</button>
                    </div>
                </header>

                <div className={`dashboard-grid dashboard-grid-anchored ${isTreePanelExpanded ? "tree-panel-expanded" : ""}`} style={{
                    height: `${treeHeight}px`,
                    "--tree-panel-height": `${treeHeight}px`
                }}>
                    <div className="project-tree-container">
                        <div className="project-tree-header">
                            <div className="tree-title-group tabs">
                                <button className={`tab-btn ${activePane === "tree" ? "active" : ""}`} onClick={async () => { setActivePane("tree"); try { await fetchProjects(); } catch (e) { console.error('Failed to refresh projects on tab switch', e); } }}>Project Tree</button>
                                <button className={`tab-btn ${activePane === "chat" ? "active" : ""}`} onClick={() => { setActivePane("chat"); setConversationId(null); setChatMessages([]); }}>AI Chat</button>
                            </div>
                            {activePane === "tree" && (
                                <div className="tree-force-controls">
                                    <label className="tree-force-control" title="How strongly linked nodes pull toward each other">
                                        <span>Connection Force</span>
                                        <input
                                            type="range"
                                            min="0"
                                            max="100"
                                            value={connectionForce}
                                            onChange={(e) => setConnectionForce(Number(e.target.value))}
                                        />
                                        <strong>{connectionForce}</strong>
                                    </label>

                                    <label className="tree-force-control" title="How strongly all nodes push away from each other">
                                        <span>Repel Force</span>
                                        <input
                                            type="range"
                                            min="0"
                                            max="100"
                                            value={repulsionForce}
                                            onChange={(e) => setRepulsionForce(Number(e.target.value))}
                                        />
                                        <strong>{repulsionForce}</strong>
                                    </label>
                                </div>
                            )}
                        </div>

                        <div
                            className={`project-tree-canvas tree-resizable-canvas ${isTreePanning ? "tree-panning" : ""}`}
                            style={{ flex: 1, minHeight: 0 }}
                            onWheel={handleTreeWheel}
                            onPointerDown={handleTreePanPointerDown}
                            onDoubleClick={handleTreeCanvasDoubleClick}
                            onAuxClick={(e) => {
                                if (e.button === 1) e.preventDefault();
                            }}
                        >
                            <button
                                type="button"
                                className="tree-resize-handle"
                                onClick={(e) => {
                                    e.preventDefault();
                                    e.stopPropagation();
                                    toggleTreePanelHeight();
                                }}
                                title="Resize tree / chat area"
                            />

                            {activePane === "tree" ? (
                                isLoading && realProjects.length === 0 ? (
                                    <div className="empty-tree-state">
                                        <div className="loading-spinner"></div>
                                        <p>Connecting to Neural Cloud...</p>
                                    </div>
                                ) : realProjects.length > 0 ? (
                                    <div ref={treeContainerRef} className="hierarchical-tree-container" style={{ position: "relative" }}>
                                        <div className="tree-zoom-indicator">{Math.round(treeZoom * 100)}%</div>
                                        <svg className="tree-svg-overlay" style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", pointerEvents: "none", overflow: "visible", zIndex: 1 }} />
                                        <div className="tree-zoom-layer" style={{ position: "relative", zIndex: 3, transform: `translate(${treePan.x}px, ${treePan.y}px) scale(${treeZoom})`, transformOrigin: "top center" }}>
                                            {renderTree(getTreeStructure())}
                                        </div>
                                    </div>
                                ) : (
                                    <div className="empty-tree-state">
                                        <p>No active nodes found on server.</p>
                                        <button className="create-first-btn" onClick={() => openModal("createProject")}>+ Create First Project</button>
                                    </div>
                                )
                            ) : (
                                <div className="pami-chat-pane" style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0, overflow: "hidden" }}>
                                    <div className="chat-header" style={{ padding: "12px 16px", borderBottom: "1px solid #eee", justifyContent: "space-between", display: "flex" }}>
                                        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                                            <strong>PAMI Conversation</strong>
                                            <span style={{ marginLeft: 12, color: "#666" }}>AI channel</span>
                                        </div>
                                        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                                            <button title="Upload assistant avatar" onClick={triggerAvatarUpload} style={{ background: "transparent", border: "none", cursor: "pointer" }}>📤</button>
                                            {assistantAvatarUrl && <button title="Clear avatar" onClick={clearAssistantAvatar} style={{ background: "transparent", border: "none", cursor: "pointer" }}>✖️</button>}
                                            <input ref={fileInputRef} type="file" accept="image/*" style={{ display: "none" }} onChange={(e) => handleAvatarFile(e.target.files && e.target.files[0])} />
                                            <button type="button" className="create-node-btn" title="Create node from conversation" onClick={handleCreateNodeFromConversation} style={{ marginLeft: 6 }} disabled={realProjects.length === 0 || chatMessages.length === 0}>➕ Create Node</button>
                                        </div>
                                    </div>
                                    <div className="chat-body" style={{ padding: "16px", overflowY: "auto", overflowX: "hidden", flex: 1, minHeight: 0 }}>
                                        {chatMessages.length === 0 ? (
                                            <div className="chat-empty-state"><p>💬 Start chatting with PAMI AI</p></div>
                                        ) : (
                                            chatMessages.map((msg, idx) => {
                                                const isUser = (msg.role === "user");
                                                const roleClass = isUser ? "user" : "assistant";
                                                return (
                                                    <div key={idx} className={`chat-message ${roleClass}`}>
                                                        {isUser ? (
                                                            <div className="message-avatar user-avatar"><img src="/mario.png" alt="user" /></div>
                                                        ) : (
                                                            <div className="message-avatar assistant" style={{ backgroundImage: `url(${assistantAvatarUrl || "/pami_ai_avatar.png"})` }} />
                                                        )}
                                                        <div className="message-content"><p>{msg.content}</p></div>
                                                    </div>
                                                );
                                            })
                                        )}
                                        {isChatLoading && (
                                            <div className="chat-message assistant">
                                                <div className="message-avatar">🤖</div>
                                                <div className="message-content">
                                                    <div className="typing-indicator"><span></span><span></span><span></span></div>
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                    <div className="chat-input" style={{ padding: "12px", borderTop: "1px solid #eee", display: "flex", gap: "8px" }}>
                                        <input type="text" placeholder="Ask PAMI anything..." value={chatInput} onChange={(e) => setChatInput(e.target.value)} onKeyPress={(e) => e.key === "Enter" && handleSendMessage()} disabled={isChatLoading} style={{ flex: 1, padding: "10px", borderRadius: "8px", border: "1px solid #ddd" }} />
                                        <button onClick={handleSendMessage} disabled={isChatLoading || !chatInput.trim()} style={{ padding: "10px 14px", borderRadius: "8px", background: "#2f6fed", color: "white", border: "none" }}>Send</button>
                                    </div>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </main>

            <aside className="integrations-fixed-container" style={{ position: "fixed", right: "30px", top: "200px", zIndex: 9999 }}>
                <div className="integrations-stack" style={{ display: "flex", flexDirection: "column", gap: "15px" }}>
                    <button type="button" className="integration-icon-btn slack-btn" onClick={() => openModal("slack")} style={{ cursor: "pointer", background: "white", border: "1px solid #eee", borderRadius: "18px", width: "70px", height: "70px", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 4px 12px rgba(0,0,0,0.1)" }}>
                        <img src="https://a.slack-edge.com/80588/marketing/img/icons/icon_slack_hash_colored.png" alt="Slack" style={{ width: "40px" }} />
                    </button>
                    <button type="button" className="integration-icon-btn jira-btn" onClick={() => openModal("jira")} style={{ cursor: "pointer", background: "white", border: "1px solid #eee", borderRadius: "18px", width: "70px", height: "70px", display: "flex", alignItems: "center", justifyContent: "center", boxShadow: "0 4px 12px rgba(0,0,0,0.1)" }}>
                        <img src="https://cdn.worldvectorlogo.com/logos/jira-1.svg" alt="Jira" style={{ width: "40px" }} />
                    </button>
                </div>
            </aside>

            {activeModal && (
                <div className="modal-overlay" onClick={closeModal} style={{ position: "fixed", top: 0, left: 0, width: "100%", height: "100%", background: "rgba(0,0,0,0.5)", display: "flex", justifyContent: "center", alignItems: "center", zIndex: 10000 }}>
                    <div className="modal-content" onClick={(e) => e.stopPropagation()} style={{ background: "white", padding: "40px", borderRadius: "30px", width: "450px", position: "relative" }}>
                        <button className="close-modal-btn" onClick={closeModal} style={{ position: "absolute", top: "20px", right: "20px", border: "none", background: "none", fontSize: "24px", cursor: "pointer" }}>&times;</button>
                        {renderModalContent()}
                    </div>
                </div>
            )}
        </div>
    );
};

export default HomePage;