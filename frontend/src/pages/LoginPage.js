import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import './LoginPage.css';
import pamiLogo from '../assets/pami-logo.png'; 

const LoginPage = () => {
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
    const navigate = useNavigate();

    const handleLogin = (e) => {
        e.preventDefault();
       
        
        if (email && password) {
            navigate('/dashboard');
        } else {
            alert('Please enter both Email and Password');
        }
    };

    return (
        <div className="login-master-container">
            <div className="login-card">

                
                

                
                <div className="login-form-area">
                    <div className="login-logo-container">
                        <img src={pamiLogo} alt="Pami Logo" className="login-logo-img" />
                    </div>

                    <div className="login-header">
                        <h1>Welcome to Pami!</h1>
                        <p>Welcome back! Please login to create your company, and manage projects effectively.</p>
                    </div>

                    <form onSubmit={handleLogin} className="login-form-fields">
                        <div className="input-group">
                            <label>Company Email</label>
                            <input
                                type="email"
                                placeholder="name@company.com"
                                value={email}
                                onChange={(e) => setEmail(e.target.value)}
                                required
                            />
                        </div>

                        <div className="input-group">
                            <label>Password</label>
                            <div className="password-wrapper">
                                <input
                                    type="password"
                                    placeholder="••••••••"
                                    value={password}
                                    onChange={(e) => setPassword(e.target.value)}
                                    required
                                />
                                <span className="password-toggle">👁️</span>
                            </div>
                        </div>

                        <div className="form-actions">
                            <a href="#" className="forgot-pass">Forgot Password?</a>
                        </div>

                        <button type="submit" className="login-submit-btn">
                            Sign In ➔
                        </button>
                    </form>

                    <div className="login-footer">
                        <p>Don't have an account? <a href="#">Sign Up</a></p>
                    </div>
                </div>

               
                <div className="little-bot-tip">
                    <div className="tip-avatar">🤖</div>
                    <div className="tip-bubble">
                        <p>Ready to jump back into managing your projects? Let's get you connected!</p>
                    </div>
                </div>
            </div>
        </div>
    );
};

export default LoginPage;