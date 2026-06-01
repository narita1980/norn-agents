import { useCallback, useEffect, useState, type FormEvent } from 'react';
import { PRODUCT_NAME_EN } from '../lib/brand';
import { API_UNAUTHORIZED_EVENT, checkSession, login } from '../lib/session';
import { LOGIN_USERNAME_BY_LEVEL, TEST_LEARNERS, type UserLevel } from '../lib/userLevels';

type Props = {
  children: React.ReactNode;
};

type GateState = 'loading' | 'authenticated' | 'login';

export function LoginGate({ children }: Props) {
  const [gate, setGate] = useState<GateState>('loading');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const refreshSession = useCallback(async () => {
    try {
      const ok = await checkSession();
      setGate(ok ? 'authenticated' : 'login');
      if (ok) setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setGate('login');
    }
  }, []);

  useEffect(() => {
    void refreshSession();
  }, [refreshSession]);

  useEffect(() => {
    const onUnauthorized = () => {
      setGate('login');
      setPassword('');
    };
    window.addEventListener(API_UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(API_UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  function handleQuickPick(level: UserLevel) {
    if (busy) return;
    setUsername(LOGIN_USERNAME_BY_LEVEL[level]);
    setError(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const user = username.trim();
    const pass = password;
    if (!user || !pass || busy) return;

    setBusy(true);
    setError(null);
    try {
      await login(user, pass);
      setGate('authenticated');
      setPassword('');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (gate === 'loading') {
    return (
      <div className="api-auth">
        <p className="api-auth__hint">読み込み中…</p>
      </div>
    );
  }

  if (gate === 'authenticated') {
    return children;
  }

  return (
    <div className="api-auth">
      <form className="api-auth__card" onSubmit={handleSubmit}>
        <h1 className="api-auth__title">{PRODUCT_NAME_EN} にログイン</h1>
        <p className="api-auth__hint">
          下のボタンで ID を選び、パスワードを入力してログインしてください。
        </p>
        <div className="api-auth__quick" role="group" aria-label="テストユーザー選択">
          <span className="api-auth__quick-label">デモ用アカウント</span>
          <div className="api-auth__quick-options">
            {TEST_LEARNERS.map((learner) => (
              <button
                key={learner.level}
                type="button"
                className={`api-auth__quick-btn${
                  username === LOGIN_USERNAME_BY_LEVEL[learner.level]
                    ? ' api-auth__quick-btn--active'
                    : ''
                }`}
                disabled={busy}
                onClick={() => handleQuickPick(learner.level)}
              >
                <span className="api-auth__quick-name">{learner.name}</span>
                <span className="api-auth__quick-subtitle">{learner.subtitle}</span>
              </button>
            ))}
          </div>
        </div>
        <label className="api-auth__label" htmlFor="login-user">
          ID
        </label>
        <input
          id="login-user"
          className="api-auth__input"
          type="text"
          autoComplete="username"
          value={username}
          onChange={(event) => setUsername(event.target.value)}
          disabled={busy}
          required
        />
        <label className="api-auth__label" htmlFor="login-pass">
          パスワード
        </label>
        <input
          id="login-pass"
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
          {busy ? 'ログイン中…' : 'ログイン'}
        </button>
      </form>
    </div>
  );
}
