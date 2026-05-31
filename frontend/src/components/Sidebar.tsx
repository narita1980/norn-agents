import { useEffect, useState } from 'react';
import { deleteThread, listThreads, type ThreadSummary } from '../lib/api';

type Props = {
  open: boolean;
  onClose: () => void;
  activeThreadId: string | null;
  onSelect: (threadId: string | null) => void;
  onDeleted?: (threadId: string) => void;
  refreshKey: number;
};

const STATUS_LABEL: Record<string, string> = {
  pending_approval: '承認待ち',
  running: '合議中',
  completed: '完了',
  failed: '失敗',
  skipped: 'スキップ',
};

function deleteConfirmMessage(thread: ThreadSummary): string {
  if (thread.session_id !== null) {
    return 'この PR レビュースレッドを削除します。承認待ち・合議履歴も消えます。';
  }
  return 'このチャットを削除しますか？';
}

export function Sidebar({ open, onClose, activeThreadId, onSelect, onDeleted, refreshKey }: Props) {
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

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

  async function handleDelete(thread: ThreadSummary, event: React.MouseEvent) {
    event.stopPropagation();
    if (deletingId !== null) return;
    if (!window.confirm(deleteConfirmMessage(thread))) return;

    setDeletingId(thread.thread_id);
    try {
      await deleteThread(thread.thread_id);
      setThreads((prev) => prev.filter((t) => t.thread_id !== thread.thread_id));
      setError(null);
      onDeleted?.(thread.thread_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeletingId(null);
    }
  }

  function handleSelect(threadId: string | null) {
    onSelect(threadId);
    onClose();
  }

  return (
    <>
      <div
        className={`sidebar-backdrop ${open ? 'sidebar-backdrop--visible' : ''}`}
        onClick={onClose}
        aria-hidden={!open}
      />
      <aside className={`sidebar ${open ? 'sidebar--open' : ''}`} aria-hidden={!open}>
      <div className="sidebar__header">
        <span>スレッド</span>
        <div className="sidebar__header-actions">
          <button
            type="button"
            className="sidebar__new"
            onClick={() => handleSelect(null)}
            title="新しいチャット"
          >
            ＋
          </button>
          <button
            type="button"
            className="sidebar__close"
            onClick={onClose}
            title="閉じる"
            aria-label="スレッド一覧を閉じる"
          >
            ×
          </button>
        </div>
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
          const isDeleting = deletingId === thread.thread_id;
          return (
            <li key={thread.thread_id} className="sidebar__row">
              <button
                type="button"
                className={`sidebar__item ${isActive ? 'sidebar__item--active' : ''}`}
                onClick={() => handleSelect(thread.thread_id)}
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
              <button
                type="button"
                className="sidebar__delete"
                title="スレッドを削除"
                disabled={isDeleting}
                onClick={(event) => handleDelete(thread, event)}
                aria-label="スレッドを削除"
              >
                ×
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
    </>
  );
}
