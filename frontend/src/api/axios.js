import axios from "axios";

// Projects API (gateway)
export const projectsApi = axios.create({
    baseURL: process.env.REACT_APP_PROJECTS_API_BASE_URL || "http://localhost:8000",
    timeout: 8000,
});

// Slack API
export const slackApi = axios.create({
    baseURL: process.env.REACT_APP_SLACK_API_BASE_URL || "http://localhost:8000/slack",
    timeout: 8000,
});

// AI API: prefer explicit AI URL, fallback to projects base + /ai
export const aiApi = axios.create({
    baseURL:
        process.env.REACT_APP_AI_API_URL ||
        (process.env.REACT_APP_PROJECTS_API_BASE_URL
            ? `${process.env.REACT_APP_PROJECTS_API_BASE_URL}/ai`
            : "http://localhost:8001/ai"),
    timeout: 30000,
});

const api = projectsApi;
export default api;