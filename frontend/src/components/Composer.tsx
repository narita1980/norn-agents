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
    <form id="composer" onSubmit={handleSubmit}>
      <textarea
        id="input"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="メッセージを入力..."
        rows={3}
        disabled={disabled}
        required
      />
      <div className="composer__footer">
        <p className="composer__hint">Enter で送信 · Shift+Enter で改行</p>
        <button type="submit" disabled={disabled}>
          送信
        </button>
      </div>
    </form>
  );
}
