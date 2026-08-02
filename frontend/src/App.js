import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
// Simplified paths
import LoginPage from './pages/LoginPage';
import HomePage from './pages/HomePage';
import SlackConsolePage from './pages/SlackConsolePage';
import ChatViewPage from './pages/ChatViewPage';
import ToastProvider from './components/feedback/ToastProvider';
import SessionProvider from './auth/SessionProvider';
import RequireAuth, { RequireAdmin } from './auth/RequireAuth';
import AdminDashboardPage from './pages/AdminDashboardPage';
import JiraConsolePage from './pages/JiraConsolePage';

function App() {
    return (
        <ToastProvider>
        <BrowserRouter>
        <SessionProvider>
            <Routes>
                {/* Redirecting to login by default */}
                <Route path="/" element={<Navigate to="/login" />} />

                <Route path="/login" element={<LoginPage />} />

                <Route
                    path="/dashboard"
                    element={
                        <RequireAuth>
                            <HomePage />
                        </RequireAuth>
                    }
                />

                <Route
                    path="/slack"
                    element={
                        <RequireAuth>
                            <SlackConsolePage />
                        </RequireAuth>
                    }
                />

                <Route
                    path="/jira"
                    element={
                        <RequireAuth>
                            <JiraConsolePage />
                        </RequireAuth>
                    }
                />

                <Route
                    path="/chats"
                    element={
                        <RequireAuth>
                            <ChatViewPage />
                        </RequireAuth>
                    }
                />

                <Route
                    path="/admin"
                    element={
                        <RequireAdmin>
                            <AdminDashboardPage />
                        </RequireAdmin>
                    }
                />
            </Routes>
        </SessionProvider>
        </BrowserRouter>
        </ToastProvider>
    );
}

export default App;