import React, { useState, useEffect, useRef } from "react";
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
        <>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "15px" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
                    <span style={{ fontSize: "40px" }}>🧠</span>
                    <h2 style={{ marginTop: "5px", color: "#333" }}>Node Blueprint Context</h2>
                </div>
                <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                    <button onClick={handleDelete} disabled={isDeleting} style={{ background: "transparent", border: "none", cursor: isDeleting ? "not-allowed" : "pointer", fontSize: "20px" }} title="Delete node">
                        🗑️
                    </button>
                    <button onClick={() => onOpenConversation && onOpenConversation(selectedNode)} style={{ background: "transparent", border: "none", cursor: 'pointer', fontSize: "18px" }} title="Open node chat">
                        💬 Open Chat
                    </button>
                </div>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", marginTop: "-6px", marginBottom: "8px" }}>
                <div
                    title="Node color"
                    style={{
                        display: "flex",
                        alignItems: "center",
                        gap: "5px",
                        padding: "5px 7px",
                        borderRadius: "999px",
                        background: "rgba(255,255,255,0.84)",
                        border: "1px solid rgba(0,0,0,0.08)",
                        boxShadow: "0 4px 12px rgba(0,0,0,0.06)"
                    }}
                >
                    {nodeColorOptions.map((option) => (
                        <button
                            key={option.value}
                            type="button"
                            disabled={isSavingColor}
                            title={option.label}
                            aria-label={`Set node color to ${option.label}`}
                            onClick={() => handleColorSelect(option.value)}
                            style={{
                                width: "18px",
                                height: "18px",
                                borderRadius: "999px",
                                border: nodeColor === option.value ? "2px solid #111827" : "2px solid rgba(255,255,255,0.9)",
                                background: option.value,
                                color: "white",
                                cursor: isSavingColor ? "not-allowed" : "pointer",
                                boxShadow: nodeColor === option.value ? "0 0 0 2px rgba(17,24,39,0.12)" : "0 3px 8px rgba(0,0,0,0.10)",
                                fontSize: "10px",
                                fontWeight: "bold",
                                lineHeight: "12px",
                                padding: 0,
                            }}
                        >
                            {nodeColor === option.value ? "✓" : ""}
                        </button>
                    ))}
                </div>
            </div>

            <div style={{ background: "#f9f9f9", padding: "15px", borderRadius: "16px", border: `2px solid ${nodeColor}`, maxHeight: "400px", overflowY: "auto", marginBottom: "20px" }}>
                <div style={{ marginBottom: "12px" }}>
                    <strong style={{ color: "#555", fontSize: "11px", letterSpacing: "0.5px" }}>NODE IDENTIFIER:</strong>
                    <p style={{ margin: "2px 0 0 0", fontSize: "16px", fontWeight: "bold", color: "#111" }}>{selectedNode.name}</p>
                </div>

                <div style={{ marginBottom: "12px", background: "#fff", padding: "12px", borderRadius: "12px", borderLeft: `4px solid ${nodeColor}`, boxShadow: "0 2px 6px rgba(0,0,0,0.02)" }}>
                    <strong style={{ color: nodeColor, fontSize: "11px", letterSpacing: "0.5px", fontWeight: "bold" }}>NODE DESCRIPTION & MISSION OBJECTIVE:</strong>
                    <p style={{ margin: "6px 0 0 0", color: "#2c3e50", fontStyle: "normal", fontSize: "14px", lineHeight: "1.5" }}>
                        {selectedNode.goal || "No description or mission objectives have been configured for this intelligence layer."}
                    </p>
                </div>

                <div style={{ display: "flex", gap: "15px", marginBottom: "10px" }}>
                    <div>
                        <strong style={{ color: "#555", fontSize: "11px" }}>LAYER TYPE:</strong>
                        <p style={{ margin: "2px 0 0 0", fontSize: "13px", fontWeight: "600", textTransform: "uppercase", color: "#666" }}>{selectedNode.status}</p>
                    </div>
                </div>

                <hr style={{ border: "none", borderTop: "1px solid #ddd", margin: "15px 0" }} />

                {isModalDataLoading ? (
                    <div style={{ textAlign: "center", padding: "20px 0" }}>
                        <div className="loading-spinner" style={{ margin: "0 auto 10px auto", width: "25px", height: "25px" }}></div>
                        <p style={{ fontSize: "13px", color: "#666" }}>Querying sub-resources from cloud...</p>
                    </div>
                ) : (
                    <>
                        <div style={{ marginBottom: "15px" }}>
                            <strong style={{ color: "#f06292", fontSize: "13px" }}>CONNECTED SUB-NODES ({subNodes.length}):</strong>
                            {subNodes.length > 0 ? (
                                <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "6px" }}>
                                    {subNodes.map((sub, idx) => (
                                        <span key={idx} style={{ background: "#f06292", color: "white", padding: "4px 10px", borderRadius: "20px", fontSize: "12px", fontWeight: "bold" }}>
                                            🌿 {sub.header || sub.name || "Sub Node"}
                                        </span>
                                    ))}
                                </div>
                            ) : (
                                <p style={{ margin: "4px 0 0 0", fontSize: "13px", color: "#888" }}>No sub-nodes attached to this context layer.</p>
                            )}
                        </div>

                        <div>
                            <strong style={{ color: "#2f6fed", fontSize: "13px" }}>ACTIVE ATTACHED TASKS ({nodeTasks.length}):</strong>
                            {nodeTasks.length > 0 ? (
                                <ul style={{ margin: "6px 0 0 0", paddingLeft: "20px", fontSize: "13px", color: "#333" }}>
                                    {nodeTasks.map((task, idx) => (
                                        <li key={idx} style={{ marginBottom: "4px" }}>
                                            <strong>{task.title || "Task"}</strong> - <span style={{ color: "#666" }}>{task.status || "pending"}</span>
                                        </li>
                                    ))}
                                </ul>
                            ) : (
                                <p style={{ margin: "4px 0 0 0", fontSize: "13px", color: "#888" }}>No direct active operational tasks configured.</p>
                            )}
                        </div>
                    </>
                )}
            </div>

            <button type="button" onClick={closeModal} style={{ width: "100%", padding: "12px", background: nodeColor, color: "white", border: "none", borderRadius: "12px", fontWeight: "bold", cursor: "pointer" }}>
                Close Blueprint View
            </button>
        </>
    );
};

