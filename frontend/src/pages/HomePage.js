import React, { useState, useEffect } from 'react';
import './HomePage.css';
import pamiLogo from '../assets/pami-logo.png';

const HomePage = () => {
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        const timer = setTimeout(() => {
            setIsLoading(false);
        }, 4000);
        return () => clearTimeout(timer);
    }, []);

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
                        <p>Hello! How can I assist you today?</p>
                    </div>
                    <div className="bot-input-area">
                        <input type="text" placeholder="Type a message..." />
                        <button className="send-btn">➔</button>
                    </div>
                </div>
            </aside>

            <main className="main-content">
                <header className="top-header">
                    <div className="header-left">
                        <button className="menu-toggle" onClick={() => setIsSidebarOpen(!isSidebarOpen)}>
                            ☰
                        </button>
                        <div className="search-bar">
                            <span className="search-icon">🔍</span>
                            <input type="text" placeholder="Search the machine memory..." />
                        </div>
                    </div>
                    <div className="header-right">
                        <span className="notification">🔔</span>
                        <button className="new-node-btn">+ New Node</button>
                    </div>
                </header>

                <div className="stats-container">
                    <div className="stat-box">
                        <div className="stat-icon pink-bg">💼</div>
                        <div className="stat-details">
                            <span className="stat-number">-</span>
                            <span className="stat-label">TOTAL PROJECTS</span>
                        </div>
                        <span className="stat-badge pink-light">+1 Month</span>
                    </div>

                    <div className="stat-box">
                        <div className="stat-icon purple-bg">👥</div>
                        <div className="stat-details">
                            <span className="stat-number">-</span>
                            <span className="stat-label">ACTIVE WORKERS</span>
                        </div>
                        <span className="stat-badge purple-light">Across Depts</span>
                    </div>

                    <div className="stat-box">
                        <div className="stat-icon green-bg">📈</div>
                        <div className="stat-details">
                            <span className="stat-number">-%</span>
                            <span className="stat-label">TASK VELOCITY</span>
                        </div>
                        <span className="stat-badge green-light">On Track</span>
                    </div>

                    <div className="stat-box">
                        <div className="stat-icon blue-bg">⚙️</div>
                        <div className="stat-details">
                            <span className="stat-number">-%</span>
                            <span className="stat-label">AI UPTIME</span>
                        </div>
                        <span className="stat-badge blue-light">Stable</span>
                    </div>
                </div>

                <div className="dashboard-grid">
                    <div className="project-tree-container">
                        <div className="project-tree-header">
                            <div className="tree-title-group">
                                <span className="pulse-icon">📈</span>
                                <h2>Project Tree</h2>
                            </div>
                            <span className="node-count">0 Nodes Connected</span>
                        </div>

                        <div className="project-tree-canvas">
                            {isLoading ? (
                                <div className="empty-tree-state">
                                    <div className="loading-spinner"></div>
                                    <p>Initializing Neural Workspace...</p>
                                </div>
                            ) : (
                                <div className="empty-tree-state no-projects">
                                    <div className="empty-icon">📂</div>
                                    <p>No Active Projects Found</p>
                                    <button className="create-first-btn">+ Create First Project</button>
                                </div>
                            )}
                        </div>
                    </div>

                    
                    <aside className="integrations-sidebar">
                        <div className="integrations-stack">
                            
                            <button className="integration-icon-btn slack-btn">
                                <img
                                    src="https://a.slack-edge.com/80588/marketing/img/icons/icon_slack_hash_colored.png"
                                    alt="Slack"
                                />
                            </button>

                            
                            <button className="integration-icon-btn jira-btn">
                                <img
                                    src="https://cdn.worldvectorlogo.com/logos/jira-1.svg"
                                    alt="Jira"
                                />
                            </button>
                        </div>
                    </aside>
                </div>
            </main>
        </div>
    );
};

export default HomePage;