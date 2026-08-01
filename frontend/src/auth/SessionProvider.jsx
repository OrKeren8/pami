import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import { projectsApi } from '../api/axios';
import { getSignedInUser, isAuthConfigured, logout as cognitoLogout } from './cognito';

const SessionContext = createContext(null);

/**
 * Who the current user is, according to the server.
 *
 * `isAdmin` comes from POST /session/ rather than from decoding the token here. Decoding it in
 * the browser would work, but then the client would be deciding its own permissions - and the
 * whole point of the admin gate is that it is not the client's decision. This value only
 * controls whether a nav link is drawn; the endpoints enforce it themselves.
 */
export const SessionProvider = ({ children }) => {
    const [session, setSession] = useState(null);
    const [isLoading, setIsLoading] = useState(true);

    const refresh = useCallback(async () => {
        setIsLoading(true);
        try {
            if (isAuthConfigured && !(await getSignedInUser())) {
                setSession(null);
                return null;
            }
            const response = await projectsApi.post('/session/');
            setSession(response.data);
            return response.data;
        } catch (error) {
            // With no pool configured the backend answers as the local dev user, so a failure
            // here means the service is unreachable - not that the user is signed out.
            console.error('Could not load the session:', error);
            setSession(null);
            return null;
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        refresh();
    }, [refresh]);

    const signOutEverywhere = useCallback(async () => {
        await cognitoLogout();
        setSession(null);
    }, []);

    const value = useMemo(
        () => ({
            session,
            isLoading,
            isAuthenticated: Boolean(session),
            isAdmin: Boolean(session?.is_admin),
            email: session?.email || null,
            refresh,
            signOut: signOutEverywhere
        }),
        [session, isLoading, refresh, signOutEverywhere]
    );

    return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
};

export const useSession = () => {
    const context = useContext(SessionContext);
    if (context) return context;
    // Outside the provider, report "not signed in, not admin" rather than throwing: a nav
    // component rendered in isolation should hide the admin link, not crash.
    return {
        session: null,
        isLoading: false,
        isAuthenticated: false,
        isAdmin: false,
        email: null,
        refresh: async () => null,
        signOut: async () => {}
    };
};

export default SessionProvider;
