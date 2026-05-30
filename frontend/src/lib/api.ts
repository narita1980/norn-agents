export type ActionPayload = {
  type: 'start_or_skip';
  session_id: string;
  repository?: string;
  pr_number?: number;
  pr_title?: string;
  pr_url?: string | null;
};

export type ChatMessageRecord = {
  message_id: string;
  role: 'user' | 'assistant';
  content: string;
  created_at: string | null;
  consensus?: unknown;
  transcript?: AgentTurn[];
  action_payload?: ActionPayload | null;
};

export type AgentTurn = {
  agent: string;
  role_label: string;
  content: string;
};

export type Consensus = {
  summary: string;
  must_fix: string[];
  next_pr: string[];
  growth: string;
  tone: 'encouraging' | 'neutral' | 'cautious';
};

export type PostMessageRequest = {
  thread_id: string | null;
  content: string;
};

export type PostMessageResponse = {
  thread_id: string;
  message_id: string;
  reply: string;
  consensus?: Consensus | null;
  transcript?: AgentTurn[];
};

export type ThreadSummary = {
  thread_id: string;
  last_message_at: string | null;
  last_role: string | null;
  last_excerpt: string;
  session_id: string | null;
  repository_name: string | null;
  pr_number: number | null;
  status: string | null;
  has_pending_action: boolean;
};

export type DashboardStats = {
  sessions: {
    total: number;
    completed: number;
    failed: number;
    skipped: number;
    pending: number;
    running: number;
  };
  by_tone: Record<string, number>;
  recent: {
    session_id: string;
    repository: string;
    pr_number: number;
    updated_at: string | null;
    status: string;
  }[];
  mock: {
    estimated_senior_hours_saved: number;
    learning_minutes_total: number;
    completion_rate: number;
  };
};

export type ThreadDetail = {
  thread_id: string;
  messages: ChatMessageRecord[];
};

async function jsonOrThrow<T>(response: Response): Promise<T> {
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (body && typeof body.detail === 'string') detail = body.detail;
    } catch {
      // ignore parse errors, keep the generic message
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export async function postMessage(body: PostMessageRequest): Promise<PostMessageResponse> {
  const response = await fetch('/chat/messages', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return jsonOrThrow<PostMessageResponse>(response);
}

export async function listThreads(): Promise<ThreadSummary[]> {
  const response = await fetch('/chat/threads');
  const data = await jsonOrThrow<{ threads: ThreadSummary[] }>(response);
  return data.threads;
}

export async function getThread(threadId: string): Promise<ThreadDetail> {
  const response = await fetch(`/chat/threads/${threadId}`);
  return jsonOrThrow<ThreadDetail>(response);
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const response = await fetch('/dashboard/stats');
  return jsonOrThrow<DashboardStats>(response);
}

export async function startReview(sessionId: string): Promise<void> {
  const response = await fetch(`/reviews/${sessionId}/start`, { method: 'POST' });
  await jsonOrThrow<{ session_id: string; status: string }>(response);
}

export async function skipReview(sessionId: string): Promise<void> {
  const response = await fetch(`/reviews/${sessionId}/skip`, { method: 'POST' });
  await jsonOrThrow<{ session_id: string; status: string }>(response);
}

export type StreamEvent =
  | { type: 'stream_open'; thread_id: string }
  | { type: 'review_pending'; session_id: string; repository: string; pr_number: number; pr_title?: string }
  | { type: 'review_started'; session_id?: string; thread_id?: string; pr_number?: number }
  | { type: 'turn'; turn: AgentTurn }
  | { type: 'consensus_ready'; consensus: Consensus }
  | { type: 'review_completed'; session_id?: string; thread_id?: string; consensus: Consensus }
  | { type: 'review_failed'; session_id?: string; thread_id?: string }
  | { type: 'review_skipped'; session_id: string };

export function openEventStream(
  threadId: string,
  onEvent: (event: StreamEvent) => void,
): EventSource {
  const source = new EventSource(`/chat/threads/${threadId}/events`);
  source.onmessage = (msg) => {
    try {
      onEvent(JSON.parse(msg.data) as StreamEvent);
    } catch (err) {
      console.warn('SSE parse error', err);
    }
  };
  source.onerror = (err) => {
    console.warn('SSE error', err);
  };
  return source;
}
