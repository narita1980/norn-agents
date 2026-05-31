/** SWA → Container Apps クロスオリジン時の API Basic 認証（sessionStorage）。 */

export type BasicAuthCredentials = {
  username: string;
  password: string;
};

const STORAGE_KEY = 'norn-api-basic-auth';

export function loadApiCredentials(): BasicAuthCredentials | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as unknown;
    if (
      typeof parsed === 'object' &&
      parsed !== null &&
      typeof (parsed as BasicAuthCredentials).username === 'string' &&
      typeof (parsed as BasicAuthCredentials).password === 'string'
    ) {
      return parsed as BasicAuthCredentials;
    }
  } catch {
    // ignore
  }
  return null;
}

export function storeApiCredentials(credentials: BasicAuthCredentials): void {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(credentials));
}

export function clearApiCredentials(): void {
  sessionStorage.removeItem(STORAGE_KEY);
}

export function authorizationHeader(): string | null {
  const credentials = loadApiCredentials();
  if (!credentials) return null;
  return `Basic ${btoa(`${credentials.username}:${credentials.password}`)}`;
}

export const API_UNAUTHORIZED_EVENT = 'norn-api-unauthorized';

export function notifyApiUnauthorized(): void {
  clearApiCredentials();
  window.dispatchEvent(new CustomEvent(API_UNAUTHORIZED_EVENT));
}
