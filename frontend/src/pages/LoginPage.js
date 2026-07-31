import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './LoginPage.css';
import pamiLogo from '../assets/pami-logo.png';

const LoginPage = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState('');
    const navigate = useNavigate();

    const handleLogin = (e) => {
        e.preventDefault();

        if (!email || !password) {
            // Inline instead of a blocking alert(), which stops the page until dismissed and
            // is announced with no relationship to the fields it is about.
            setError('Please enter both your email and password.');
            return;
        }

        setError('');
        navigate('/dashboard');
    };

    return (
        <div className="login-master-container">
            <div className="login-card">
                <div className="login-form-area">
                    <div className="login-logo-container">
                        <img src={pamiLogo} alt="Pami" className="login-logo-img" />
                    </div>

                    <div className="login-header">
                        <h1>Welcome to Pami!</h1>
                        <p>Welcome back! Please login to create your company, and manage projects effectively.</p>
                    </div>

                    <form onSubmit={handleLogin} className="login-form-fields" noValidate>
                        <div className="input-group">
                            <label htmlFor="login-email">Company Email</label>
                            <input
                                id="login-email"
                                name="email"
                                type="email"
                                autoComplete="email"
                                placeholder="name@company.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                aria-invalid={Boolean(error) && !email}
                                required
                            />
                        </div>

                        <div className="input-group">
                            <label htmlFor="login-password">Password</label>
                            <div className="password-wrapper">
                                <input
                                    id="login-password"
                                    name="password"
                                    type={showPassword ? 'text' : 'password'}
                                    autoComplete="current-password"
                                    placeholder="••••••••"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    aria-invalid={Boolean(error) && !password}
                                    required
                                />
                                {/* Was a decorative emoji span that did nothing when clicked. */}
                                <button
                                    type="button"
                                    className="password-toggle"
                                    onClick={() => setShowPassword((shown) => !shown)}
                                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                                    aria-pressed={showPassword}
                                >
                                    <svg viewBox="0 0 20 20" aria-hidden="true" focusable="false">
                                        <path
                                            d="M2 10s3-5 8-5 8 5 8 5-3 5-8 5-8-5-8-5Z"
                                            fill="none"
                                            stroke="currentColor"
                                            strokeWidth="1.5"
                                            strokeLinecap="round"
                                        />
                                        <circle cx="10" cy="10" r="2.2" fill="none" stroke="currentColor" strokeWidth="1.5" />
                                        {showPassword && (
                                            <path d="M4 16 16 4" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
                                        )}
                                    </svg>
                                </button>
                            </div>
                        </div>

                        {error && (
                            <p className="login-error" role="alert">
                                {error}
                            </p>
                        )}

                        <button type="submit" className="login-submit-btn">
                            Sign In
                        </button>
                    </form>

                    {/* "Forgot Password?" and "Sign Up" were <a href="#"> that jumped to the top
                        of the page. Neither flow exists, so they are stated as unavailable
                        rather than pretending to be links. */}
                    <div className="login-footer">
                        <p className="login-footer-note">
                            Password recovery and self-service sign-up are not available yet.
                        </p>
                    </div>
                </div>

                <div className="little-bot-tip">
                    <div className="tip-avatar" aria-hidden="true">
                        <img src="/pami-assistant.png" alt="" />
                    </div>
                    <div className="tip-bubble">
                        <p>Ready to jump back into managing your projects? Let's get you connected!</p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default LoginPage;
