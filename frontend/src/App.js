import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
// Simplified paths
import LoginPage from './pages/LoginPage';
import HomePage from './pages/HomePage';
import SlackConsolePage from './pages/SlackConsolePage';
import ChatViewPage from './pages/ChatViewPage';
import ToastProvider from './components/feedback/ToastProvider';

function App() {
    return (
        <ToastProvider>
        <BrowserRouter>
            <Routes>
                {/* Redirecting to login by default */}
                <Route path="/" element={<Navigate to="/login" />} />

                <Route path="/login" element={<LoginPage />} />

                <Route path="/dashboard" element={<HomePage />} />

                <Route path="/slack" element={<SlackConsolePage />} />

                <Route path="/chats" element={<ChatViewPage />} />
            </Routes>
        </BrowserRouter>
        </ToastProvider>
    );
}

export default App;