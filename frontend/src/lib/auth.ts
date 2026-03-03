import { api, getToken, clearToken } from './api';
import type { User } from '@/types';

export async function login(email: string, password: string): Promise<User> {
  const response = await api.auth.login(email, password);
  return response.user;
}

export function logout(): void {
  api.auth.logout();
}

export function isAuthenticated(): boolean {
  return !!getToken();
}

export async function getCurrentUser(): Promise<User | null> {
  if (!isAuthenticated()) {
    return null;
  }

  try {
    return await api.auth.me();
  } catch {
    clearToken();
    return null;
  }
}

export function hasRole(user: User | null, ...roles: string[]): boolean {
  if (!user) return false;
  return roles.includes(user.role);
}

export function isAdmin(user: User | null): boolean {
  return hasRole(user, 'admin');
}

export function isSMM(user: User | null): boolean {
  return hasRole(user, 'admin', 'smm');
}