const HomePage = () => {
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [activePane, setActivePane] = useState("tree");
    const [treeZoom, setTreeZoom] = useState(1);
    const [treeHeight, setTreeHeight] = useState(590);
    const [treePan, setTreePan] = useState({ x: 0, y: 0 });
    const [isTreePanning, setIsTreePanning] = useState(false);
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
    const treeContainerRef = useRef(null);
    const fileInputRef = useRef(null);

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
            console.log(`Fetching live connected data for project: ${node.id}`);
            const [tasksRes, nodesRes] = await Promise.all([
                projectsApi.get(`/tasks/projects/${node.id}/tasks`).catch(() => ({ data: [] })),
                projectsApi.get(`/context-tree/projects/${node.id}/nodes`).catch(() => ({ data: [] }))
            ]);

            setNodeTasks(tasksRes.data || []);
            setSubNodes(nodesRes.data || []);
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
            const body = {
                parent_id: null,
                children_ids: [],
                text: recent || 'Conversation snapshot',
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

    const drawConnections = () => {
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

        nodes.forEach((el) => {
            const parentId = el.getAttribute('data-parent-id');
            if (!parentId) return;
            const parentEl = idToEl[parentId];
            if (!parentEl) return;

            const parentVisual = parentEl.querySelector('.neural-node-v2') || parentEl;
            const childVisual = el.querySelector('.neural-node-v2') || el;

            const pRect = parentVisual.getBoundingClientRect();
            const cRect = childVisual.getBoundingClientRect();
            const containerRect = container.getBoundingClientRect();

            const startX = pRect.left + pRect.width / 2 - containerRect.left;
            const startY = pRect.top + pRect.height - containerRect.top;
            const endX = cRect.left + cRect.width / 2 - containerRect.left;
            const endY = cRect.top - containerRect.top;

            const vw = Math.max(1, Math.round(containerRect.width));
            const vh = Math.max(1, Math.round(containerRect.height));
            svg.setAttribute('viewBox', `0 0 ${vw} ${vh}`);
            svg.setAttribute('preserveAspectRatio', 'none');
            svg.setAttribute('width', `${vw}`);
            svg.setAttribute('height', `${vh}`);

            const deltaX = Math.max(30, Math.abs(endX - startX) * 0.28);
            const control1X = startX + (endX > startX ? deltaX : -deltaX);
            const control2X = endX - (endX > startX ? deltaX : -deltaX);
            const verticalGap = Math.max(30, (endY - startY) * 0.25);
            const control1Y = startY + verticalGap;
            const control2Y = endY - verticalGap;

            const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
            const d = `M ${startX} ${startY} C ${control1X} ${control1Y} ${control2X} ${control2Y} ${endX} ${endY}`;
            path.setAttribute('d', d);
            path.setAttribute('stroke', getComputedStyle(document.documentElement).getPropertyValue('--connector-color') || '#d1d9e2');
            path.setAttribute('stroke-width', '2');
            path.setAttribute('fill', 'none');
            path.setAttribute('stroke-linecap', 'round');
            svg.appendChild(path);
        });
    };

    useEffect(() => {
        if (activePane !== "tree") return;

        const t = setTimeout(drawConnections, 80);
        window.addEventListener("resize", drawConnections);

        return () => {
            clearTimeout(t);
            window.removeEventListener("resize", drawConnections);
        };
    }, [realProjects, contextNodesMap, activePane, isLoading, treeZoom, treeHeight, treePan]);

    useEffect(() => {
        const container = treeContainerRef.current;
        if (!container) return;

        let active = null;
        let startX = 0;
        let startY = 0;
        let origX = 0;
        let origY = 0;

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

            drawConnections();
        };

        const onPointerUp = () => {
            if (!active) return;
            active = null;
            window.removeEventListener("pointermove", onPointerMove);
            window.removeEventListener("pointerup", onPointerUp);
        };

        const nodeEls = Array.from(container.querySelectorAll(".neural-node-v2"));
        nodeEls.forEach((nodeEl) => {
            nodeEl.style.touchAction = "none";
            const down = (e) => {
                if (e.button !== 0) return;

                const wrapper = nodeEl.closest(".tree-node-wrapper");
                if (!wrapper) return;

                e.stopPropagation();

                active = wrapper;
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
        };
    }, [realProjects, contextNodesMap, activePane, isLoading, treeZoom]);

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
        if (e.button !== 1) return;

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
            </aside>

            <main className="main-content">
                <header className="top-header" style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
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
                        gap: "15px",
                        background: "rgba(255, 255, 255, 0.5)",
                        padding: "6px 16px",
                        borderRadius: "14px",
                        border: "1px solid rgba(0,0,0,0.04)",
                        margin: "0 20px",
                        flex: "1",
                        justifyContent: "center",
                        overflowX: "auto"
                    }}>
                        <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", whiteSpace: "nowrap" }}>
                            <span>💼</span> <strong style={{ color: "#333" }}>{realProjects.length}</strong> <span style={{ color: "#666", fontSize: "11px" }}>NODES</span>
                        </div>
                        <div style={{ width: "1px", height: "14px", background: "#ddd" }} />
                        <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", whiteSpace: "nowrap" }}>
                            <span>👥</span> <strong style={{ color: "#333" }}>12</strong> <span style={{ color: "#666", fontSize: "11px" }}>WORKERS</span>
                        </div>
                        <div style={{ width: "1px", height: "14px", background: "#ddd" }} />
                        <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", whiteSpace: "nowrap" }}>
                            <span>📈</span> <strong style={{ color: "#333" }}>84%</strong> <span style={{ color: "#666", fontSize: "11px" }}>VELOCITY</span>
                        </div>
                        <div style={{ width: "1px", height: "14px", background: "#ddd" }} />
                        <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "12px", whiteSpace: "nowrap" }}>
                            <span>⚙️</span> <strong style={{ color: "#333" }}>99.9%</strong> <span style={{ color: "#666", fontSize: "11px" }}>UPTIME</span>
                        </div>
                    </div>

                    <div className="header-right" style={{ display: "flex", alignItems: "center", gap: "15px", flex: "0 0 auto" }}>
                        <span className="notification">🔔</span>
                        <button className="new-node-btn" onClick={() => openModal("createProject")}>+ New Node</button>
                    </div>
                </header>

                <div className="dashboard-grid dashboard-grid-anchored" style={{
                    height: `${treeHeight}px`,
                    flexBasis: `${treeHeight}px`,
                    marginTop: `-${Math.max(0, treeHeight - 590)}px`
                }}>
                    <div className="project-tree-container">
                        <div className="project-tree-header">
                            <div className="tree-title-group tabs">
                                <button className={`tab-btn ${activePane === "tree" ? "active" : ""}`} onClick={async () => { setActivePane("tree"); try { await fetchProjects(); } catch (e) { console.error('Failed to refresh projects on tab switch', e); } }}>Project Tree</button>
                                <button className={`tab-btn ${activePane === "chat" ? "active" : ""}`} onClick={() => { setActivePane("chat"); setConversationId(null); setChatMessages([]); }}>AI Chat</button>
                            </div>
                        </div>

                        <div
                            className={`project-tree-canvas tree-resizable-canvas ${isTreePanning ? "tree-panning" : ""}`}
                            style={{ flex: 1, minHeight: 0 }}
                            onWheel={handleTreeWheel}
                            onPointerDown={handleTreePanPointerDown}
                            onAuxClick={(e) => {
                                if (e.button === 1) e.preventDefault();
                            }}
                        >
                            <div className="tree-resize-handle" onPointerDown={handleTreeResizePointerDown} title="Drag top edge to resize tree / chat area" />

                            {activePane === "tree" ? (
                                isLoading && realProjects.length === 0 ? (
                                    <div className="empty-tree-state">
                                        <div className="loading-spinner"></div>
                                        <p>Connecting to Neural Cloud...</p>
                                    </div>
                                ) : realProjects.length > 0 ? (
                                    <div ref={treeContainerRef} className="hierarchical-tree-container" style={{ position: "relative" }}>
                                        <div className="tree-zoom-indicator">{Math.round(treeZoom * 100)}%</div>
                                        <svg className="tree-svg-overlay" style={{ position: "absolute", top: 0, left: 0, width: "100%", height: "100%", pointerEvents: "none", overflow: "visible", zIndex: 5 }} />
                                        <div className="tree-zoom-layer" style={{ transform: `translate(${treePan.x}px, ${treePan.y}px) scale(${treeZoom})`, transformOrigin: "top center" }}>
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