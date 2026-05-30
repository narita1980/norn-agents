import { useState } from 'react';
import { Composer } from './components/Composer';
import { MessageList, type Message } from './components/MessageList';
import { postMessage } from './lib/api';

export default function App() {
  const [threadId, setThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [sending, setSending] = useState(false);

  async function handleSend(content: string) {
    setMessages((prev) => [...prev, { role: 'user', content }]);
    setSending(true);
    try {
      const data = await postMessage({ thread_id: threadId, content });
      if (!threadId) setThreadId(data.thread_id);
      setMessages((prev) => [...prev, { role: 'assistant', content: data.reply }]);
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `エラーが発生しました: ${detail}` },
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <>
      <header>
        <h1>Norn</h1>
        <p className="subtitle">3女神があなたのコードに伴走します</p>
      </header>
      <main>
        <MessageList messages={messages} />
        <Composer onSend={handleSend} disabled={sending} />
        <p className="hint">
          スレッドID: <span>{threadId ?? '（新規）'}</span>
        </p>
      </main>
    </>
  );
}
