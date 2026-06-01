import type { UserLevel } from './userLevels';
import { apiUrl } from './apiBase';

export const API_UNAUTHORIZED_EVENT = 'norn-api-unauthorized';

export type SessionInfo = {
  username: string;
  user_level: UserLevel | null;
};

export function notifyApiUnauthorized(): void {
  window.dispatchEvent(new CustomEvent(API_UNAUTHORIZED_EVENT));
}

async function authFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (init.body != null && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  return fetch(apiUrl(path), {
    ...init,
    credentials: 'include',
    headers,
  });
}

function parseUserLevel(value: unknown): UserLevel | null {
  if (value === 'junior' || value === 'mid' || value === 'senior') return value;
  return null;
}

function parseSessionBody(body: unknown): SessionInfo | null {
  if (typeof body !== 'object' || body === null) return null;
  const record = body as Record<string, unknown>;
  if (record.authenticated !== true) return null;
  if (typeof record.username !== 'string' || !record.username) return null;
  return {
    username: record.username,
    user_level: parseUserLevel(record.user_level),
  };
}

/** 有効なセッションがあればユーザー情報を返す。未ログインなら null。 */
export async function getSession(): Promise<SessionInfo | null> {
  const response = await authFetch('/auth/session', { method: 'GET' });
  if (response.status === 401) return null;
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  const body = (await response.json()) as unknown;
  return parseSessionBody(body);
}

/** 認証不要、または有効なセッションがあるとき true。ログインが必要なとき false。 */
export async function checkSession(): Promise<boolean> {
  const session = await getSession();
  return session !== null;
}

export async function login(username: string, password: string): Promise<void> {
  const response = await authFetch('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  if (response.status === 401) {
    throw new Error('ユーザー名またはパスワードが正しくありません');
  }
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
}

export async function switchLearner(level: UserLevel): Promise<SessionInfo> {
  const response = await authFetch('/auth/switch-learner', {
    method: 'POST',
    body: JSON.stringify({ user_level: level }),
  });
  if (response.status === 401) {
    notifyApiUnauthorized();
    throw new Error('ログインが必要です');
  }
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: string };
      if (body.detail) detail = body.detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  const body = (await response.json()) as unknown;
  if (typeof body !== 'object' || body === null) {
    throw new Error('invalid switch-learner response');
  }
  const record = body as Record<string, unknown>;
  if (typeof record.username !== 'string' || !record.username) {
    throw new Error('invalid switch-learner response');
  }
  const userLevel = parseUserLevel(record.user_level);
  if (userLevel === null) {
    throw new Error('invalid switch-learner response');
  }
  return { username: record.username, user_level: userLevel };
}

export async function logout(): Promise<void> {
  await authFetch('/auth/logout', { method: 'POST' });
  notifyApiUnauthorized();
}
