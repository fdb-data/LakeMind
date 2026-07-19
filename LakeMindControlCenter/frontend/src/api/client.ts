import axios from 'axios';

const baseURL = import.meta.env.VITE_BFF_URL || '/api';

export const api = axios.create({ baseURL, withCredentials: true });

let csrfToken: string | null = null;

api.interceptors.request.use((config) => {
  if (csrfToken && ['post', 'put', 'patch', 'delete'].includes(config.method || '')) {
    config.headers['X-CSRF-Token'] = csrfToken;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      csrfToken = null;
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

export async function login(username: string, password: string) {
  const resp = await api.post('/auth/login', { username, password });
  csrfToken = resp.data.csrf_token || null;
  return resp;
}

export async function logout() {
  try {
    await api.post('/auth/logout');
  } finally {
    csrfToken = null;
  }
}

export async function restoreCsrf() {
  try {
    const resp = await api.get('/auth/csrf');
    csrfToken = resp.headers['x-csrf-token'] || null;
  } catch {
    csrfToken = null;
  }
}

export async function getMe() {
  return api.get('/auth/me');
}
