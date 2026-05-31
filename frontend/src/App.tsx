import { useCallback, useEffect, useRef, useState } from 'react';
import { flushSync } from 'react-dom';
import { Composer } from './components/Composer';
import { ConsensusPanel } from './components/ConsensusPanel';
import { ManualReviewForm } from './components/ManualReviewForm';
import { useThreadConsensus, type ConsensusSeed } from './hooks/useThreadConsensus';
import { Dashboard } from './components/Dashboard';
import { MessageList, type Message } from './components/MessageList';
import { Sidebar } from './components/Sidebar';
import { AboutPage } from './components/AboutPage';
import { LearnerSwitcher } from './components/LearnerSwitcher';
import { TopNav, type AppView } from './components/TopNav';
import {
  getThread,
  postMessage,
  type AgentTurn,
  type ChatMessageRecord,
  type Consensus,
} from './lib/api';
import {
  loadStoredUserLevel,
  loadStoredThreadId,
  storeThreadId,
  storeUserLevel,
  type UserLevel,
} from './lib/userLevels';

const EMPTY_CONSENSUS: ConsensusSeed = {
  turns: [],
  consensus: null,
  status: 'idle',
};

export default function App() {
  const [view, setView] = useState<AppView>('chat');
  const [userLevel, setUserLevel] = useState<UserLevel>(() => loadStoredUserLevel());
  const [threadId, setThreadId] = useState<string | null>(() =>
    loadStoredThreadId(loadStoredUserLevel()),
  );
  const [messages, setMessages] = useState<Message[]>([]);
  const [sending, setSending] = useState(false);
  const [sidebarRefresh, setSidebarRefresh] = useState(0);
  const [sidebarOpen, setSidebarOpen] = useState(false);
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
    }
    // 合議進行中は SSE 状態を維持するため、transcript が無いときは seed を触らない
  }, []);

  const loadThread = useCallback(
    async (id: string, level?: UserLevel) => {
      const effectiveLevel = level ?? userLevel;
      try {
        const data = await getThread(id, effectiveLevel);
        setMessages(data.messages.map(toMessage));
        applyThreadConsensus(data.messages);
        setError(null);
      } catch (err) {
        const detail = err instanceof Error ? err.message : String(err);
        if (detail === 'thread not found' || detail === 'HTTP 404') {
          storeThreadId(effectiveLevel, null);
          setThreadId(null);
        }
        setMessages([]);
        setConsensusSeed(EMPTY_CONSENSUS);
        setError(detail === 'thread not found' ? null : detail);
      }
    },
    [applyThreadConsensus, userLevel],
  );

  useEffect(() => {
    if (view !== 'chat' || !sidebarOpen) return;
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') setSidebarOpen(false);
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [view, sidebarOpen]);

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

  const handleSelectThread = useCallback(
    (id: string | null) => {
      setThreadId(id);
      storeThreadId(userLevel, id);
      setConsensusSeed(EMPTY_CONSENSUS);
      setError(null);
      setView('chat');
    },
    [userLevel],
  );

  const handleThreadDeleted = useCallback(
    (id: string) => {
      if (threadId === id) {
        setThreadId(null);
        storeThreadId(userLevel, null);
        setMessages([]);
        setConsensusSeed(EMPTY_CONSENSUS);
        setError(null);
      }
      refreshSidebar();
    },
    [threadId, userLevel, refreshSidebar],
  );

  const handleActionResolved = useCallback(async () => {
    if (threadId) {
      setConsensusSeed({
        turns: [],
        consensus: null,
        status: 'streaming',
        pipelineAgents: [],
      });
      await loadThread(threadId);
    }
    refreshSidebar();
  }, [loadThread, refreshSidebar, threadId]);

  useEffect(() => {
    if (!threadId) return;
    if (consensus.status !== 'completed' && consensus.status !== 'failed') return;
    void loadThread(threadId);
    refreshSidebar();
  }, [consensus.status, threadId, loadThread, refreshSidebar]);

  const handleManualReviewRegistered = useCallback(
    async (id: string) => {
      setThreadId(id);
      storeThreadId(userLevel, id);
      setConsensusSeed(EMPTY_CONSENSUS);
      setError(null);
      await loadThread(id);
      refreshSidebar();
    },
    [loadThread, refreshSidebar, userLevel],
  );

  async function handleSend(content: string) {
    const activeThreadId = threadId ?? crypto.randomUUID();
    const isNewThread = threadId === null;

    if (isNewThread) {
      pendingNewThreadRef.current = activeThreadId;
      flushSync(() => {
        setThreadId(activeThreadId);
        storeThreadId(userLevel, activeThreadId);
      });
    }

    setMessages((prev) => [...prev, { role: 'user', content }]);
    setConsensusSeed({ turns: [], consensus: null, status: 'streaming', pipelineAgents: [] });
    setSending(true);
    setError(null);

    try {
      const data = await postMessage({
        thread_id: activeThreadId,
        content,
        user_level: userLevel,
      });
      storeThreadId(userLevel, data.thread_id);
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

  function handleUserLevelChange(level: UserLevel) {
    if (level === userLevel) return;
    storeThreadId(userLevel, threadId);
    storeUserLevel(level);
    setUserLevel(level);
    const nextThreadId = loadStoredThreadId(level);
    setThreadId(nextThreadId);
    setMessages([]);
    setConsensusSeed(EMPTY_CONSENSUS);
    setError(null);
    setSidebarOpen(false);
    if (nextThreadId) {
      void loadThread(nextThreadId, level);
    }
  }

  return (
    <div className="app">
      <TopNav view={view} onSelect={setView} />
      {view === 'chat' && (
        <div className="app__body">
          <div className="chat-shell">
            <Sidebar
              open={sidebarOpen}
              onToggle={() => setSidebarOpen((open) => !open)}
              activeThreadId={threadId}
              userLevel={userLevel}
              onSelect={handleSelectThread}
              onDeleted={handleThreadDeleted}
              refreshKey={sidebarRefresh}
            />
            <main className="chat">
            <div className="chat__toolbar">
              <button
                type="button"
                className="chat__toolbar-btn chat__toolbar-btn--secondary"
                onClick={() => handleSelectThread(null)}
              >
                新規チャット
              </button>
              <LearnerSwitcher
                level={userLevel}
                onChange={handleUserLevelChange}
                disabled={sending}
              />
            </div>
            <MessageList
              messages={messages}
              onActionResolved={handleActionResolved}
              consensusTurns={consensus.turns}
              consensusStatus={consensus.status}
              pipelineAgents={consensus.pipelineAgents}
            />
            <ManualReviewForm
              userLevel={userLevel}
              disabled={sending}
              onRegistered={handleManualReviewRegistered}
            />
            <Composer onSend={handleSend} disabled={sending} />
            {error && <p className="chat__error">{error}</p>}
            <p className="hint">
              スレッドID: <span>{threadId ?? '（新規）'}</span>
            </p>
            </main>
          </div>
          <ConsensusPanel
            threadId={threadId}
            turns={consensus.turns}
            consensus={consensus.consensus}
            status={consensus.status}
            pipelineAgents={consensus.pipelineAgents}
          />
        </div>
      )}
      {view === 'dashboard' && (
        <main className="page-wrap">
          <Dashboard />
        </main>
      )}
      {view === 'about' && (
        <main className="page-wrap">
          <AboutPage />
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
