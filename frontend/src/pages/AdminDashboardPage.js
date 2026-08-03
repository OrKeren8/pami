import React, { useCallback, useEffect, useState } from 'react';

import { projectsApi } from '../api/axios';
import { useToast } from '../components/feedback/ToastProvider';
import AppSidebar from '../components/layout/AppSidebar';
import './HomePage.css';
import './AdminDashboardPage.css';

const formatDate = (iso) => {
    if (!iso) return '—';
    const date = new Date(iso.endsWith('Z') || iso.includes('+') ? iso : `${iso}Z`);
    return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
};

function AdminDashboardPage() {
    const toast = useToast();
    const [overview, setOverview] = useState(null);
    const [error, setError] = useState(null);
    const [isLoading, setIsLoading] = useState(true);
    // Keyed by project id: two orphans on screen must not share one input.
    const [adoptEmail, setAdoptEmail] = useState({});
    const [adopting, setAdopting] = useState(null);

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

    const adopt = async (project) => {
        const email = (adoptEmail[project.id] || '').trim();
        if (!email) return;

        setAdopting(project.id);
        try {
            const response = await projectsApi.post(
                `/admin/projects/${project.id}/owner`,
                { email }
            );
            toast.success(response.data?.message || `${project.name} has an owner now.`);
            setAdoptEmail((current) => ({ ...current, [project.id]: '' }));
            await load();
        } catch (adoptError) {
            console.error('Could not assign an owner:', adoptError);
            const detail = adoptError?.response?.data?.detail;
            toast.error(
                typeof detail === 'string' ? detail : 'Could not assign that owner.'
            );
        } finally {
            setAdopting(null);
        }
    };

    const body = () => {
        if (isLoading) {
            return (
                <div className="ds-state">
                    <span className="ds-spinner" aria-hidden="true" />
                    <p>Loading users...</p>
                </div>
            );
        }

        if (error) {
            return (
                <div className="ds-state">
                    <p>{error}</p>
                    <button type="button" className="ds-btn ds-btn-primary ds-btn-sm" onClick={load}>
                        Try again
                    </button>
                </div>
            );
        }

        if (!overview?.users?.length) {
            return (
                <div className="ds-state">
                    <p>No users have signed in yet.</p>
                </div>
            );
        }

        return (
            <>
                {/* Data nobody can reach. Sharing needs an owner, so an ownerless project
                    cannot be rescued from any user screen - only from here. */}
                {(overview.unowned || []).length > 0 && (
                    <section className="admin-unowned">
                        <span className="ds-section-label">
                            {overview.unowned.length} project
                            {overview.unowned.length === 1 ? '' : 's'} with no owner
                        </span>
                        <p className="ds-hint">
                            Nobody can see these. Give one to whoever should have it - they
                            need to have signed in at least once.
                        </p>
                        <ul className="ds-list">
                            {overview.unowned.map((project) => (
                                <li key={project.id} className="admin-unowned-row">
                                    <span className="admin-unowned-name">{project.name}</span>
                                    <span className="ds-hint">{formatDate(project.created_at)}</span>
                                    <input
                                        className="ds-input"
                                        type="email"
                                        placeholder="owner@example.com"
                                        aria-label={`New owner for ${project.name}`}
                                        value={adoptEmail[project.id] || ''}
                                        onChange={(event) =>
                                            setAdoptEmail((current) => ({
                                                ...current,
                                                [project.id]: event.target.value
                                            }))
                                        }
                                    />
                                    <button
                                        type="button"
                                        className="ds-btn ds-btn-primary ds-btn-sm"
                                        onClick={() => adopt(project)}
                                        disabled={
                                            adopting === project.id ||
                                            !(adoptEmail[project.id] || '').trim()
                                        }
                                    >
                                        {adopting === project.id ? 'Assigning…' : 'Assign owner'}
                                    </button>
                                </li>
                            ))}
                        </ul>
                    </section>
                )}

                <div className="ds-table-scroll">
                <table className="ds-table">
                    <thead>
                        <tr>
                            <th scope="col">Email</th>
                            <th scope="col">Joined</th>
                            <th scope="col">Last seen</th>
                            <th scope="col" className="ds-num">Sign-ins</th>
                            <th scope="col" className="ds-num">Owns</th>
                            <th scope="col" className="ds-num">Shared with them</th>
                        </tr>
                    </thead>
                    <tbody>
                        {overview.users.map((user) => (
                            <tr key={user.user_id}>
                                <td>{user.email}</td>
                                <td>{formatDate(user.created_at)}</td>
                                <td>{formatDate(user.last_seen_at)}</td>
                                <td className="ds-num">{user.sign_in_count}</td>
                                <td className="ds-num">{user.projects_owned}</td>
                                <td className="ds-num">{user.projects_shared}</td>
                            </tr>
                        ))}
                    </tbody>
                    </table>
                </div>
            </>
        );
    };

    return (
        <div className="dashboard-container admin-page">
            <AppSidebar
                active="admin"
            />

            <main className="admin-main">
                <header className="admin-header ds-header-rule">
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
                        <div className="ds-inline">
                            <div className="ds-stat">
                                <strong>{overview.total_users}</strong>
                                <span>Users</span>
                            </div>
                            <div className="ds-stat">
                                <strong>{overview.total_projects}</strong>
                                <span>Projects</span>
                            </div>
                            {/* Projects with no owner are visible to nobody. Surfaced so a
                                half-finished migration looks like what it is. */}
                            {overview.orphaned_projects > 0 && (
                                <div className="ds-stat ds-stat-warn">
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
