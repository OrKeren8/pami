import axios from 'axios';

const ensureAiPrefix = (baseUrl) => {
    if (!baseUrl) return baseUrl;
    const trimmed = String(baseUrl).replace(/\/+$/, '');
    if (trimmed.endsWith('/ai')) return trimmed;
    return `${trimmed}/ai`;
};

// ����� ��� ����� ����� (Gateway) ���������, ������ ��� �������
export const projectsApi = axios.create({
    baseURL: process.env.REACT_APP_PROJECTS_API_URL,
    timeout: 8000,
});

// ����� ������ ������� �-AI �� ���
export const aiApi = axios.create({
    baseURL: ensureAiPrefix(process.env.REACT_APP_AI_API_URL),
    timeout: 12000,
});

// ����� ������ ������� ����� �� ������
export const slackApi = axios.create({
    baseURL: process.env.REACT_APP_SLACK_API_URL,
    timeout: 8000,
});

// ����� ���� ������ ����� ��� ������ ����� ���� �������� �-api �����
const api = projectsApi;
export default api;