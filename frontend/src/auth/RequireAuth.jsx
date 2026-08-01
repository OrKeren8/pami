import React from 'react';
import { Navigate, useLocation } from 'react-router-dom';

import { isAuthConfigured } from './cognito';
import { useSession } from './SessionProvider';

/**
 * Keeps signed-out users off the app pages.
 *
 * This is cosmetic, and deliberately so: anyone can call the API directly, so the real
 * enforcement is the token check on every endpoint. What this buys is that a signed-out user
 * sees the login page instead of a dashboard full of failed requests.
 */
export const RequireAuth = ({ children }) => {
    const { isAuthenticated, isLoading } = useSession();
    const location = useLocation();

    // With no user pool configured there is nobody to sign in as, and the backends still
    // answer. Guarding here would lock the app with no way in.
    if (!isAuthConfigured) return children;

    if (isLoading) {
        return (
            <div className="auth-gate">
                <span className="auth-gate-spinner" aria-hidden="true" />
                <p>Checking your session…</p>
            </div>
        );
    }

    if (!isAuthenticated) {
        return <Navigate to="/login" replace state={{ from: location.pathname }} />;
    }

    return children;
};

/** Same idea for the admin page: the server refuses it regardless of what is rendered. */
export const RequireAdmin = ({ children }) => {
    const { isAdmin, isLoading, isAuthenticated } = useSession();

    if (isLoading) {
        return (
            <div className="auth-gate">
                <span className="auth-gate-spinner" aria-hidden="true" />
                <p>Checking your session…</p>
            </div>
        );
    }

    if (!isAuthenticated && isAuthConfigured) return <Navigate to="/login" replace />;
    if (!isAdmin) return <Navigate to="/dashboard" replace />;

    return children;
};

export default RequireAuth;
