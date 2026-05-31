/**
 * 合議エージェントの UI 表示名（内部 ID は urd / verdandi / skuld / moderator / companion）。
 * 変更時は backend/norn/agents/personas.py の role_label も同期すること。
 * @see docs/CONVENTIONS.md
 */

export const AGENT_LABEL: Record<string, string> = {
  urd: 'ウルド（メンター）',
  verdandi: 'ヴェルダンディ（伴走）',
  skuld: 'スクルド（キャリア）',
  moderator: 'モデレーター（合議）',
  companion: 'ヴェルダンディ（伴走）',
};

export const AGENT_SHORT: Record<string, string> = {
  urd: 'ウルド',
  verdandi: 'ヴェルダンディ',
  skuld: 'スクルド',
  moderator: 'モデレーター',
  companion: 'ヴェルダンディ（伴走）',
};

export const GODDESSES_DISPLAY = 'ウルド・ヴェルダンディ・スクルド';

export function agentLabel(agent: string, fallback?: string): string {
  if (fallback && fallback !== AGENT_LABEL[agent]) {
    return fallback;
  }
  return AGENT_LABEL[agent] ?? fallback ?? agent;
}

export function agentShort(agent: string): string {
  return AGENT_SHORT[agent] ?? agent;
}

export const FULL_CONSENSUS_PIPELINE = ['urd', 'skuld', 'verdandi', 'moderator'] as const;

/** 並行合議の第 1 段（ウルド ∥ スクルド） */
export const PARALLEL_DELIBERATION_AGENTS = ['urd', 'skuld'] as const;

export const AGENT_TURN_ORDER = [
  'urd',
  'skuld',
  'verdandi',
  'moderator',
  'companion',
] as const;

/** 合議ライブ UI 用: 各エージェントの会話上の位置づけ */
export const AGENT_DELIBERATION_HINT: Record<string, string> = {
  urd: 'ヴェルダンディ（伴走）へ（並行）',
  skuld: 'ヴェルダンディ（伴走）へ（並行）',
  verdandi: 'ウルド・スクルドを踏まえて締める',
  moderator: '3 女神の合議をまとめ',
  companion: '伴走メンターとして返答',
};

/** 合議進行中の待機メッセージ */
export const AGENT_SPEAKING_HINT: Record<string, string> = {
  urd: 'ウルドが技術面を整理しています…',
  skuld: 'スクルドがキャリア視点を整理しています…',
  verdandi: 'ヴェルダンディが二人の発言を受け、伴走の言葉にしています…',
  moderator: 'モデレーターが合議を 1 本のレビューにまとめています…',
  companion: 'ヴェルダンディ（伴走）が回答しています…',
};

export function sortTurnsByAgent<T extends { agent: string }>(turns: T[]): T[] {
  return [...turns].sort(
    (a, b) =>
      (AGENT_TURN_ORDER as readonly string[]).indexOf(a.agent) -
      (AGENT_TURN_ORDER as readonly string[]).indexOf(b.agent),
  );
}

export function activeConsensusAgents(
  order: readonly string[],
  completed: ReadonlySet<string>,
  streaming: boolean,
): string[] {
  if (!streaming || order.length === 0) return [];

  const parallelPending = PARALLEL_DELIBERATION_AGENTS.filter(
    (agent) => order.includes(agent) && !completed.has(agent),
  );
  if (parallelPending.length > 0) return [...parallelPending];

  for (const agent of order) {
    if (!completed.has(agent)) return [agent];
  }
  return [];
}

export function parallelSpeakingHint(activeAgents: readonly string[]): string {
  if (activeAgents.length >= 2) {
    return 'ウルドとスクルドが並行して分析し、ヴェルダンディへ渡す材料を揃えています…';
  }
  if (activeAgents.length === 1) {
    return agentSpeakingHint(activeAgents[0]);
  }
  return '合議を開始しています…';
}

export function agentDeliberationHint(agent: string): string | null {
  return AGENT_DELIBERATION_HINT[agent] ?? null;
}

export function agentSpeakingHint(agent: string): string {
  return AGENT_SPEAKING_HINT[agent] ?? `${agentShort(agent)}が発言しています…`;
}
