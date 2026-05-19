import React, { useState, useEffect } from 'react';
import './HomePage.css';
import pamiLogo from '../assets/pami-logo.png';
import api from '../api/axios';

const HomePage = () => {
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [isLoading, setIsLoading] = useState(true);
    const [activeModal, setActiveModal] = useState(null);
    const [realProjects, setRealProjects] = useState([]);

    const [emailInput, setEmailInput] = useState('');
    const [tokenInput, setTokenInput] = useState('');

    const fetchProjects = async () => {
        setIsLoading(true);
        try {
            const response = await api.get('/projects/');
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
            const response = await api.post('/projects/', {
                name: emailInput,
                goal: tokenInput || "No goal defined",
                status: "active"
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
                alert("Check if server is running at http://127.0.0.1:8001");
            }
        } finally {
            setIsLoading(false);
        }
    };

    useEffect(() => {
        fetchProjects();
    }, []);

    const getTreeStructure = () => {
        if (realProjects.length === 0) {
            return null;
        }

        return {
            name: 'PAMI Global Core',
            color: '#f06292',
            status: 'Root',
            children: realProjects.map((proj) => ({
                name: proj.name || 'Untitled Project',
                color: '#2196f3',
                status: proj.status || 'Active',
                children: []
            }))
        };
    };

    const closeModal = () => {
        setActiveModal(null);
        setEmailInput('');
        setTokenInput('');
    };

    const openModal = (type) => {
        setActiveModal(type);
    };

    const handleConnect = async (e) => {
        e.preventDefault();
        setIsLoading(true);

        try {
            if (activeModal === 'slack') {
                await api.post('/slack/test-connection');
                alert('Connected successfully to Slack!');
                closeModal();
                return;
            }

            await api.post(`/integrate/${activeModal}`, {
                email: emailInput,
                token: tokenInput
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

    const renderTree = (node) => {
        if (!node) {
            return null;
        }

        return (
            <div className="tree-branch" key={node.name}>
                <div className="tree-node-wrapper">
                    <div className="neural-node-v2" style={{ borderColor: node.color }}>
                        <div className="node-dot" style={{ backgroundColor: node.color }}></div>
                        <div className="node-content-v2">
                            <span className="node-name-v2">{node.name}</span>
                            <span className="node-status-v2">{node.status}</span>
                        </div>
                    </div>
                    {node.children && node.children.length > 0 && (
                        <div className="tree-connector-arrow"></div>
                    )}
                </div>

                {node.children && node.children.length > 0 && (
                    <div className="tree-children">
                        {node.children.map((child) => renderTree(child))}
                    </div>
                )}
            </div>
        );
    };

    return (
        <div className={`dashboard-container ${isSidebarOpen ? 'sidebar-open' : 'sidebar-closed'}`}>
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
                        <li className="logout-item" onClick={() => alert('Logging out...')}>
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
                        <p>
                            {realProjects.length > 0
                                ? `Neural network active with ${realProjects.length} nodes.`
                                : "System ready. Initialize your first node."}
                        </p>
                    </div>

                    <div className="bot-input-area">
                        <input type="text" placeholder="Ask PAMI anything..." />
                        <button className="send-btn">➔</button>
                    </div>
                </div>
            </aside>

            <main className="main-content">
                <header className="top-header">
                    <div className="header-left">
                        <button
                            className="menu-toggle"
                            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                        >
                            ☰
                        </button>

                        <div className="search-bar">
                            <span className="search-icon">🔍</span>
                            <input type="text" placeholder="Search the machine memory..." />
                        </div>
                    </div>

                    <div className="header-right">
                        <span className="notification">🔔</span>
                        <button
                            className="new-node-btn"
                            onClick={() => openModal('createProject')}
                        >
                            + New Node
                        </button>
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
                                <span className="pulse-icon">📈</span>
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
                                <div className="hierarchical-tree-container">
                                    {renderTree(getTreeStructure())}
                                </div>
                            ) : (
                                <div className="empty-tree-state">
                                    <p>No active nodes found on server.</p>
                                    <button
                                        className="create-first-btn"
                                        onClick={() => openModal('createProject')}
                                    >
                                        + Create First Project
                                    </button>
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </main>

            <aside
                className="integrations-fixed-container"
                style={{ position: 'fixed', right: '30px', top: '200px', zIndex: 9999 }}
            >
                <div
                    className="integrations-stack"
                    style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}
                >
                    <button
                        type="button"
                        className="integration-icon-btn slack-btn"
                        onClick={() => openModal('slack')}
                        style={{
                            cursor: 'pointer',
                            background: 'white',
                            border: '1px solid #eee',
                            borderRadius: '18px',
                            width: '70px',
                            height: '70px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
                        }}
                    >
                        <img
                            src="https://a.slack-edge.com/80588/marketing/img/icons/icon_slack_hash_colored.png"
                            alt="Slack"
                            style={{ width: '40px' }}
                        />
                    </button>

                    <button
                        type="button"
                        className="integration-icon-btn jira-btn"
                        onClick={() => openModal('jira')}
                        style={{
                            cursor: 'pointer',
                            background: 'white',
                            border: '1px solid #eee',
                            borderRadius: '18px',
                            width: '70px',
                            height: '70px',
                            display: 'flex',
                            alignItems: 'center',
                            justifyContent: 'center',
                            boxShadow: '0 4px 12px rgba(0,0,0,0.1)'
                        }}
                    >
                        <img
                            src="https://cdn.worldvectorlogo.com/logos/jira-1.svg"
                            alt="Jira"
                            style={{ width: '40px' }}
                        />
                    </button>
                </div>
            </aside>

            {activeModal && (
                <div
                    className="modal-overlay"
                    onClick={closeModal}
                    style={{
                        position: 'fixed',
                        top: 0,
                        left: 0,
                        width: '100%',
                        height: '100%',
                        background: 'rgba(0,0,0,0.5)',
                        display: 'flex',
                        justifyContent: 'center',
                        alignItems: 'center',
                        zIndex: 10000
                    }}
                >
                    <div
                        className="modal-content"
                        onClick={(e) => e.stopPropagation()}
                        style={{
                            background: 'white',
                            padding: '40px',
                            borderRadius: '30px',
                            width: '400px',
                            position: 'relative'
                        }}
                    >
                        <button
                            className="close-modal-btn"
                            onClick={closeModal}
                            style={{
                                position: 'absolute',
                                top: '20px',
                                right: '20px',
                                border: 'none',
                                background: 'none',
                                fontSize: '24px',
                                cursor: 'pointer'
                            }}
                        >
                            &times;
                        </button>

                        <div className="modal-header" style={{ textAlign: 'center', marginBottom: '20px' }}>
                            {activeModal === 'createProject' ? (
                                <>
                                    <span style={{ fontSize: '40px' }}>📁</span>
                                    <h2>Initialize New Node</h2>
                                </>
                            ) : (
                                <>
                                    <img
                                        src={
                                            activeModal === 'slack'
                                                ? "https://a.slack-edge.com/80588/marketing/img/icons/icon_slack_hash_colored.png"
                                                : "https://cdn.worldvectorlogo.com/logos/jira-1.svg"
                                        }
                                        alt={activeModal}
                                        style={{ height: '50px', marginBottom: '10px' }}
                                    />
                                    <h2>Connect to {activeModal === 'slack' ? 'Slack' : 'Jira'}</h2>
                                </>
                            )}
                        </div>

                        <form
                            className="modal-form"
                            onSubmit={activeModal === 'createProject' ? handleCreateProject : handleConnect}
                        >
                            <div className="input-group" style={{ marginBottom: '15px' }}>
                                <label style={{ display: 'block', marginBottom: '5px' }}>
                                    {activeModal === 'createProject' ? 'Project Name' : 'Workspace Email'}
                                </label>
                                <input
                                    type={activeModal === 'createProject' ? 'text' : 'email'}
                                    placeholder={activeModal === 'createProject' ? "e.g. Neural Alpha" : "name@company.com"}
                                    required
                                    value={emailInput}
                                    onChange={(e) => setEmailInput(e.target.value)}
                                    style={{
                                        width: '100%',
                                        padding: '10px',
                                        borderRadius: '8px',
                                        border: '1px solid #ddd'
                                    }}
                                />
                            </div>

                            <div className="input-group" style={{ marginBottom: '20px' }}>
                                <label style={{ display: 'block', marginBottom: '5px' }}>
                                    {activeModal === 'createProject' ? 'Description (Optional)' : 'Password / API Token'}
                                </label>
                                <input
                                    type={activeModal === 'createProject' ? 'text' : 'password'}
                                    placeholder={activeModal === 'createProject' ? "Project goals..." : "••••••••"}
                                    value={tokenInput}
                                    onChange={(e) => setTokenInput(e.target.value)}
                                    style={{
                                        width: '100%',
                                        padding: '10px',
                                        borderRadius: '8px',
                                        border: '1px solid #ddd'
                                    }}
                                />
                            </div>

                            <button
                                type="submit"
                                className="login-submit-btn"
                                disabled={isLoading}
                                style={{
                                    width: '100%',
                                    padding: '12px',
                                    background: '#f06292',
                                    color: 'white',
                                    border: 'none',
                                    borderRadius: '12px',
                                    fontWeight: 'bold',
                                    cursor: isLoading ? 'not-allowed' : 'pointer',
                                    opacity: isLoading ? 0.7 : 1
                                }}
                            >
                                {isLoading
                                    ? 'Processing...'
                                    : (activeModal === 'createProject' ? 'Deploy Node' : 'Connect Account')}
                            </button>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};

export default HomePage;