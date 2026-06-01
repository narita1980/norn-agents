import { useState, type FormEvent, type KeyboardEvent } from 'react';

type Props = {
  onSend: (content: string) => void | Promise<void>;
  disabled: boolean;
};

export function Composer({ onSend, disabled }: Props) {
  const [value, setValue] = useState('');

  async function submitMessage() {
    const content = value.trim();
    if (!content || disabled) return;
    setValue('');
    await onSend(content);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    await submitMessage();
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    void submitMessage();
  }

  return (
    <form id="composer" className="chat-input-dock__composer" onSubmit={handleSubmit}>
      <div className="chat-input-dock__field">
        <textarea
          id="input"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="メッセージを入力..."
          rows={2}
          disabled={disabled}
          required
        />
        <button
          type="submit"
          className="chat-input-dock__send"
          disabled={disabled || !value.trim()}
          aria-label="送信"
          title="送信"
        >
          <svg viewBox="0 0 24 24" width={18} height={18} aria-hidden="true">
            <path
              fill="currentColor"
              d="M3.4 20.6 21 12 3.4 3.4l1.8 7.2L16 12l-10.8 1.4-1.8 7.2Z"
            />
          </svg>
        </button>
      </div>
      <p className="chat-input-dock__composer-hint">Enter で送信 · Shift+Enter で改行</p>
    </form>
  );
}
