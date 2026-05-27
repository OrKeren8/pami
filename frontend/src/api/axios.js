import axios from 'axios';

// חיבור שער הגישה הראשי (Gateway) לפרויקטים, משימות ועץ קונטקסט
export const projectsApi = axios.create({
    baseURL: process.env.REACT_APP_PROJECTS_API_URL,
    timeout: 8000,
});

// חיבור ייעודי לסרוויס ה-AI של אור
export const aiApi = axios.create({
    baseURL: process.env.REACT_APP_AI_API_URL,
    timeout: 12000,
});

// חיבור ייעודי לסרוויס הסלאק של החברים
export const slackApi = axios.create({
    baseURL: process.env.REACT_APP_SLACK_API_URL,
    timeout: 8000,
});

// ברירת מחדל לגיבוי למקרה שיש קריאות ישנות בקוד שמשתמשות ב-api הכללי
const api = projectsApi;
export default api;