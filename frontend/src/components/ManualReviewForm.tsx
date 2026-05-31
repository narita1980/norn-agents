import { useState, type FormEvent } from 'react';
import { registerManualReview } from '../lib/api';

type Props = {
  threadId: string | null;
  disabled: boolean;
  onRegistered: (threadId: string) => void | Promise<void>;
};

export function ManualReviewForm({ threadId, disabled, onRegistered }: Props) {
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
        thread_id: threadId ?? undefined,
      });
      setValue('');
      await onRegistered(result.thread_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="manual-review" onSubmit={handleSubmit}>
      <label className="manual-review__label" htmlFor="manual-pr-ref">
        プルリクを手動レビュー
      </label>
      <div className="manual-review__row">
        <input
          id="manual-pr-ref"
          className="manual-review__input"
          type="text"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="owner/repo#42 または GitHub PR URL"
          disabled={disabled || busy}
          required
        />
        <button type="submit" disabled={disabled || busy || !value.trim()}>
          {busy ? '登録中…' : '登録'}
        </button>
      </div>
      <p className="manual-review__hint">
        Webhook なしで PR を承認待ちに追加します。登録後に「開始する」で合議が始まります。
      </p>
      {error && <p className="manual-review__error">{error}</p>}
    </form>
  );
}
