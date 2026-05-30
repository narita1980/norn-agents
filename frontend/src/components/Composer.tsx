import { useState, type FormEvent } from 'react';

type Props = {
  onSend: (content: string) => void | Promise<void>;
  disabled: boolean;
};

export function Composer({ onSend, disabled }: Props) {
  const [value, setValue] = useState('');

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const content = value.trim();
    if (!content || disabled) return;
    setValue('');
    await onSend(content);
  }

  return (
    <form id="composer" onSubmit={handleSubmit}>
      <textarea
        id="input"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        placeholder="メッセージを入力してください..."
        rows={3}
        disabled={disabled}
        required
      />
      <button type="submit" disabled={disabled}>
        送信
      </button>
    </form>
  );
}
