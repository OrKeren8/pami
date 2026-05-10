import axios from 'axios';

const api = axios.create({
    baseURL: 'http://34.204.77.90:8000',
    timeout: 5000,
});

export default api;