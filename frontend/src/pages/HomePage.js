import React, { useState, useEffect } from 'react';
import './HomePage.css';
import pamiLogo from '../assets/pami-logo.png';

const HomePage = () => {
    const [isSidebarOpen, setIsSidebarOpen] = useState(true);
    const [isLoading, setIsLoading] = useState(true);
    const [activeModal, setActiveModal] = useState(null);

    // מבנה נתונים היררכי (עץ)
    const neuralTreeData = {
        name: 'PAMI Global Core',
        color: '#f06292',
        status: 'Root',
        children: [
            {
                name: 'Slack Engine',
                color: '#4caf50',
                status: 'Active',
                children: [
                    { name: 'Channel Manager', color: '#4caf50', status: 'Standby' },
                    { name: 'Bot Listener', color: '#4caf50', status: 'Active' }
                ]
            },
            {
                name: 'Jira Sync',
                color: '#2196f3',
                status: 'Syncing',
                children: [
                    { name: 'Ticket Automator', color: '#2196f3', status: 'Running' }
                ]
            },
            {
                name: 'Auth Neural',
                color: '#ff9800',
                status: 'Secure',
                children: []
            }
        ]
    };

    const closeModal = () => setActiveModal(null);
    const openModal = (type) => setActiveModal(type);

    useEffect(() => {
        const timer = setTimeout(() => {
            setIsLoading(false);
        }, 2000);
        return () => clearTimeout(timer);
    }, []);

    // פונקציה לרינדור העץ בצורה רקורסיבית
    const renderTree = (node) => (
        <div className="tree-branch" key={node.name}>
            <div className="tree-node-wrapper">
                <div className="neural-node-v2" style={{ borderColor: node.color }}>
                    <div className="node-dot" style={{ backgroundColor: node.color }}></div>
                    <div className="node-content-v2">
                        <span className="node-name-v2">{node.name}</span>
                        <span className="node-status-v2">{node.status}</span>
                    </div>
                </div>
                {/* הצגת חץ רק אם יש ילדים */}
                {node.children && node.children.length > 0 && <div className="tree-connector-arrow"></div>}
            </div>
            {node.children && node.children.length > 0 && (
                <div className="tree-children">
                    {node.children.map(child => renderTree(child))}
                </div>
            )}
        </div>
    );

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
                        <p>Hello! I've visualized your project hierarchy.</p>
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
                        <button className="menu-toggle" onClick={() => setIsSidebarOpen(!isSidebarOpen)}>☰</button>
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
                            <span className="stat-number">7</span>
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
                            <span className="node-count">Neural Hierarchy Active</span>
                        </div>

                        <div className="project-tree-canvas">
                            {isLoading ? (
                                <div className="empty-tree-state">
                                    <div className="loading-spinner"></div>
                                    <p>Initializing Neural Workspace...</p>
                                </div>
                            ) : (
                                <div className="hierarchical-tree-container">
                                    {renderTree(neuralTreeData)}
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </main>

            <aside className="integrations-fixed-container" style={{ position: 'fixed', right: '30px', top: '200px', zIndex: 9999 }}>
                <div className="integrations-stack" style={{ display: 'flex', flexDirection: 'column', gap: '15px' }}>
                    <button type="button" className="integration-icon-btn slack-btn" onClick={() => openModal('slack')} style={{ cursor: 'pointer', background: 'white', border: '1px solid #eee', borderRadius: '18px', width: '70px', height: '70px', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}>
                        <img src="https://a.slack-edge.com/80588/marketing/img/icons/icon_slack_hash_colored.png" alt="Slack" style={{ width: '40px' }} />
                    </button>
                    <button type="button" className="integration-icon-btn jira-btn" onClick={() => openModal('jira')} style={{ cursor: 'pointer', background: 'white', border: '1px solid #eee', borderRadius: '18px', width: '70px', height: '70px', display: 'flex', alignItems: 'center', justifyContent: 'center', boxShadow: '0 4px 12px rgba(0,0,0,0.1)' }}>
                        <img src="https://cdn.worldvectorlogo.com/logos/jira-1.svg" alt="Jira" style={{ width: '40px' }} />
                    </button>
                </div>
            </aside>

            {activeModal && (
                <div className="modal-overlay" onClick={closeModal} style={{ position: 'fixed', top: 0, left: 0, width: '100%', height: '100%', background: 'rgba(0,0,0,0.5)', display: 'flex', justifyContent: 'center', alignItems: 'center', zIndex: 10000 }}>
                    <div className="modal-content" onClick={e => e.stopPropagation()} style={{ background: 'white', padding: '40px', borderRadius: '30px', width: '400px', position: 'relative' }}>
                        <button className="close-modal-btn" onClick={closeModal} style={{ position: 'absolute', top: '20px', right: '20px', border: 'none', background: 'none', fontSize: '24px', cursor: 'pointer' }}>&times;</button>
                        <div className="modal-header" style={{ textAlign: 'center', marginBottom: '20px' }}>
                            <img src={activeModal === 'slack' ? "https://a.slack-edge.com/80588/marketing/img/icons/icon_slack_hash_colored.png" : "https://cdn.worldvectorlogo.com/logos/jira-1.svg"} alt={activeModal} style={{ height: '50px', marginBottom: '10px' }} />
                            <h2>Connect to {activeModal === 'slack' ? 'Slack' : 'Jira'}</h2>
                        </div>
                        <form className="modal-form" onSubmit={(e) => { e.preventDefault(); alert(`Connecting to ${activeModal}...`); closeModal(); }}>
                            <div className="input-group" style={{ marginBottom: '15px' }}>
                                <label style={{ display: 'block', marginBottom: '5px' }}>Workspace Email</label>
                                <input type="email" placeholder="name@company.com" required style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #ddd' }} />
                            </div>
                            <div className="input-group" style={{ marginBottom: '20px' }}>
                                <label style={{ display: 'block', marginBottom: '5px' }}>Password / API Token</label>
                                <input type="password" placeholder="••••••••" required style={{ width: '100%', padding: '10px', borderRadius: '8px', border: '1px solid #ddd' }} />
                            </div>
                            <button type="submit" className="login-submit-btn" style={{ width: '100%', padding: '12px', background: '#f06292', color: 'white', border: 'none', borderRadius: '12px', fontWeight: 'bold', cursor: 'pointer' }}>Connect Account</button>
                        </form>
                    </div>
                </div>
            )}
        </div>
    );
};

export default HomePage;