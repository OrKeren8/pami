import React, { useCallback, useEffect, useRef, useState } from "react";
import { slackApi } from "../api/axios";
import AppSidebar from "../components/layout/AppSidebar";
import "./HomePage.css";
import "./SlackConsolePage.css";

const AVATAR_COLORS = ["#4a154b", "#1264a3", "#0f9d58", "#e01e5a", "#ecb22e", "#36c5f0", "#8b3f8f"];

const colorForName = (name) => {
    const str = String(name || "?");
    let hash = 0;
    for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
    return AVATAR_COLORS[Math.abs(hash) % AVATAR_COLORS.length];
};

const initialsForName = (name) => {
    const parts = String(name || "?").trim().split(/[\s._-]+/).filter(Boolean);
    if (parts.length === 0) return "?";
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[1][0]).toUpperCase();
};

const formatMessageTime = (ts) => {
    if (!ts) return "";
    const date = new Date(parseFloat(ts) * 1000);
    return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
};

const formatMessageDay = (ts) => {
    if (!ts) return "";
    const date = new Date(parseFloat(ts) * 1000);
    const today = new Date();
    const isToday = date.toDateString() === today.toDateString();
    if (isToday) return "Today";
    return date.toLocaleDateString([], { weekday: "long", month: "short", day: "numeric" });
};

const POLL_INTERVAL_MS = 4000;

