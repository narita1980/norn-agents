import { useCallback, useEffect, useState } from 'react';
import { Composer } from './components/Composer';
import { ConsensusPanel } from './components/ConsensusPanel';
import { Dashboard } from './components/Dashboard';
import { MessageList, type Message } from './components/MessageList';
import { Sidebar } from './components/Sidebar';
import { TopNav } from './components/TopNav';
import {
  getThread,
  postMessage,
  type ChatMessageRecord,
} from './lib/api';

type View = 'chat' | 'dashboard';

export default function App() {
  const [view, setView] = useState<View>('chat');
  const [threadId, setThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [sending, setSending] = useState(false);
  const [sidebarRefresh, setSidebarRefresh] = useState(0);
  const [error, setError] = useState<string | null>(null);

  const refreshSidebar = useCallback(() => {
    setSidebarRefresh((n) => n + 1);
  }, []);

  const loadThread = useCallback(async (id: string) => {
    try {
      const data = await getThread(id);
      setMessages(data.messages.map(toMessage));
      setError(null);
    } catch (err) {
      setMessages([]);
      setError(err instanceof Error ? err.message : String(err));
    }
  }, []);

  useEffect(() => {
    if (!threadId) {
      setMessages([]);
      return;
    }
    loadThread(threadId);
  }, [threadId, loadThread]);

  const handleSelectThread = useCallback((id: string | null) => {
    setThreadId(id);
    setError(null);
    setView('chat');
  }, []);

  const handleActionResolved = useCallback(async () => {
    if (threadId) await loadThread(threadId);
    refreshSidebar();
  }, [loadThread, refreshSidebar, threadId]);

  async function handleSend(content: string) {
    setMessages((prev) => [...prev, { role: 'user', content }]);
    setSending(true);
    setError(null);
    try {
      const data = await postMessage({ thread_id: threadId, content });
      if (!threadId) setThreadId(data.thread_id);
      setMessages((prev) => [...prev, { role: 'assistant', content: data.reply }]);
      refreshSidebar();
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err);
      setError(detail);
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: `エラーが発生しました: ${detail}` },
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="app">
      <TopNav view={view} onSelect={setView} />
      {view === 'chat' ? (
        <div className="app__body">
          <Sidebar
            activeThreadId={threadId}
            onSelect={handleSelectThread}
            refreshKey={sidebarRefresh}
          />
          <main className="chat">
            <MessageList messages={messages} onActionResolved={handleActionResolved} />
            <Composer onSend={handleSend} disabled={sending} />
            {error && <p className="chat__error">{error}</p>}
            <p className="hint">
              スレッドID: <span>{threadId ?? '（新規）'}</span>
            </p>
          </main>
          <ConsensusPanel threadId={threadId} />
        </div>
      ) : (
        <main className="dashboard-wrap">
          <Dashboard />
        </main>
      )}
    </div>
  );
}

function toMessage(row: ChatMessageRecord): Message {
  return {
    message_id: row.message_id,
    role: row.role,
    content: row.content,
    action_payload: row.action_payload ?? null,
  };
}
