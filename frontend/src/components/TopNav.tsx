import { useState } from 'react';
import { PRODUCT_NAME_EN } from '../lib/brand';
import { LearnerSwitcher } from './LearnerSwitcher';
import { logout } from '../lib/session';
import type { UserLevel } from '../lib/userLevels';

export type AppView = 'chat' | 'dashboard' | 'about';

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
            <LearnerSwitcher currentLevel={userLevel} onSwitched={onLearnerSwitched} />
            <span className="top-nav__session-sep" aria-hidden="true">
              ·
            </span>
            <button
              type="button"
              className="top-nav__logout"
              onClick={() => void handleLogout()}
              disabled={busy}
            >
              {busy ? '…' : 'ログアウト'}
            </button>
          </div>
        )}
      </div>
    </nav>
  );
}
