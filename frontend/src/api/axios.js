import axios from 'axios';


export const projectsApi = axios.create({
    baseURL: process.env.REACT_APP_PROJECTS_API_URL,
    timeout: 5000,
});


export const aiApi = axios.create({
    baseURL: process.env.REACT_APP_AI_API_URL,
    timeout: 10000, 
});


export const slackApi = axios.create({
    baseURL: process.env.REACT_APP_SLACK_API_URL,
    timeout: 5000,
});