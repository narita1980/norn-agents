/** SWA + 別オリジン API 時はビルド時に VITE_API_BASE_URL を設定。未設定なら同一オリジン。 */
export const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? '';

export const CROSS_ORIGIN_API = API_BASE.length > 0;

export function isCrossOriginApi(): boolean {
  return CROSS_ORIGIN_API;
}

export function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}
