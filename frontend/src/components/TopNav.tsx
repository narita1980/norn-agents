type Props = {
  view: 'chat' | 'dashboard';
  onSelect: (view: 'chat' | 'dashboard') => void;
};

export function TopNav({ view, onSelect }: Props) {
  return (
    <nav className="top-nav">
      <div className="top-nav__brand">
        <span className="top-nav__title">Norn</span>
        <span className="top-nav__subtitle">3女神があなたのコードに伴走します</span>
      </div>
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
          className={`top-nav__tab ${view === 'dashboard' ? 'top-nav__tab--active' : ''}`}
          onClick={() => onSelect('dashboard')}
        >
          ダッシュボード
        </button>
      </div>
    </nav>
  );
}
