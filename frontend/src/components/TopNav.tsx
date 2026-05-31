export type AppView = 'chat' | 'dashboard' | 'about';

type Props = {
  view: AppView;
  onSelect: (view: AppView) => void;
};

export function TopNav({ view, onSelect }: Props) {
  return (
    <nav className="top-nav">
      <button
        type="button"
        className="top-nav__brand"
        onClick={() => onSelect('about')}
        title="Norn とは"
      >
        <span className="top-nav__title">Norn</span>
        <span className="top-nav__subtitle">若手向け AI コードレビュー伴走（ノルン）</span>
      </button>
      <div className="top-nav__tabs">
        <button
          type="button"
          className={`top-nav__tab ${view === 'chat' ? 'top-nav__tab--active' : ''}`}
          onClick={() => onSelect('chat')}
        >
          チャット
        </button>
        <button
          type="button"
          className={`top-nav__tab ${view === 'about' ? 'top-nav__tab--active' : ''}`}
          onClick={() => onSelect('about')}
        >
          Norn とは
        </button>
        <button
          type="button"
          className={`top-nav__tab ${view === 'dashboard' ? 'top-nav__tab--active' : ''}`}
          onClick={() => onSelect('dashboard')}
        >
          ダッシュボード
        </button>
      </div>
    </nav>
  );
}
