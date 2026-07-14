import axios from 'axios';

const baseURL = import.meta.env.VITE_BFF_URL || '/api';

export const api = axios.create({ baseURL, withCredentials: true });

export async function login(username: string, password: string) {
  return api.post('/auth/login', { username, password });
}

export async function logout() {
  return api.post('/auth/logout');
}
