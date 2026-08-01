import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './LoginPage.css';
import pamiLogo from '../assets/pami-logo.png';
import {
    confirm,
    describeAuthError,
    isAuthConfigured,
    login,
    register,
    resendCode
} from '../auth/cognito';
import { useSession } from '../auth/SessionProvider';

// One page for all three steps rather than three routes: they share the same card, the same
// two fields, and the confirmation step always follows sign-up immediately.
const MODES = {
    SIGN_IN: 'sign-in',
    SIGN_UP: 'sign-up',
    CONFIRM: 'confirm'
};

const LoginPage = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const [code, setCode] = useState('');
    const [mode, setMode] = useState(MODES.SIGN_IN);
    const [showPassword, setShowPassword] = useState(false);
    const [error, setError] = useState('');
    const [notice, setNotice] = useState('');
    const [isBusy, setIsBusy] = useState(false);
    const navigate = useNavigate();
    const { refresh } = useSession();

    const finishSignIn = async () => {
        // The session is loaded before navigating so the dashboard does not render, discover
        // it has no session, and bounce back to this page.
        await refresh();
        navigate('/dashboard');
    };

    const handleLogin = async (e) => {
        e.preventDefault();
        setError('');
        setNotice('');

        if (!email || !password) {
            // Inline instead of a blocking alert(), which stops the page until dismissed and
            // is announced with no relationship to the fields it is about.
            setError('Please enter both your email and password.');
            return;
        }

        // With no user pool configured there is nobody to authenticate against, and the
        // backends still answer as a local development user.
        if (!isAuthConfigured) {
            await finishSignIn();
            return;
        }

        setIsBusy(true);
        try {
            if (mode === MODES.SIGN_UP) {
                const { needsConfirmation } = await register(email, password);
                if (needsConfirmation) {
                    setMode(MODES.CONFIRM);
                    setNotice(`We sent a confirmation code to ${email}.`);
                    return;
                }
                await login(email, password);
                await finishSignIn();
                return;
            }

            const { needsConfirmation } = await login(email, password);
            if (needsConfirmation) {
                setMode(MODES.CONFIRM);
                setNotice('This account still needs confirming. Enter the code we emailed you.');
                return;
            }
            await finishSignIn();
        } catch (authError) {
            setError(describeAuthError(authError));
        } finally {
            setIsBusy(false);
        }
    };

    const handleConfirm = async (e) => {
        e.preventDefault();
        setError('');
        setNotice('');

        if (!code.trim()) {
            setError('Enter the code from your email.');
            return;
        }

        setIsBusy(true);
        try {
            await confirm(email, code.trim());
            await login(email, password);
            await finishSignIn();
        } catch (authError) {
            setError(describeAuthError(authError));
        } finally {
            setIsBusy(false);
        }
    };

    const handleResend = async () => {
        setError('');
        try {
            await resendCode(email);
            setNotice(`We sent another code to ${email}.`);
        } catch (authError) {
            setError(describeAuthError(authError));
        }
    };

    return (
        <div className="login-master-container">
            <div className="login-card">
                <div className="login-form-area">
                    <div className="login-logo-container">
                        <img src={pamiLogo} alt="Pami" className="login-logo-img" />
                    </div>

                    <div className="login-header">
                        <h1>
                            {mode === MODES.SIGN_UP
                                ? 'Create your Pami account'
                                : mode === MODES.CONFIRM
                                    ? 'Confirm your email'
                                    : 'Welcome to Pami!'}
                        </h1>
                        <p>
                            {mode === MODES.SIGN_UP
                                ? 'Your projects are yours. You can share any of them with a teammate by email.'
                                : mode === MODES.CONFIRM
                                    ? `Enter the code we sent to ${email}.`
                                    : 'Welcome back! Please login to manage your projects effectively.'}
                        </p>
                    </div>

                    {mode === MODES.CONFIRM ? (
                        <form onSubmit={handleConfirm} className="login-form-fields" noValidate>
                            <div className="input-group">
                                <label htmlFor="confirm-code">Confirmation code</label>
                                <input
                                    id="confirm-code"
                                    name="code"
                                    type="text"
                                    inputMode="numeric"
                                    autoComplete="one-time-code"
                                    placeholder="123456"
                                    value={code}
                                    onChange={(e) => setCode(e.target.value)}
                                    required
                                />
                            </div>

                            {error && (
                                <p className="login-error" role="alert">
                                    {error}
                                </p>
                            )}
                            {notice && <p className="login-mode-note">{notice}</p>}

                            <button type="submit" className="login-submit-btn" disabled={isBusy}>
                                {isBusy ? 'Confirming…' : 'Confirm and sign in'}
                            </button>

                            <button type="button" className="login-secondary-action" onClick={handleResend}>
                                Send me a new code
                            </button>
                        </form>
                    ) : (
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
                                    autoComplete={
                                        mode === MODES.SIGN_UP ? 'new-password' : 'current-password'
                                    }
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

                        {notice && <p className="login-mode-note">{notice}</p>}

                        <button type="submit" className="login-submit-btn" disabled={isBusy}>
                            {isBusy
                                ? 'Please wait…'
                                : mode === MODES.SIGN_UP
                                    ? 'Create account'
                                    : 'Sign In'}
                        </button>

                        {isAuthConfigured && (
                            <button
                                type="button"
                                className="login-secondary-action"
                                onClick={() => {
                                    setMode(mode === MODES.SIGN_UP ? MODES.SIGN_IN : MODES.SIGN_UP);
                                    setError('');
                                    setNotice('');
                                }}
                            >
                                {mode === MODES.SIGN_UP
                                    ? 'I already have an account'
                                    : 'Create an account instead'}
                            </button>
                        )}
                    </form>
                    )}

                    <div className="login-footer">
                        <p className="login-footer-note">
                            {isAuthConfigured
                                ? 'Password recovery is not available yet.'
                                : 'Accounts are not configured yet, so signing in continues as a local user.'}
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
