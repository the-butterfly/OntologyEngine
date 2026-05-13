// ontology-engine-ui/src/api/client.ts
// Shared API client based on axios

import axios from 'axios';

const BASE_URL = (typeof import.meta !== 'undefined' && (import.meta as any).env?.VITE_API_BASE_URL) || '/v1';

export const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for adding auth token
apiClient.interceptors.request.use(
  (config) => {
    // Add auth token if available
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status;
    const url = error.config?.url || 'unknown';
    const method = error.config?.method?.toUpperCase() || 'GET';
    const backendError = error.response?.data?.error;
    const backendMsg = backendError?.message || error.message || 'Unknown';

    if (status === 401) {
      console.error(`[401] ${method} ${url} — Unauthorized, please login again`);
    } else if (status === 403) {
      console.error(`[403] ${method} ${url} — Forbidden`);
    } else if (status === 404) {
      console.error(`[404] ${method} ${url} — Not found`);
    } else if (status && status >= 500) {
      console.error(`[${status}] ${method} ${url} — ${backendMsg}`);
    } else if (!error.response) {
      console.error(`[NETWORK] ${method} ${url} — ${error.message}`);
    }
    return Promise.reject(error);
  }
);

export default apiClient;
