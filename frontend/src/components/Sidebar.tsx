import { useEffect, useState } from 'react';
import { listThreads, type ThreadSummary } from '../lib/api';

type Props = {
  activeThreadId: string | null;
  onSelect: (threadId: string | null) => void;
  refreshKey: number;
};

const STATUS_LABEL: Record<string, string> = {
  pending_approval: '承認待ち',
  running: '合議中',
  completed: '完了',
  failed: '失敗',
  skipped: 'スキップ',
};

export function Sidebar({ activeThreadId, onSelect, refreshKey }: Props) {
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await listThreads();
        if (!cancelled) {
          setThreads(data);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      }
    }
    load();
    const interval = window.setInterval(load, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [refreshKey]);

  return (
    <aside className="sidebar">
      <div className="sidebar__header">
        <span>スレッド</span>
        <button
          type="button"
          className="sidebar__new"
          onClick={() => onSelect(null)}
          title="新しいチャット"
        >
          ＋
        </button>
      </div>
      {error && <p className="sidebar__error">{error}</p>}
      <ul className="sidebar__list">
        {threads.length === 0 && (
          <li className="sidebar__empty">スレッドはまだありません</li>
        )}
        {threads.map((thread) => {
          const isActive = thread.thread_id === activeThreadId;
          const isPR = thread.session_id !== null;
          const label = isPR
            ? `${thread.repository_name} #${thread.pr_number}`
            : 'チャット';
          const statusLabel = thread.status ? STATUS_LABEL[thread.status] ?? thread.status : null;
          return (
            <li key={thread.thread_id}>
              <button
                type="button"
                className={`sidebar__item ${isActive ? 'sidebar__item--active' : ''}`}
                onClick={() => onSelect(thread.thread_id)}
              >
                <div className="sidebar__item-header">
                  <span className="sidebar__item-title">{label}</span>
                  {thread.has_pending_action && (
                    <span className="sidebar__badge sidebar__badge--pending">!</span>
                  )}
                </div>
                {statusLabel && (
                  <span className={`sidebar__status sidebar__status--${thread.status}`}>
                    {statusLabel}
                  </span>
                )}
                <p className="sidebar__excerpt">{thread.last_excerpt || '（メッセージなし）'}</p>
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
