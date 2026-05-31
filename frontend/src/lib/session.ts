import { apiUrl } from './apiBase';

export const API_UNAUTHORIZED_EVENT = 'norn-api-unauthorized';

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

/** 認証不要、または有効なセッションがあるとき true。ログインが必要なとき false。 */
export async function checkSession(): Promise<boolean> {
  const response = await authFetch('/auth/session', { method: 'GET' });
  if (response.ok) return true;
  if (response.status === 401) return false;
  let detail = `HTTP ${response.status}`;
  try {
    const body = (await response.json()) as { detail?: string };
    if (body.detail) detail = body.detail;
  } catch {
    // ignore
  }
  throw new Error(detail);
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

export async function logout(): Promise<void> {
  await authFetch('/auth/logout', { method: 'POST' });
}
