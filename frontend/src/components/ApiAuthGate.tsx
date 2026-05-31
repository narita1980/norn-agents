import { useCallback, useEffect, useState, type FormEvent } from 'react';
import {
  API_UNAUTHORIZED_EVENT,
  loadApiCredentials,
  storeApiCredentials,
} from '../lib/basicAuth';
import { isCrossOriginApi } from '../lib/api';

type Props = {
  children: React.ReactNode;
};

export function ApiAuthGate({ children }: Props) {
  const crossOrigin = isCrossOriginApi();
  const [authed, setAuthed] = useState(
    () => !crossOrigin || loadApiCredentials() !== null,
  );
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!crossOrigin) return;
    const onUnauthorized = () => setAuthed(false);
    window.addEventListener(API_UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(API_UNAUTHORIZED_EVENT, onUnauthorized);
  }, [crossOrigin]);

  const verifyAndStore = useCallback(async (user: string, pass: string) => {
    const base = (import.meta.env.VITE_API_BASE_URL as string).replace(/\/$/, '');
    const response = await fetch(`${base}/chat/threads?user_level=junior`, {
      headers: { Authorization: `Basic ${btoa(`${user}:${pass}`)}` },
      credentials: 'include',
    });
    if (response.status === 401) {
      throw new Error('ユーザー名またはパスワードが正しくありません');
    }
    if (!response.ok) {
      throw new Error(`API に接続できません（HTTP ${response.status}）`);
    }
    storeApiCredentials({ username: user, password: pass });
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const user = username.trim();
    const pass = password;
    if (!user || !pass || busy) return;

    setBusy(true);
    setError(null);
    try {
      await verifyAndStore(user, pass);
      setAuthed(true);
      setPassword('');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!crossOrigin || authed) {
    return children;
  }

  return (
    <div className="api-auth">
      <form className="api-auth__card" onSubmit={handleSubmit}>
        <h1 className="api-auth__title">API 認証</h1>
        <p className="api-auth__hint">
          Azure Container Apps の Basic 認証情報を入力してください。SWA から API
          を直接呼び出すため、ブラウザの認証ダイアログは表示されません。
        </p>
        <label className="api-auth__label" htmlFor="api-auth-user">
          ユーザー名
        </label>
        <input
          id="api-auth-user"
          className="api-auth__input"
          type="text"
          autoComplete="username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          disabled={busy}
          required
        />
        <label className="api-auth__label" htmlFor="api-auth-pass">
          パスワード
        </label>
        <input
          id="api-auth-pass"
          className="api-auth__input"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          disabled={busy}
          required
        />
        {error && <p className="api-auth__error">{error}</p>}
        <button type="submit" className="api-auth__submit" disabled={busy}>
          {busy ? '確認中…' : '接続する'}
        </button>
      </form>
    </div>
  );
}