function SlackConsolePage() {
    const [connection, setConnection] = useState({ status: "checking", team: null, error: null });
    const [channels, setChannels] = useState([]);
    const [channelsLoading, setChannelsLoading] = useState(true);
    const [channelsError, setChannelsError] = useState(null);
    const [selectedChannelId, setSelectedChannelId] = useState(null);
    const [messages, setMessages] = useState([]);
    const [messagesLoading, setMessagesLoading] = useState(false);
    const [messagesError, setMessagesError] = useState(null);
    const [messageInput, setMessageInput] = useState("");
    const [isSending, setIsSending] = useState(false);
    const [search, setSearch] = useState("");
    const [isCreatingChannel, setIsCreatingChannel] = useState(false);
    const [newChannelName, setNewChannelName] = useState("");
    const [isSubmittingChannel, setIsSubmittingChannel] = useState(false);
    const [isConnecting, setIsConnecting] = useState(false);

    const pollRef = useRef(null);
    const messagesEndRef = useRef(null);

    const selectedChannel = channels.find((c) => c.id === selectedChannelId) || null;

    const loadConnection = useCallback(async () => {
        try {
            const response = await slackApi.post("/connection-check");
            if (response.data && response.data.ok) {
                setConnection({ status: "connected", team: response.data.team || null, error: null });
            } else {
                setConnection({ status: "disconnected", team: null, error: response.data ? response.data.error : "unknown_error" });
            }
        } catch (error) {
            setConnection({ status: "disconnected", team: null, error: "unreachable" });
        }
    }, []);

    const handleConnectClick = async () => {
        setIsConnecting(true);
        await loadConnection();
        setIsConnecting(false);
    };

    const loadChannels = useCallback(async ({ silent } = {}) => {
        if (!silent) setChannelsLoading(true);
        setChannelsError(null);
        try {
            const response = await slackApi.get("/list-channels");
            if (!response.data || response.data.ok !== true) {
                throw new Error(response.data && response.data.error ? response.data.error : "Failed to load channels.");
            }
            const list = response.data.channels || [];
            setChannels(list);
            setSelectedChannelId((current) => current || (list.length > 0 ? list[0].id : null));
        } catch (error) {
            setChannelsError("Couldn't load channels. Check that the Slack backend is running and configured.");
        } finally {
            if (!silent) setChannelsLoading(false);
        }
    }, []);

    const loadMessages = useCallback(async (channelId, { silent } = {}) => {
        if (!channelId) return;
        if (!silent) setMessagesLoading(true);
        setMessagesError(null);
        try {
            const response = await slackApi.get(`/channels/${channelId}/messages`);
            if (!response.data || response.data.ok !== true) {
                const reason = response.data ? response.data.error : "unknown_error";
                if (reason === "not_in_channel") {
                    setMessagesError("PAMI's Slack bot hasn't joined this channel yet. Invite it with /invite @PAMI to see the conversation here.");
                } else if (reason === "missing_scope") {
                    const needed = response.data.needed
                        ? response.data.needed.split(",")[0]
                        : "channels:history";
                    setMessagesError(
                        `The Slack app is missing the "${needed}" scope. Add it under OAuth & Permissions at api.slack.com/apps, then reinstall the app to the workspace.`
                    );
                } else {
                    setMessagesError("Couldn't load messages for this channel.");
                }
                setMessages([]);
                return;
            }
            setMessages(response.data.messages || []);
        } catch (error) {
            setMessagesError("Couldn't load messages for this channel.");
        } finally {
            if (!silent) setMessagesLoading(false);
        }
    }, []);

    useEffect(() => {
        loadConnection();
    }, [loadConnection]);

    useEffect(() => {
        if (connection.status === "connected") loadChannels();
    }, [connection.status, loadChannels]);

    useEffect(() => {
        if (connection.status !== "connected" || !selectedChannelId) return undefined;
        loadMessages(selectedChannelId);

        if (pollRef.current) clearInterval(pollRef.current);
        pollRef.current = setInterval(() => {
            loadMessages(selectedChannelId, { silent: true });
        }, POLL_INTERVAL_MS);

        return () => {
            if (pollRef.current) clearInterval(pollRef.current);
        };
    }, [connection.status, selectedChannelId, loadMessages]);

    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
    }, [messages]);

    const handleSend = async (e) => {
        e.preventDefault();
        const text = messageInput.trim();
        if (!text || !selectedChannelId || isSending) return;

        setIsSending(true);
        const optimisticMessage = {
            id: `pending-${Date.now()}`,
            user_id: null,
            user_name: "PAMI",
            text,
            ts: `${Date.now() / 1000}`,
            is_bot: true,
            pending: true,
        };
        setMessages((current) => [...current, optimisticMessage]);
        setMessageInput("");

        try {
            const response = await slackApi.post("/messages", { channel: selectedChannelId, text });
            if (!response.data || response.data.ok !== true) {
                throw new Error("send_failed");
            }
            loadMessages(selectedChannelId, { silent: true });
        } catch (error) {
            setMessages((current) => current.filter((m) => m.id !== optimisticMessage.id));
            alert("Failed to send message to Slack.");
        } finally {
            setIsSending(false);
        }
    };

    const handleCreateChannel = async (e) => {
        e.preventDefault();
        const name = newChannelName.trim();
        if (!name || isSubmittingChannel) return;

        setIsSubmittingChannel(true);
        try {
            const response = await slackApi.post("/channels", { name });
            if (!response.data || response.data.ok !== true) {
                throw new Error(response.data && response.data.error ? response.data.error : "create_failed");
            }
            setNewChannelName("");
            setIsCreatingChannel(false);
            await loadChannels({ silent: true });
            setSelectedChannelId(response.data.channel_id);
        } catch (error) {
            alert("Failed to create the channel in Slack.");
        } finally {
            setIsSubmittingChannel(false);
        }
    };

    const filteredChannels = channels.filter((c) =>
        c.name.toLowerCase().includes(search.trim().toLowerCase())
    );

    let lastRenderedDay = null;

    if (connection.status === "checking") {
        return (
            <div className="slack-console-shell">
                <AppSidebar active="slack" />
                <div className="slack-console-gate">
                    <div className="slack-console-gate-spinner" />
                </div>
            </div>
        );
    }

    if (connection.status === "disconnected") {
        return (
            <div className="slack-console-shell">
                <AppSidebar active="slack" />
                <div className="slack-console-gate">
                <div className="slack-console-login-card">
                    <div className="slack-console-login-icon">P</div>
                    <h1>Connect Slack Workspace</h1>
                    <p>
                        Connect PAMI to Slack so the console can check channels, create project channels,
                        and send operational updates directly to your workspace.
                    </p>

                    <div className="slack-console-gate-features">
                        <div className="slack-console-gate-feature">
                            <span>#</span>
                            <div>
                                <strong>Channel Management</strong>
                                <span className="slack-console-gate-feature-desc">List channels and create new Slack channels from PAMI.</span>
                            </div>
                        </div>
                        <div className="slack-console-gate-feature">
                            <span>↗</span>
                            <div>
                                <strong>Team Updates</strong>
                                <span className="slack-console-gate-feature-desc">Send messages to selected Slack channels from the dashboard.</span>
                            </div>
                        </div>
                    </div>

                    {connection.error === "unreachable" && (
                        <div className="slack-console-login-error">Could not reach the Slack service. Is it running?</div>
                    )}

                    <button type="button" onClick={handleConnectClick} disabled={isConnecting}>
                        {isConnecting ? "Connecting…" : "Connect Slack"}
                    </button>

                    <span className="slack-console-login-hint">
                        Uses the configured Slack backend service. No manual token entry is required here.
                    </span>
                </div>
                </div>
            </div>
        );
    }

    return (
        <div className="slack-console-shell">
            <AppSidebar active="slack" />
            <div className="slack-console">
            <aside className="slack-console-sidebar">
                <div className="slack-console-workspace">
                    <div className="slack-console-workspace-icon">P</div>
                    <div className="slack-console-workspace-info">
                        <div className="slack-console-workspace-name">
                            {connection.team || "Slack Workspace"}
                        </div>
                        <div className="slack-console-status slack-console-status-connected">
                            <span className="slack-console-status-dot" />
                            Connected
                        </div>
                    </div>
                </div>

                <div className="slack-console-search">
                    <span className="slack-console-search-icon">⌕</span>
                    <input
                        type="text"
                        placeholder="Search channels"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                    />
                </div>

                <div className="slack-console-channels-header">
                    <span>Channels</span>
                    <button
                        type="button"
                        className="slack-console-add-btn"
                        title="Create a channel"
                        onClick={() => setIsCreatingChannel((v) => !v)}
                    >
                        +
                    </button>
                </div>

                {isCreatingChannel && (
                    <form className="slack-console-create-form" onSubmit={handleCreateChannel}>
                        <input
                            type="text"
                            autoFocus
                            placeholder="new-channel-name"
                            value={newChannelName}
                            onChange={(e) => setNewChannelName(e.target.value)}
                        />
                        <div className="slack-console-create-actions">
                            <button type="submit" disabled={isSubmittingChannel || !newChannelName.trim()}>
                                {isSubmittingChannel ? "Creating…" : "Create"}
                            </button>
                            <button type="button" className="ghost" onClick={() => setIsCreatingChannel(false)}>
                                Cancel
                            </button>
                        </div>
                    </form>
                )}

                <div className="slack-console-channel-list">
                    {channelsLoading && (
                        <>
                            {[0, 1, 2, 3, 4].map((i) => (
                                <div key={i} className="slack-console-channel-skeleton" />
                            ))}
                        </>
                    )}

                    {!channelsLoading && channelsError && (
                        <div className="slack-console-sidebar-error">{channelsError}</div>
                    )}

                    {!channelsLoading && !channelsError && filteredChannels.length === 0 && (
                        <div className="slack-console-sidebar-empty">No channels found.</div>
                    )}

                    {!channelsLoading && filteredChannels.map((channel) => (
                        <button
                            type="button"
                            key={channel.id}
                            className={`slack-console-channel-item ${channel.id === selectedChannelId ? "active" : ""}`}
                            onClick={() => setSelectedChannelId(channel.id)}
                        >
                            <span className="slack-console-channel-hash">#</span>
                            <span className="slack-console-channel-name">{channel.name}</span>
                        </button>
                    ))}
                </div>
            </aside>

            <main className="slack-console-main">
                {selectedChannel ? (
                    <>
                        <header className="slack-console-channel-header">
                            <div className="slack-console-channel-title">
                                <span className="slack-console-channel-hash">#</span>
                                {selectedChannel.name}
                            </div>
                        </header>

                        <div className="slack-console-messages">
                            {messagesLoading && (
                                <div className="slack-console-messages-loading">
                                    {[0, 1, 2].map((i) => <div key={i} className="slack-console-message-skeleton" />)}
                                </div>
                            )}

                            {!messagesLoading && messagesError && (
                                <div className="slack-console-messages-error">
                                    <span className="slack-console-messages-error-icon">⚠</span>
                                    <p>{messagesError}</p>
                                </div>
                            )}

                            {!messagesLoading && !messagesError && messages.length === 0 && (
                                <div className="slack-console-messages-empty">
                                    <p>No messages yet in #{selectedChannel.name}.</p>
                                    <span>Say hello below to start the conversation.</span>
                                </div>
                            )}

                            {!messagesLoading && !messagesError && messages.map((message) => {
                                const day = formatMessageDay(message.ts);
                                const showDivider = day !== lastRenderedDay;
                                lastRenderedDay = day;

                                return (
                                    <React.Fragment key={message.id}>
                                        {showDivider && (
                                            <div className="slack-console-day-divider">
                                                <span>{day}</span>
                                            </div>
                                        )}
                                        <div className={`slack-console-message ${message.pending ? "pending" : ""}`}>
                                            <div
                                                className="slack-console-avatar"
                                                style={{ background: colorForName(message.user_name) }}
                                            >
                                                {initialsForName(message.user_name)}
                                            </div>
                                            <div className="slack-console-message-body">
                                                <div className="slack-console-message-meta">
                                                    <span className="slack-console-message-author">{message.user_name}</span>
                                                    <span className="slack-console-message-time">{formatMessageTime(message.ts)}</span>
                                                </div>
                                                <div className="slack-console-message-text">{message.text}</div>
                                            </div>
                                        </div>
                                    </React.Fragment>
                                );
                            })}
                            <div ref={messagesEndRef} />
                        </div>

                        <form className="slack-console-composer" onSubmit={handleSend}>
                            <input
                                type="text"
                                placeholder={`Message #${selectedChannel.name}`}
                                value={messageInput}
                                onChange={(e) => setMessageInput(e.target.value)}
                                disabled={isSending}
                            />
                            <button type="submit" disabled={isSending || !messageInput.trim()}>
                                {isSending ? "Sending…" : "Send"}
                            </button>
                        </form>
                    </>
                ) : (
                    <div className="slack-console-no-channel">
                        {channelsLoading ? "Loading channels…" : "Select a channel to start chatting."}
                    </div>
                )}
            </main>
            </div>
        </div>
    );
}

export default SlackConsolePage;
