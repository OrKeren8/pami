import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
// Simplified paths
import LoginPage from './pages/LoginPage';
import HomePage from './pages/HomePage';
import SlackConsolePage from './pages/SlackConsolePage';

function App() {
    return (
        <BrowserRouter>
            <Routes>
                {/* Redirecting to login by default */}
                <Route path="/" element={<Navigate to="/login" />} />

                <Route path="/login" element={<LoginPage />} />

                <Route path="/dashboard" element={<HomePage />} />

                <Route path="/slack" element={<SlackConsolePage />} />
            </Routes>
        </BrowserRouter>
    );
}

export default App;