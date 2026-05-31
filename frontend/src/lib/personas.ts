/**
 * 合議エージェントの UI 表示名（内部 ID は urd / verdandi / skuld / moderator）。
 * 変更時は backend/norn/agents/personas.py の role_label も同期すること。
 * @see docs/CONVENTIONS.md
 */

export const AGENT_LABEL: Record<string, string> = {
  urd: 'ウルド（技術）',
  verdandi: 'ヴェルダンディ（共感）',
  skuld: 'スクルド（未来）',
  moderator: 'モデレーター（合議）',
};

export const AGENT_SHORT: Record<string, string> = {
  urd: 'ウルド',
  verdandi: 'ヴェルダンディ',
  skuld: 'スクルド',
  moderator: 'モデレーター',
};

export const GODDESSES_DISPLAY = 'ウルド・ヴェルダンディ・スクルド';

export function agentLabel(agent: string, fallback?: string): string {
  return AGENT_LABEL[agent] ?? fallback ?? agent;
}

export function agentShort(agent: string): string {
  return AGENT_SHORT[agent] ?? agent;
}
