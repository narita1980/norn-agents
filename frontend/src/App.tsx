import { useCallback, useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { Composer } from './components/Composer';
import { ConsensusPanel } from './components/ConsensusPanel';
import { ManualReviewForm } from './components/ManualReviewForm';
import { useThreadConsensus, type ConsensusSeed } from './hooks/useThreadConsensus';
import { Dashboard } from './components/Dashboard';
import { MessageList, type Message } from './components/MessageList';
import { Sidebar } from './components/Sidebar';
import { TopNav } from './components/TopNav';
import {
  getThread,
  postMessage,
  type AgentTurn,
  type ChatMessageRecord,
  type Consensus,
} from './lib/api';

type View = 'chat' | 'dashboard';

const EMPTY_CONSENSUS: ConsensusSeed = {
  turns: [],
  consensus: null,
  status: 'idle',
};

export default function App() {
  const [view, setView] = useState<View>('chat');
  const [threadId, setThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [sending, setSending] = useState(false);
  const [sidebarRefresh, setSidebarRefresh] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [consensusSeed, setConsensusSeed] = useState<ConsensusSeed>(EMPTY_CONSENSUS);
  const pendingNewThreadRef = useRef<string | null>(null);
  const consensus = useThreadConsensus(threadId, consensusSeed);

  const refreshSidebar = useCallback(() => {
    setSidebarRefresh((n) => n + 1);
  }, []);

  const applyThreadConsensus = useCallback((rows: ChatMessageRecord[]) => {
    const latest = latestTranscript(rows);
    if (latest) {
      setConsensusSeed({
        turns: latest.turns,
        consensus: latest.consensus,
        status: 'completed',
      });
    } else {
      setConsensusSeed(EMPTY_CONSENSUS);
    }
  }, []);

  const loadThread = useCallback(
    async (id: string) => {
      try {
        const data = await getThread(id);
        setMessages(data.messages.map(toMessage));
        applyThreadConsensus(data.messages);
        setError(null);
      } catch (err) {
        setMessages([]);
        setConsensusSeed(EMPTY_CONSENSUS);
        setError(err instanceof Error ? err.message : String(err));
      }
    },
    [applyThreadConsensus],
  );

  useEffect(() => {
    if (!threadId) {
      setMessages([]);
      setConsensusSeed(EMPTY_CONSENSUS);
      return;
    }
    if (pendingNewThreadRef.current === threadId) {
      pendingNewThreadRef.current = null;
      return;
    }
    loadThread(threadId);
  }, [threadId, loadThread]);

  const handleSelectThread = useCallback((id: string | null) => {
    setThreadId(id);
    setConsensusSeed(EMPTY_CONSENSUS);
    setError(null);
    setView('chat');
  }, []);

  const handleActionResolved = useCallback(async () => {
    if (threadId) await loadThread(threadId);
    refreshSidebar();
  }, [loadThread, refreshSidebar, threadId]);

  const handleManualReviewRegistered = useCallback(
    async (id: string) => {
      setThreadId(id);
      setConsensusSeed(EMPTY_CONSENSUS);
      setError(null);
      await loadThread(id);
      refreshSidebar();
    },
    [loadThread, refreshSidebar],
  );

  async function handleSend(content: string) {
    const activeThreadId = threadId ?? crypto.randomUUID();
    const isNewThread = threadId === null;

    if (isNewThread) {
      pendingNewThreadRef.current = activeThreadId;
      flushSync(() => setThreadId(activeThreadId));
    }

    setMessages((prev) => [...prev, { role: 'user', content }]);
    setConsensusSeed({ turns: [], consensus: null, status: 'streaming', pipelineAgents: [] });
    setSending(true);
    setError(null);

    try {
      const data = await postMessage({ thread_id: activeThreadId, content });
      setMessages((prev) => [...prev, { role: 'assistant', content: data.reply }]);
      setConsensusSeed({
        turns: data.transcript ?? [],
        consensus: data.consensus ?? null,
        status: data.transcript?.length ? 'completed' : 'idle',
      });
      refreshSidebar();
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err);
      setError(detail);
      setConsensusSeed((prev) => ({ ...prev, status: 'failed' }));
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
            <MessageList
              messages={messages}
              onActionResolved={handleActionResolved}
              consensusTurns={consensus.turns}
              consensusStatus={consensus.status}
              pipelineAgents={consensus.pipelineAgents}
            />
            <ManualReviewForm
              threadId={threadId}
              disabled={sending}
              onRegistered={handleManualReviewRegistered}
            />
            <Composer onSend={handleSend} disabled={sending} />
            {error && <p className="chat__error">{error}</p>}
            <p className="hint">
              スレッドID: <span>{threadId ?? '（新規）'}</span>
            </p>
          </main>
          <ConsensusPanel
            threadId={threadId}
            turns={consensus.turns}
            consensus={consensus.consensus}
            status={consensus.status}
          />
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

function latestTranscript(messages: ChatMessageRecord[]): {
  turns: AgentTurn[];
  consensus: Consensus | null;
} | null {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    const message = messages[i];
    if (message.transcript?.length) {
      return {
        turns: message.transcript,
        consensus: (message.consensus as Consensus | undefined) ?? null,
      };
    }
  }
  return null;
}
