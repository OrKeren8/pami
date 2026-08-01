import axios from 'axios';

import { getIdToken } from '../auth/cognito';

const ensureAiPrefix = (baseUrl) => {
    if (!baseUrl) return baseUrl;
    const trimmed = String(baseUrl).replace(/\/+$/, '');
    if (trimmed.endsWith('/ai')) return trimmed;
    return `${trimmed}/ai`;
};

//                       (Gateway)          ,                   
export const projectsApi = axios.create({
    baseURL: process.env.REACT_APP_PROJECTS_API_URL,
    timeout: 8000,
});

//                       -AI       
export const aiApi = axios.create({
    baseURL: ensureAiPrefix(process.env.REACT_APP_AI_API_URL),
    timeout: 12000,
});

//                                     
export const slackApi = axios.create({
    baseURL: process.env.REACT_APP_SLACK_API_URL,
    timeout: 8000,
});

export const jiraApi = axios.create({
    baseURL: process.env.REACT_APP_JIRA_API_URL,
    timeout: 8000,
});

//                                                         -api      
const api = projectsApi;
export default api;

// Attached to every request rather than passed per call: a single missed call site would be
// an endpoint that silently acts as nobody, which is exactly what this replaces.
const attachIdToken = async (config) => {
    const token = await getIdToken();
    if (token) {
        config.headers = config.headers || {};
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
};

[projectsApi, aiApi, slackApi].forEach((client) => {
    client.interceptors.request.use(attachIdToken);
});
