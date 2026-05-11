import axios from 'axios';

const api = axios.create({
    baseURL: 'http://35.174.137.69:8000',
    timeout: 5000,
});

export default api;