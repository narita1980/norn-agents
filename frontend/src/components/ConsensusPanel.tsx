import { useEffect, useRef } from 'react';
import type { AgentTurn, Consensus } from '../lib/api';
import {
  activeConsensusAgents,
  agentDeliberationHint,
  agentLabel,
  agentShort,
  parallelSpeakingHint,
  PARALLEL_DELIBERATION_AGENTS,
  sortTurnsByAgent,
} from '../lib/personas';
import type { ConsensusStatus } from '../hooks/useThreadConsensus';

type Props = {
  threadId: string | null;
  turns: AgentTurn[];
  consensus: Consensus | null;
  status: ConsensusStatus;
  pipelineAgents?: string[];
};

export function ConsensusPanel({
  threadId,
  turns,
  consensus,
  status,
  pipelineAgents = [],
}: Props) {
  const endRef = useRef<HTMLLIElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [turns.length, status, pipelineAgents.length]);

  if (!threadId) {
    return (
      <section className="consensus consensus--empty">
        <h2 className="consensus__title">合議ライブ</h2>
        <p className="consensus__hint">スレッドを選ぶと、3 女神が会話しながら合議する様子がリアルタイムに流れます。</p>
      </section>
    );
  }

  const order = pipelineAgents.length > 0 ? pipelineAgents : [];
  const completed = new Set(turns.map((t) => t.agent));
  const activeAgents = activeConsensusAgents(order, completed, status === 'streaming');
  const visibleTurns = sortTurnsByAgent(turns.filter((turn) => !isLegacyModeratorJson(turn)));
  const isParallelPhase = activeAgents.some((agent) =>
    (PARALLEL_DELIBERATION_AGENTS as readonly string[]).includes(agent),
  );

  return (
    <section className="consensus">
      <header className="consensus__header">
        <h2 className="consensus__title">合議ライブ</h2>
        <span className={`consensus__status consensus__status--${status}`}>
          {statusLabel(status)}
        </span>
      </header>
      {order.length >= 4 && (
        <ol className="consensus__pipeline" aria-label="合議の進行">
          <li className="consensus__pipeline-parallel" aria-label="並行合議">
            {PARALLEL_DELIBERATION_AGENTS.filter((agent) => order.includes(agent)).map((agent) => {
              const stepStatus = completed.has(agent)
                ? 'done'
                : activeAgents.includes(agent)
                  ? 'active'
                  : 'pending';
              return (
                <span
                  key={agent}
                  className={`consensus__pipeline-step consensus__pipeline-step--${agent} consensus__pipeline-step--${stepStatus}`}
                >
                  <span className="consensus__pipeline-label">{agentShort(agent)}</span>
                </span>
              );
            })}
          </li>
          {order
            .filter((agent) => !(PARALLEL_DELIBERATION_AGENTS as readonly string[]).includes(agent))
            .map((agent) => {
              const stepStatus = completed.has(agent)
                ? 'done'
                : activeAgents.includes(agent)
                  ? 'active'
                  : 'pending';
              return (
                <li
                  key={agent}
                  className={`consensus__pipeline-step consensus__pipeline-step--${agent} consensus__pipeline-step--${stepStatus}`}
                >
                  <span className="consensus__pipeline-label">{agentShort(agent)}</span>
                </li>
              );
            })}
        </ol>
      )}
      {visibleTurns.length === 0 && status !== 'streaming' && (
        <p className="consensus__hint">まだ発言がありません。合議が始まると、女神同士のやり取りがここに並びます。</p>
      )}
      {visibleTurns.length === 0 && status === 'streaming' && (
        <p className="consensus__hint">
          {activeAgents.length > 0 ? parallelSpeakingHint(activeAgents) : '合議を開始しています…'}
        </p>
      )}
      <ul className="consensus__turns">
        {visibleTurns.map((turn, idx) => {
          const turnClass = turn.agent === 'companion' ? 'companion' : turn.agent;
          const replyHint = agentDeliberationHint(turn.agent);
          const quoteTurns =
            turn.agent === 'verdandi'
              ? visibleTurns.slice(0, idx).filter((t) => t.agent === 'urd' || t.agent === 'skuld')
              : [];
          return (
            <li
              key={`${turn.agent}-${idx}`}
              className={`turn turn--${turnClass}`}
              ref={idx === visibleTurns.length - 1 && activeAgents.length === 0 ? endRef : null}
            >
              <div className="turn__header">
                <span className="turn__avatar" aria-hidden="true">
                  {agentShort(turn.agent).slice(0, 1)}
                </span>
                <div className="turn__meta">
                  <span className="turn__role">{agentLabel(turn.agent, turn.role_label)}</span>
                  {replyHint && (
                    <span className="turn__context">{replyHint}</span>
                  )}
                </div>
              </div>
              {quoteTurns.map((quoted) => (
                <blockquote key={quoted.agent} className="turn__quote">
                  <span className="turn__quote-label">{agentShort(quoted.agent)} → ヴェルダンディ:</span>
                  {excerpt(quoted.content)}
                </blockquote>
              ))}
              <div className="turn__body">{turn.content}</div>
            </li>
          );
        })}
        {activeAgents.map((agent) => (
          <li
            key={`typing-${agent}`}
            ref={agent === activeAgents[activeAgents.length - 1] ? endRef : null}
            className={`turn turn--${agent} turn--typing${isParallelPhase ? ' turn--parallel' : ''}`}
            aria-busy="true"
          >
            <div className="turn__header">
              <span className="turn__avatar" aria-hidden="true">
                {agentShort(agent).slice(0, 1)}
              </span>
              <div className="turn__meta">
                <span className="turn__role">{agentLabel(agent)}</span>
                <span className="turn__context">
                  {isParallelPhase && activeAgents.length >= 2
                    ? parallelSpeakingHint(activeAgents)
                    : parallelSpeakingHint([agent])}
                </span>
              </div>
            </div>
            <div className="turn__typing" aria-hidden="true">
              <span />
              <span />
              <span />
            </div>
          </li>
        ))}
      </ul>
      {consensus && (
        <div className="consensus__summary">
          <strong>合議結果（{consensus.tone}）:</strong>
          <p>{consensus.summary}</p>
        </div>
      )}
    </section>
  );
}

function statusLabel(status: ConsensusStatus): string {
  switch (status) {
    case 'streaming':
      return '合議中…';
    case 'completed':
      return '完了';
    case 'failed':
      return '失敗';
    case 'skipped':
      return 'スキップ';
    default:
      return '待機中';
  }
}

function excerpt(text: string, maxLen = 72): string {
  const oneLine = text.replace(/\s+/g, ' ').trim();
  if (oneLine.length <= maxLen) return oneLine;
  return `${oneLine.slice(0, maxLen)}…`;
}

function isLegacyModeratorJson(turn: AgentTurn): boolean {
  if (turn.agent !== 'moderator') return false;
  const trimmed = turn.content.trim();
  return trimmed.startsWith('{') && trimmed.includes('"summary"');
}
