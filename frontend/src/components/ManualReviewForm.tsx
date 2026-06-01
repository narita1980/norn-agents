import { useState, type FormEvent } from 'react';
import { registerManualReview } from '../lib/api';
import type { UserLevel } from '../lib/userLevels';

type Props = {
  userLevel: UserLevel;
  disabled: boolean;
  onRegistered: (threadId: string) => void | Promise<void>;
};

export function ManualReviewForm({ userLevel, disabled, onRegistered }: Props) {
  const [expanded, setExpanded] = useState(false);
  const [value, setValue] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const prRef = value.trim();
    if (!prRef || disabled || busy) return;

    setBusy(true);
    setError(null);
    try {
      const result = await registerManualReview({
        pr_ref: prRef,
        user_level: userLevel,
      });
      setValue('');
      setExpanded(false);
      await onRegistered(result.thread_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!expanded) {
    return (
      <button
        type="button"
        className="chat-input-dock__pr-link"
        onClick={() => setExpanded(true)}
        disabled={disabled}
      >
        PR を手動登録
      </button>
    );
  }

  return (
    <form className="chat-input-dock__pr" onSubmit={handleSubmit}>
      <input
        id="manual-pr-ref"
        className="chat-input-dock__pr-input"
        type="text"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="owner/repo#42 または PR URL"
        disabled={disabled || busy}
        autoFocus
        required
      />
      <button type="submit" className="chat-input-dock__pr-submit" disabled={disabled || busy || !value.trim()}>
        {busy ? '…' : '登録'}
      </button>
      <button
        type="button"
        className="chat-input-dock__pr-close"
        onClick={() => {
          setExpanded(false);
          setError(null);
        }}
        disabled={busy}
        aria-label="閉じる"
        title="閉じる"
      >
        ×
      </button>
      {error && <p className="chat-input-dock__pr-error">{error}</p>}
    </form>
  );
}
