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
  user_level?: 'junior' | 'mid' | 'senior';
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

/** SWA + 別オリジン API 時はビルド時に VITE_API_BASE_URL を設定。未設定なら同一オリジン。 */
const API_BASE = (import.meta.env.VITE_API_BASE_URL as string | undefined)?.replace(/\/$/, '') ?? '';
const CROSS_ORIGIN_API = API_BASE.length > 0;

function apiUrl(path: string): string {
  return `${API_BASE}${path}`;
}

function withApiCredentials(init: RequestInit = {}): RequestInit {
  return CROSS_ORIGIN_API ? { ...init, credentials: 'include' } : init;
}

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
  const response = await fetch(
    apiUrl('/chat/messages'),
    withApiCredentials({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  );
  return jsonOrThrow<PostMessageResponse>(response);
}

import type { UserLevel } from './userLevels';

function userLevelQuery(level: UserLevel): string {
  return `user_level=${encodeURIComponent(level)}`;
}

export async function listThreads(userLevel: UserLevel): Promise<ThreadSummary[]> {
  const response = await fetch(
    apiUrl(`/chat/threads?${userLevelQuery(userLevel)}`),
    withApiCredentials(),
  );
  const data = await jsonOrThrow<{ threads: ThreadSummary[] }>(response);
  return data.threads;
}

export async function getThread(threadId: string, userLevel: UserLevel): Promise<ThreadDetail> {
  const response = await fetch(
    apiUrl(`/chat/threads/${threadId}?${userLevelQuery(userLevel)}`),
    withApiCredentials(),
  );
  return jsonOrThrow<ThreadDetail>(response);
}

export async function deleteThread(threadId: string, userLevel: UserLevel): Promise<void> {
  const response = await fetch(
    apiUrl(`/chat/threads/${threadId}?${userLevelQuery(userLevel)}`),
    withApiCredentials({ method: 'DELETE' }),
  );
  if (!response.ok) {
    await jsonOrThrow<never>(response);
  }
}

export async function getDashboardStats(): Promise<DashboardStats> {
  const response = await fetch(apiUrl('/dashboard/stats'), withApiCredentials());
  return jsonOrThrow<DashboardStats>(response);
}

export async function startReview(sessionId: string): Promise<void> {
  const response = await fetch(
    apiUrl(`/reviews/${sessionId}/start`),
    withApiCredentials({ method: 'POST' }),
  );
  await jsonOrThrow<{ session_id: string; status: string }>(response);
}

export async function skipReview(sessionId: string): Promise<void> {
  const response = await fetch(
    apiUrl(`/reviews/${sessionId}/skip`),
    withApiCredentials({ method: 'POST' }),
  );
  await jsonOrThrow<{ session_id: string; status: string }>(response);
}

export type ManualReviewRequest = {
  pr_ref?: string;
  repository?: string;
  pr_number?: number;
  thread_id?: string;
  user_level?: 'junior' | 'mid' | 'senior';
};

export type ManualReviewResponse = {
  session_id: string;
  thread_id: string;
  status: string;
  repository: string;
  pr_number: number;
  pr_title: string;
  pr_url?: string | null;
};

export async function registerManualReview(
  body: ManualReviewRequest,
): Promise<ManualReviewResponse> {
  const response = await fetch(
    apiUrl('/reviews/manual'),
    withApiCredentials({
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }),
  );
  return jsonOrThrow<ManualReviewResponse>(response);
}

export type ConsensusPipelineMode = 'full_consensus' | 'single_agent' | 'out_of_scope';

export type StreamEvent =
  | { type: 'stream_open'; thread_id: string }
  | { type: 'review_pending'; session_id: string; repository: string; pr_number: number; pr_title?: string }
  | { type: 'review_started'; session_id?: string; thread_id?: string; pr_number?: number }
  | {
      type: 'routing_decided';
      mode: ConsensusPipelineMode;
      agents: string[];
    }
  | { type: 'turn'; turn: AgentTurn }
  | { type: 'consensus_ready'; consensus: Consensus }
  | { type: 'review_completed'; session_id?: string; thread_id?: string; consensus: Consensus }
  | { type: 'review_failed'; session_id?: string; thread_id?: string }
  | { type: 'review_skipped'; session_id: string };

export function openEventStream(
  threadId: string,
  onEvent: (event: StreamEvent) => void,
): EventSource {
  const url = apiUrl(`/chat/threads/${threadId}/events`);
  const source = CROSS_ORIGIN_API
    ? new EventSource(url, { withCredentials: true })
    : new EventSource(url);
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
