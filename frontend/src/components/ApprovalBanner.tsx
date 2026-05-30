import { useState } from 'react';
import { skipReview, startReview, type ActionPayload } from '../lib/api';

type Props = {
  payload: ActionPayload;
  onResolved: () => void;
};

export function ApprovalBanner({ payload, onResolved }: Props) {
  const [busy, setBusy] = useState<'start' | 'skip' | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleStart() {
    setBusy('start');
    setError(null);
    try {
      await startReview(payload.session_id);
      onResolved();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  async function handleSkip() {
    setBusy('skip');
    setError(null);
    try {
      await skipReview(payload.session_id);
      onResolved();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="approval">
      <p className="approval__title">
        Norn のレビューを開始しますか？{' '}
        {payload.pr_url ? (
          <a href={payload.pr_url} target="_blank" rel="noreferrer">
            {payload.repository} #{payload.pr_number}
          </a>
        ) : (
          <span>
            {payload.repository} #{payload.pr_number}
          </span>
        )}
      </p>
      {payload.pr_title && <p className="approval__pr">{payload.pr_title}</p>}
      <div className="approval__actions">
        <button
          type="button"
          className="approval__primary"
          onClick={handleStart}
          disabled={busy !== null}
        >
          {busy === 'start' ? '起動中…' : '開始する'}
        </button>
        <button
          type="button"
          className="approval__secondary"
          onClick={handleSkip}
          disabled={busy !== null}
        >
          {busy === 'skip' ? '更新中…' : '今回はスキップ'}
        </button>
      </div>
      {error && <p className="approval__error">{error}</p>}
    </div>
  );
}
