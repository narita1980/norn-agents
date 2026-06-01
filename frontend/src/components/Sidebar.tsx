import { useEffect, useState } from 'react';
import { deleteThread, listThreads, type ThreadSummary } from '../lib/api';
import type { UserLevel } from '../lib/userLevels';
import { learnerByLevel } from '../lib/userLevels';

type Props = {
  open: boolean;
  onToggle: () => void;
  activeThreadId: string | null;
  userLevel: UserLevel;
  onSelect: (threadId: string | null) => void;
  onDeleted?: (threadId: string) => void;
  refreshKey: number;
  consensusOpen: boolean;
  onToggleConsensus: () => void;
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

function ThreadListIcon() {
  return (
    <svg
      className="activity-rail__icon"
      viewBox="0 0 24 24"
      width={22}
      height={22}
      aria-hidden="true"
    >
      <path
        fill="currentColor"
        d="M4 6.5a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Zm0 4.5a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Zm0 4.5a1.5 1.5 0 1 1 0 3 1.5 1.5 0 0 1 0-3Zm5-9h11a1 1 0 1 1 0 2H9a1 1 0 1 1 0-2Zm0 4.5h11a1 1 0 1 1 0 2H9a1 1 0 1 1 0-2Zm0 4.5h11a1 1 0 1 1 0 2H9a1 1 0 1 1 0-2Z"
      />
    </svg>
  );
}

function NewChatIcon() {
  return (
    <svg
      className="activity-rail__icon"
      viewBox="0 0 24 24"
      width={22}
      height={22}
      aria-hidden="true"
    >
      <path
        fill="currentColor"
        d="M12 3a1 1 0 0 1 1 1v7h7a1 1 0 1 1 0 2h-7v7a1 1 0 1 1-2 0v-7H4a1 1 0 1 1 0-2h7V4a1 1 0 0 1 1-1Z"
      />
    </svg>
  );
}

function ConsensusIcon() {
  return (
    <svg
      className="activity-rail__icon"
      viewBox="0 0 24 24"
      width={22}
      height={22}
      aria-hidden="true"
    >
      <path
        fill="currentColor"
        d="M4 5.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5Zm8 0a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5Zm8 0a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5ZM4 13.5a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5Zm8 0a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5Zm8 0a2.5 2.5 0 1 1 0 5 2.5 2.5 0 0 1 0-5Z"
      />
    </svg>
  );
}

export function Sidebar({
  open,
  onToggle,
  activeThreadId,
  userLevel,
  onSelect,
  onDeleted,
  refreshKey,
  consensusOpen,
  onToggleConsensus,
}: Props) {
  const [threads, setThreads] = useState<ThreadSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await listThreads(userLevel);
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
  }, [refreshKey, userLevel]);

  async function handleDelete(thread: ThreadSummary, event: React.MouseEvent) {
    event.stopPropagation();
    if (deletingId !== null) return;
    if (!window.confirm(deleteConfirmMessage(thread))) return;

    setDeletingId(thread.thread_id);
    try {
      await deleteThread(thread.thread_id, userLevel);
      setThreads((prev) => prev.filter((t) => t.thread_id !== thread.thread_id));
      setError(null);
      onDeleted?.(thread.thread_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="chat-shell__side">
      <nav className="activity-rail" aria-label="サイドパネル">
        <button
          type="button"
          className={`activity-rail__btn${activeThreadId === null ? ' activity-rail__btn--active' : ''}`}
          onClick={() => onSelect(null)}
          title="新規チャット"
        >
          <NewChatIcon />
          <span className="activity-rail__label">新規</span>
        </button>
        <button
          type="button"
          className={`activity-rail__btn${open ? ' activity-rail__btn--active' : ''}`}
          onClick={onToggle}
          aria-expanded={open}
          aria-controls="thread-panel"
          title="スレッド一覧"
        >
          <ThreadListIcon />
          <span className="activity-rail__label">スレッド</span>
        </button>
        <button
          type="button"
          className={`activity-rail__btn${consensusOpen ? ' activity-rail__btn--active' : ''}`}
          onClick={onToggleConsensus}
          aria-expanded={consensusOpen}
          aria-controls="consensus-panel"
          title="合議ライブ"
        >
          <ConsensusIcon />
          <span className="activity-rail__label">合議</span>
        </button>
      </nav>
      <aside
        id="thread-panel"
        className={`sidebar${open ? ' sidebar--open' : ''}`}
        aria-hidden={!open}
      >
        <div className="sidebar__header">
          <span>スレッド（{learnerByLevel(userLevel).name}）</span>
          <button
            type="button"
            className="sidebar__new"
            title="新規チャット"
            onClick={() => onSelect(null)}
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
            const isDeleting = deletingId === thread.thread_id;
            return (
              <li key={thread.thread_id} className="sidebar__row">
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
    </div>
  );
}
