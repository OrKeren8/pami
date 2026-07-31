import React, { createContext, useCallback, useContext, useMemo, useRef, useState } from 'react';
import './toast.css';

const ToastContext = createContext(null);

const DEFAULT_DURATION = 4200;
const ERROR_DURATION = 7000;

/**
 * Replaces window.alert for feedback that does not need an answer.
 *
 * alert() freezes the page until it is dismissed, cannot be styled, and stacks up one
 * modal per event, so a failed request mid-render left the app unusable until every
 * dialog was clicked away.
 */
export const ToastProvider = ({ children }) => {
    const [toasts, setToasts] = useState([]);
    const nextId = useRef(0);
    const timers = useRef(new Map());

    const dismiss = useCallback((id) => {
        setToasts((current) => current.filter((toast) => toast.id !== id));
        const timer = timers.current.get(id);
        if (timer) {
            clearTimeout(timer);
            timers.current.delete(id);
        }
    }, []);

    const notify = useCallback(
        (message, { tone = 'info', duration } = {}) => {
            if (!message) return null;

            const id = nextId.current++;
            setToasts((current) => [...current, { id, message: String(message), tone }]);

            const life = duration ?? (tone === 'error' ? ERROR_DURATION : DEFAULT_DURATION);
            timers.current.set(
                id,
                setTimeout(() => dismiss(id), life)
            );
            return id;
        },
        [dismiss]
    );

    const value = useMemo(
        () => ({
            notify,
            success: (message, options) => notify(message, { ...options, tone: 'success' }),
            error: (message, options) => notify(message, { ...options, tone: 'error' }),
            dismiss,
        }),
        [notify, dismiss]
    );

    return (
        <ToastContext.Provider value={value}>
            {children}
            {/* Announced politely so a background success does not interrupt whatever the
                screen reader is currently on; errors carry their own role below. */}
            <div className="toast-stack" role="region" aria-label="Notifications">
                {toasts.map((toast) => (
                    <div
                        key={toast.id}
                        className={`toast toast-${toast.tone}`}
                        role={toast.tone === 'error' ? 'alert' : 'status'}
                    >
                        <span className="toast-message">{toast.message}</span>
                        <button
                            type="button"
                            className="toast-dismiss"
                            onClick={() => dismiss(toast.id)}
                            aria-label="Dismiss notification"
                        >
                            ×
                        </button>
                    </div>
                ))}
            </div>
        </ToastContext.Provider>
    );
};

/** Falls back to a console line when used outside the provider, never to alert(). */
export const useToast = () => {
    const context = useContext(ToastContext);
    if (context) return context;

    const log = (message) => console.warn('[toast outside provider]', message);
    return { notify: log, success: log, error: log, dismiss: () => {} };
};

export default ToastProvider;
