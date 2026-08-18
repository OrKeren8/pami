import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { useSession } from '../../auth/SessionProvider';

import pamiLogo from '../../assets/pami-logo.png';

const ASSISTANT_IMAGE = '/pami-assistant.png';
const SLACK_LOGO = 'https://a.slack-edge.com/80588/marketing/img/icons/icon_slack_hash_colored.png';
const JIRA_LOGO = 'https://cdn.worldvectorlogo.com/logos/jira-1.svg';

// Illustrative only: nothing here reads the user's project. Shown behind a "Sample" badge and
// a disclaimer rather than as live output, because the panel used to claim "12 tasks may miss
// due dates" for a project with no tasks at all - and the three cards contradicted each other.
const RECOMMENDATIONS = [
    {
        title: 'Recommendation 1',
        summary:
            'Several project tasks are moving slower than expected. Review blockers and ownership to keep the timeline stable.',
        bullets: ['12 tasks may miss due dates.', '3 blockers need approval.', 'Reassign 2 developers.']
    },
    {
        title: 'Recommendation 2',
        summary: 'Jira sync looks healthy, but some tasks are missing ownership details.',
        bullets: ['5 tasks have no owner.', '2 tasks miss priority.', '1 task has no context node.']
    },
    {
        title: 'Recommendation 3',
        summary: 'Everything looks stable right now. No critical project changes are required.',
        bullets: ['No overdue tasks.', 'All blockers resolved.', 'Team load is balanced.']
    }
];

const LogoutIcon = () => (
    <svg className="sidebar-nav-icon" viewBox="0 0 16 16" aria-hidden="true" focusable="false">
        <path
            d="M6.5 2.5h-3a1 1 0 0 0-1 1v9a1 1 0 0 0 1 1h3M10 5l3 3-3 3M13 8H6"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.4"
            strokeLinecap="round"
            strokeLinejoin="round"
        />
    </svg>
);

// Shared by the dashboard and the Slack console so the console is navigable rather than a
// dead end. `active` is the id of the current page. Jira now has a full window of its own, so
// every page navigates there rather than one of them opening a modal in place.
function AppSidebar({ active }) {
    const navigate = useNavigate();
    // From the server, not from decoding the token here: the client must not be the one
    // deciding it is an admin. This only draws or hides a link - /admin/users refuses anyone
    // else regardless of what is rendered.
    const { isAdmin, email, signOut } = useSession();
    const [index, setIndex] = useState(0);
    const recommendation = RECOMMENDATIONS[index];
    // One shipped image. The upload was the only writer of the stored override, so with it
    // gone a stored value could only be a leftover from before.
    const avatar = ASSISTANT_IMAGE;

    const items = [
        { id: 'dashboard', label: 'Neural Dashboard', onClick: () => navigate('/dashboard') },
        { id: 'chats', label: 'Chat View', onClick: () => navigate('/chats') },
        { id: 'slack', label: 'Slack', icon: SLACK_LOGO, onClick: () => navigate('/slack') },
        { id: 'jira', label: 'Jira', icon: JIRA_LOGO, onClick: () => navigate('/jira') },
        { id: 'settings', label: 'Settings', disabled: true }
    ];

    if (isAdmin) {
        items.push({
            id: 'admin',
            label: 'Admin',
            onClick: () => navigate('/admin')
        });
    }

    return (
        <aside className="sidebar">
            <div className="sidebar-logo">
                <img src={pamiLogo} alt="Pami Logo" className="logo-img" />
            </div>

            <nav className="sidebar-nav" aria-label="Main">
                <ul>
                    {items.map((item) => (
                        <li
                            key={item.id}
                            className={`${item.id === active ? 'active' : ''} ${
                                item.disabled ? 'nav-item-unbuilt' : ''
                            }`}
                        >
                            <button
                                type="button"
                                className="sidebar-nav-btn"
                                onClick={item.onClick}
                                disabled={item.disabled}
                                aria-current={item.id === active ? 'page' : undefined}
                                title={item.disabled ? `${item.label} is not built yet` : undefined}
                            >
                                {item.icon && (
                                    <img
                                        src={item.icon}
                                        alt=""
                                        aria-hidden="true"
                                        className="sidebar-nav-logo"
                                    />
                                )}
                                {item.label}
                                {item.disabled && <span className="nav-soon-tag">Soon</span>}
                            </button>
                        </li>
                    ))}

                    <li className="logout-item">
                        <button
                            type="button"
                            className="sidebar-nav-btn sidebar-logout-btn"
                            onClick={async () => {
                                await signOut();
                                navigate('/login');
                            }}
                            title={email ? `Signed in as ${email}` : undefined}
                        >
                            <LogoutIcon />
                            Log Out
                        </button>
                    </li>
                </ul>
            </nav>

            <div className="pami-sidebar-assistant-panel">
                <div className="pami-assistant-panel-header">
                    <div className="pami-assistant-panel-title">
                        <span className="pami-assistant-spark" aria-hidden="true" />
                        <span>PAMI Assistant</span>
                    </div>
                    <span className="pami-assistant-sample">Sample</span>
                </div>

                <div className="pami-assistant-bubble">
                    <div className="pami-assistant-bubble-top">
                        <div className="pami-assistant-recommendation-title">
                            <span className="pami-assistant-mini-spark" aria-hidden="true" />
                            <span>{recommendation.title}</span>
                        </div>

                        <div className="pami-assistant-pager">
                            <button
                                type="button"
                                className="pami-assistant-page-btn"
                                onClick={() =>
                                    setIndex((current) =>
                                        current === 0 ? RECOMMENDATIONS.length - 1 : current - 1
                                    )
                                }
                                aria-label="Previous PAMI recommendation"
                            >
                                ‹
                            </button>
                            <span>
                                {index + 1} / {RECOMMENDATIONS.length}
                            </span>
                            <button
                                type="button"
                                className="pami-assistant-page-btn"
                                onClick={() =>
                                    setIndex((current) =>
                                        current === RECOMMENDATIONS.length - 1 ? 0 : current + 1
                                    )
                                }
                                aria-label="Next PAMI recommendation"
                            >
                                ›
                            </button>
                        </div>
                    </div>

                    <div className="pami-assistant-message">
                        <p>{recommendation.summary}</p>
                        <ul>
                            {recommendation.bullets.map((bullet) => (
                                <li key={bullet}>{bullet}</li>
                            ))}
                        </ul>
                        <p className="pami-assistant-disclaimer">
                            Example of what PAMI will report. The numbers are not from your
                            project.
                        </p>
                    </div>
                </div>

                <div className="pami-assistant-robot-wrap">
                    <img src={avatar} alt="PAMI assistant avatar" className="pami-assistant-avatar-image" />
                </div>

            </div>
        </aside>
    );
}

export default AppSidebar;
