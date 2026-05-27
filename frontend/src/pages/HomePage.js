import React, { useState, useEffect, useRef } from "react";
import "./HomePage.css";
import pamiLogo from "../assets/pami-logo.png";
import api, { projectsApi, slackApi, aiApi } from "../api/axios";

const NodeDetailsModal = ({ selectedNode, nodeTasks, subNodes, isModalDataLoading, closeModal, fetchProjects, drawConnections }) => {
    const [isDeleting, setIsDeleting] = useState(false);
    if (!selectedNode) return null;

    const handleDelete = async () => {
        const ok = window.confirm(`Delete node "${selectedNode.name}"? This will reparent its children.`);
        if (!ok) return;
        setIsDeleting(true);
        try {
            const nodeId = selectedNode.id || selectedNode._id || (selectedNode._id && selectedNode._id.$oid) || null;
            if (!nodeId) throw new Error("Selected node has no id");

            // Determine whether selected item is a context-tree node or a top-level project
            // Context tree nodes include a `project_id` field in responses; projects do not.
            let deletePath = null;
            if (selectedNode.project_id) {
                // it's a context node
                deletePath = `/context-tree/nodes/${nodeId}`;
            } else {
                // assume it's a project
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
                <div>
                    <button onClick={handleDelete} disabled={isDeleting} style={{ background: "transparent", border: "none", cursor: isDeleting ? "not-allowed" : "pointer", fontSize: "20px" }} title="Delete node">
                        🗑️
                    </button>
                </div>
            </div>

            <div style={{ background: "#f9f9f9", padding: "15px", borderRadius: "16px", border: `2px solid ${selectedNode.color}`, maxHeight: "400px", overflowY: "auto", marginBottom: "20px" }}>
                <div style={{ marginBottom: "10px" }}>
                    <strong style={{ color: "#555", fontSize: "13px" }}>NODE IDENTIFIER:</strong>
                    <p style={{ margin: "2px 0 0 0", fontSize: "15px", fontWeight: "bold", color: "#111" }}>{selectedNode.name}</p>
                </div>

                <div style={{ marginBottom: "10px" }}>
                    <strong style={{ color: "#555", fontSize: "13px" }}>MISSION OBJECTIVE / GOAL:</strong>
                    <p style={{ margin: "2px 0 0 0", color: "#444", fontStyle: "italic", fontSize: "14px" }}>{selectedNode.goal}</p>
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
                                            🌿 {sub.name || "Sub Node"}
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

            <button type="button" onClick={closeModal} style={{ width: "100%", padding: "12px", background: selectedNode.color || "#2196f3", color: "white", border: "none", borderRadius: "12px", fontWeight: "bold", cursor: "pointer" }}>
                Close Blueprint View
            </button>
        </>
    );
};

const HomePage = () => {
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [isLoading, setIsLoading] = useState(true);
    const [activeModal, setActiveModal] = useState(null);
    const [realProjects, setRealProjects] = useState([]);

    // סטייט מורחב לנוד שנבחר - כולל המשימות ותתי-הנודים שלו מהשרת
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

    // AI Chat states
    const [chatMessages, setChatMessages] = useState([]);
    const [chatInput, setChatInput] = useState("");
    const [conversationId, setConversationId] = useState(null);
    const [isChatLoading, setIsChatLoading] = useState(false);
    const treeContainerRef = useRef(null);

    const fetchProjects = async () => {
        setIsLoading(true);
        try {
            const response = await projectsApi.get("/projects/");
            console.log("Projects fetched:", response.data);
            setRealProjects(response.data);
        } catch (error) {
            console.error("Failed to fetch projects:", error);
        } finally {
            setIsLoading(false);
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

    useEffect(() => {
        fetchProjects();
    }, []);

    // AI Chat functions
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

    const getTreeStructure = () => {
        if (realProjects.length === 0) return null;
        return {
            id: "root",
            name: "PAMI Global Core",
            color: "#f06292",
            status: "Root",
            goal: "Central orchestration engine",
            children: realProjects.map((proj) => ({
                id: proj.id || proj._id || "unknown",
                name: proj.name || "Untitled Project",
                color: "#2196f3",
                status: proj.status || "Active",
                goal: proj.goal || "No goal defined",
                children: [],
            })),
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

    const openModal = (type) => {
        if (type === "slack") {
            setActiveModal(slackConnected ? "slackActions" : "slack");
            return;
        }
        setActiveModal(type);
    };

    // פונקציה חכמה שמטפלת בלחיצה על נוד ומושכת את כל המידע המחובר אליו מהשרת
    const handleNodeClick = async (node) => {
        if (node.id === "root") return; // התעלמות בלחיצה על ה-Root

        setSelectedNode(node);
        setActiveModal("viewNodeDetails");
        setIsModalDataLoading(true);

        try {
            console.log(`Fetching live connected data for project: ${node.id}`);

            // קריאה סימולטנית לשרת למשיכת משימות ותתי-נודים (לפי ה-Swagger החדש)
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
        const response = await slackApi.get("/slack/list-channels");
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
            const response = await slackApi.post("/slack/connection-check");
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

    const handleCreateSlackChannel = async (e) => {
        e.preventDefault();
        if (!channelNameInput) {
            alert("Please enter a channel name.");
            return;
        }
        setIsLoading(true);
        try {
            const response = await slackApi.post("/slack/channels", { name: channelNameInput });
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
            const response = await slackApi.post("/slack/messages", {
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
                        style={{ borderColor: node.color, cursor: node.id === "root" ? "default" : "pointer" }}
                        onDoubleClick={() => handleNodeClick(node)}
                    >
                        <div className="node-dot" style={{ backgroundColor: node.color }}></div>
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
        // clear
        while (svg.firstChild) svg.removeChild(svg.firstChild);

        const nodes = Array.from(container.querySelectorAll('.tree-node-wrapper[data-node-id]'));
        const idToEl = {};
        nodes.forEach((el) => {
            const id = el.getAttribute('data-node-id');
            idToEl[id] = el;
        });

        nodes.forEach((el) => {
            const parentId = el.getAttribute('data-parent-id');
            if (!parentId) return; // skip root
            const parentEl = idToEl[parentId];
            if (!parentEl) return;

            // Prefer the visual `.neural-node-v2` element inside the wrapper
            const parentVisual = parentEl.querySelector('.neural-node-v2') || parentEl;
            const childVisual = el.querySelector('.neural-node-v2') || el;

            const pRect = parentVisual.getBoundingClientRect();
            const cRect = childVisual.getBoundingClientRect();
            const containerRect = container.getBoundingClientRect();

            // Coordinates relative to container
            const startX = pRect.left + pRect.width / 2 - containerRect.left;
            const startY = pRect.top + pRect.height - containerRect.top; // bottom of visual parent
            const endX = cRect.left + cRect.width / 2 - containerRect.left;
            const endY = cRect.top - containerRect.top; // top of visual child

            // ensure svg has correct coordinate system and explicit pixel sizing
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
        // draw after layout
        const t = setTimeout(drawConnections, 120);
        window.addEventListener('resize', drawConnections);
        return () => {
            clearTimeout(t);
            window.removeEventListener('resize', drawConnections);
        };
    }, [realProjects, isLoading]);

    // make nodes draggable and update connectors while moving
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
            const dx = e.clientX - startX;
            const dy = e.clientY - startY;
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
            window.removeEventListener('pointermove', onPointerMove);
            window.removeEventListener('pointerup', onPointerUp);
        };

        const nodeEls = Array.from(container.querySelectorAll('.neural-node-v2'));
        nodeEls.forEach((nodeEl) => {
            nodeEl.style.touchAction = 'none';
            const down = (e) => {
                // ignore right-click
                if (e.button && e.button !== 0) return;
                const wrapper = nodeEl.closest('.tree-node-wrapper');
                if (!wrapper) return;
                active = wrapper;
                startX = e.clientX;
                startY = e.clientY;
                origX = parseFloat(wrapper.dataset.translateX || 0) || 0;
                origY = parseFloat(wrapper.dataset.translateY || 0) || 0;
                window.addEventListener('pointermove', onPointerMove);
                window.addEventListener('pointerup', onPointerUp);
            };
            nodeEl.addEventListener('pointerdown', down);
            // store for cleanup
            nodeEl.__pami_down = down;
        });

        return () => {
            nodeEls.forEach((nodeEl) => {
                if (nodeEl.__pami_down) nodeEl.removeEventListener('pointerdown', nodeEl.__pami_down);
                delete nodeEl.__pami_down;
            });
            window.removeEventListener('pointermove', onPointerMove);
            window.removeEventListener('pointerup', onPointerUp);
        };
    }, [realProjects, isLoading]);

    const renderSlackConnectModal = () => {
        return (
            <>
                <div className="modal-header" style={{ textAlign: "center", marginBottom: "20px" }}>
                    <img src="https://a.slack-edge.com/80588/marketing/img/icons/icon_slack_hash_colored.png" alt="Slack" style={{ height: "50px", marginBottom: "10px" }} />
                    <h2>Connect to Slack</h2>
                    <p style={{ color: "#666", marginTop: "10px" }}>
                        Use the server-side Slack bot credentials to connect once, then continue to Slack actions.
                    </p>
                </div>
                <button type="button" className="login-submit-btn" disabled={isLoading} onClick={handleConnect} style={{ width: "100%", padding: "12px", background: "#4a154b", color: "white", border: "none", borderRadius: "12px", fontWeight: "bold", cursor: isLoading ? "not-allowed" : "pointer" }}>
                    {isLoading ? "Processing..." : "Connect to Slack"}
                </button>
            </>
        );
    };

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

    // Node details modal is now rendered via top-level `NodeDetailsModal` component

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
                <div className="sidebar-bot">
                    <div className="bot-header">
                        <span className="bot-avatar">🤖</span>
                        <div className="bot-info">
                            <strong>PAMI</strong>
                            <span className="status-dot"></span>
                        </div>
                    </div>
                    <div className="bot-bubble">
                        <p>{realProjects.length > 0 ? `Neural network active with ${realProjects.length} nodes.` : "System ready. Initialize your first node."}</p>
                    </div>

                    <div className="chat-messages">
                        {chatMessages.length === 0 ? (
                            <div className="chat-empty-state">
                                <p>💬 Start chatting with PAMI AI</p>
                            </div>
                        ) : (
                            chatMessages.map((msg, idx) => (
                                <div key={idx} className={`chat-message ${msg.role}`}>
                                    <div className="message-avatar">{msg.role === 'user' ? '👤' : '🤖'}</div>
                                    <div className="message-content"><p>{msg.content}</p></div>
                                </div>
                            ))
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

                    <div className="bot-input-area">
                        <input
                            type="text"
                            placeholder="Ask PAMI anything..."
                            value={chatInput}
                            onChange={(e) => setChatInput(e.target.value)}
                            onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
                            disabled={isChatLoading}
                        />
                        <button
                            className="send-btn"
                            onClick={handleSendMessage}
                            disabled={isChatLoading || !chatInput.trim()}
                        >
                            ➔
                        </button>
                    </div>
                </div>
            </aside>

            <main className="main-content">
                <header className="top-header">
                    <div className="header-left">
                        <button className="menu-toggle" onClick={() => setIsSidebarOpen(!isSidebarOpen)}>☰</button>
                        <div className="search-bar">
                            <span className="search-icon">🔍</span>
                            <input type="text" placeholder="Search the machine memory..." />
                        </div>
                    </div>
                    <div className="header-right">
                        <span className="notification">🔔</span>
                        <button className="new-node-btn" onClick={() => openModal("createProject")}>+ New Node</button>
                    </div>
                </header>

                <div className="stats-container">
                    <div className="stat-box">
                        <div className="stat-icon pink-bg">💼</div>
                        <div className="stat-details">
                            <span className="stat-number">{realProjects.length}</span>
                            <span className="stat-label">TOTAL NODES</span>
                        </div>
                    </div>
                    <div className="stat-box">
                        <div className="stat-icon purple-bg">👥</div>
                        <div className="stat-details">
                            <span className="stat-number">12</span>
                            <span className="stat-label">ACTIVE WORKERS</span>
                        </div>
                    </div>
                    <div className="stat-box">
                        <div className="stat-icon green-bg">📈</div>
                        <div className="stat-details">
                            <span className="stat-number">84%</span>
                            <span className="stat-label">TASK VELOCITY</span>
                        </div>
                    </div>
                    <div className="stat-box">
                        <div className="stat-icon blue-bg">⚙️</div>
                        <div className="stat-details">
                            <span className="stat-number">99.9%</span>
                            <span className="stat-label">AI UPTIME</span>
                        </div>
                    </div>
                </div>

                <div className="dashboard-grid">
                    <div className="project-tree-container">
                        <div className="project-tree-header">
                            <div className="tree-title-group">
                                <h2>Project Tree</h2>
                            </div>
                        </div>
                        <div className="project-tree-canvas">
                            {isLoading && realProjects.length === 0 ? (
                                <div className="empty-tree-state">
                                    <div className="loading-spinner"></div>
                                    <p>Connecting to Neural Cloud...</p>
                                </div>
                            ) : realProjects.length > 0 ? (
                                <div ref={treeContainerRef} className="hierarchical-tree-container" style={{ position: 'relative' }}>
                                    <svg className="tree-svg-overlay" style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', pointerEvents: 'none', overflow: 'visible', zIndex: 5 }} />
                                    {renderTree(getTreeStructure())}
                                </div>
                            ) : (
                                <div className="empty-tree-state">
                                    <p>No active nodes found on server.</p>
                                    <button className="create-first-btn" onClick={() => openModal("createProject")}>+ Create First Project</button>
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