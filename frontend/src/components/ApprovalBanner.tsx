import { useState } from 'react';
import { skipReview, startReview, type ActionPayload } from '../lib/api';

type Props = {
  payload: ActionPayload;
  onResolved: () => void;
};

export function ApprovalBanner({ payload, onResolved }: Props) {
  const [choice, setChoice] = useState<'start' | 'skip' | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleStart() {
    if (choice !== null) return;
    setChoice('start');
    setError(null);
    try {
      await startReview(payload.session_id);
      onResolved();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  async function handleSkip() {
    if (choice !== null) return;
    setChoice('skip');
    setError(null);
    try {
      await skipReview(payload.session_id);
      onResolved();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    }
  }

  const resolvedLabel =
    choice === 'start'
      ? '合議を開始しました。右パネルで進行を確認できます。'
      : choice === 'skip'
        ? '今回はスキップしました。'
        : null;

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
      {choice === null ? (
        <div className="approval__actions">
          <button type="button" className="approval__primary" onClick={handleStart}>
            開始する
          </button>
          <button type="button" className="approval__secondary" onClick={handleSkip}>
            今回はスキップ
          </button>
        </div>
      ) : (
        <p className="approval__resolved" aria-live="polite">
          {resolvedLabel}
        </p>
      )}
      {error && <p className="approval__error">{error}</p>}
    </div>
  );
}
