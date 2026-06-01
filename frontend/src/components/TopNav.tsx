import { useState } from 'react';
import { PRODUCT_NAME_EN } from '../lib/brand';
import { LearnerSwitcher } from './LearnerSwitcher';
import { logout } from '../lib/session';
import type { UserLevel } from '../lib/userLevels';

export type AppView = 'chat' | 'dashboard' | 'about';

function UserIcon() {
  return (
    <svg className="top-nav__user-icon" viewBox="0 0 24 24" width={16} height={16} aria-hidden="true">
      <path
        fill="currentColor"
        d="M12 12a4.5 4.5 0 1 0 0-9 4.5 4.5 0 0 0 0 9Zm0 2.25c-4.01 0-7.25 2.13-7.25 4.75V21a1 1 0 1 0 2 0v-1.5c0-.96 2.35-2.25 5.25-2.25s5.25 1.29 5.25 2.25V21a1 1 0 1 0 2 0v-2c0-2.62-3.24-4.75-7.25-4.75Z"
      />
    </svg>
  );
}

type Props = {
  view: AppView;
  username: string | null;
  userLevel: UserLevel;
  onSelect: (view: AppView) => void;
  onLearnerSwitched: (level: UserLevel, username: string) => void;
};

export function TopNav({ view, username, userLevel, onSelect, onLearnerSwitched }: Props) {
  const [busy, setBusy] = useState(false);

  async function handleLogout() {
    if (busy) return;
    setBusy(true);
    try {
      await logout();
    } finally {
      setBusy(false);
    }
  }

  return (
    <nav className="top-nav">
      <button
        type="button"
        className="top-nav__brand"
        onClick={() => onSelect('about')}
        title={`${PRODUCT_NAME_EN} とは`}
      >
        <span className="top-nav__title">{PRODUCT_NAME_EN}</span>
      </button>
      <div className="top-nav__right">
        <div className="top-nav__tabs" role="tablist" aria-label="メイン">
          <button
            type="button"
            role="tab"
            aria-selected={view === 'chat'}
            className={`top-nav__tab ${view === 'chat' ? 'top-nav__tab--active' : ''}`}
            onClick={() => onSelect('chat')}
          >
            チャット
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={view === 'dashboard'}
            className={`top-nav__tab ${view === 'dashboard' ? 'top-nav__tab--active' : ''}`}
            onClick={() => onSelect('dashboard')}
          >
            ダッシュボード
          </button>
        </div>
        {username && (
          <div className="top-nav__session">
            <LearnerSwitcher
              currentLevel={userLevel}
              username={username}
              onSwitched={onLearnerSwitched}
            />
            <div className="top-nav__user" title={`ログイン中: ${username}`}>
              <UserIcon />
              <span className="top-nav__user-label">ログイン</span>
              <span className="top-nav__user-name">{username}</span>
            </div>
            <button
              type="button"
              className="top-nav__logout"
              onClick={() => void handleLogout()}
              disabled={busy}
            >
              {busy ? 'ログアウト中…' : 'ログアウト'}
            </button>
          </div>
        )}
      </div>
    </nav>
  );
}
