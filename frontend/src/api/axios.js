import axios from "axios";

const projectsApi = axios.create({
  baseURL: process.env.REACT_APP_PROJECTS_API_BASE_URL,
  timeout: 5000,
});

const slackApi = axios.create({
  baseURL: process.env.REACT_APP_SLACK_API_BASE_URL,
  timeout: 5000,
});

export { projectsApi, slackApi };

export default projectsApi;
