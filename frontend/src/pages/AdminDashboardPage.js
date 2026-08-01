import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';

import { projectsApi } from '../api/axios';
import AppSidebar from '../components/layout/AppSidebar';
import './HomePage.css';
import './AdminDashboardPage.css';

const formatDate = (iso) => {
    if (!iso) return '—';
    const date = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`);
    return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
};

function AdminDashboardPage() {
    const navigate = useNavigate();
    const [overview, setOverview] = useState(null);
    const [error, setError] = useState(null);
    const [isLoading, setIsLoading] = useState(true);

    const load = useCallback(async () => {
        setIsLoading(true);
        setError(null);
        try {
            const response = await projectsApi.get('/admin/users');
            setOverview(response.data);
        } catch (loadError) {
            console.error('Failed to load the admin overview:', loadError);
            setError(
                loadError?.response?.status === 403
                    ? 'This page is restricted to administrators.'
                    : 'Could not load the user list.'
            );
        } finally {
            setIsLoading(false);
        }
    }, []);

    useEffect(() => {
        load();
    }, [load]);

    const body = () => {
        if (isLoading) {
            return (
                <div className="admin-state">
                    <span className="admin-spinner" aria-hidden="true" />
                    <p>Loading users...</p>
                </div>
            );
        }

        if (error) {
            return (
                <div className="admin-state">
                    <p>{error}</p>
                    <button type="button" className="admin-retry" onClick={load}>
                        Try again
                    </button>
                </div>
            );
        }

        if (!overview?.users?.length) {
            return (
                <div className="admin-state">
                    <p>No users have signed in yet.</p>
                </div>
            );
        }

        return (
            <div className="admin-table-scroll">
                <table className="admin-table">
                    <thead>
                        <tr>
                            <th scope="col">Email</th>
                            <th scope="col">Joined</th>
                            <th scope="col">Last seen</th>
                            <th scope="col">Sign-ins</th>
                            <th scope="col">Owns</th>
                            <th scope="col">Shared with them</th>
                        </tr>
                    </thead>
                    <tbody>
                        {overview.users.map((user) => (
                            <tr key={user.user_id}>
                                <td>{user.email}</td>
                                <td>{formatDate(user.created_at)}</td>
                                <td>{formatDate(user.last_seen_at)}</td>
                                <td>{user.sign_in_count}</td>
                                <td>{user.projects_owned}</td>
                                <td>{user.projects_shared}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        );
    };

    return (
        <div className="dashboard-container admin-page">
            <AppSidebar
                active="admin"
                onJira={() => navigate('/dashboard?integration=jira')}
            />

            <main className="admin-main">
                <header className="admin-header">
                    <div>
                        <span className="admin-kicker">Admin dashboard</span>
                        <h1>Everyone using PAMI</h1>
                        <p>
                            Users are recorded when they sign in, so this list comes from PAMI
                            itself rather than from Cognito - which cannot report a last
                            sign-in time or join against the projects.
                        </p>
                    </div>

                    {overview && (
                        <div className="admin-stats">
                            <div className="admin-stat">
                                <strong>{overview.total_users}</strong>
                                <span>Users</span>
                            </div>
                            <div className="admin-stat">
                                <strong>{overview.total_projects}</strong>
                                <span>Projects</span>
                            </div>
                            {/* Projects with no owner are visible to nobody. Surfaced so a
                                half-finished migration looks like what it is. */}
                            {overview.orphaned_projects > 0 && (
                                <div className="admin-stat admin-stat-warn">
                                    <strong>{overview.orphaned_projects}</strong>
                                    <span>Unowned</span>
                                </div>
                            )}
                        </div>
                    )}
                </header>

                <section className="admin-body">{body()}</section>
            </main>
        </div>
    );
}

export default AdminDashboardPage;
