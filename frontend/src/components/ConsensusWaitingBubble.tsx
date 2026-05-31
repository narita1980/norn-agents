import { forwardRef } from 'react';
import type { AgentTurn } from '../lib/api';
import type { ConsensusStatus } from '../hooks/useThreadConsensus';

const STEP_LABEL: Record<string, string> = {
  urd: 'Urd',
  verdandi: 'Verdandi',
  skuld: 'Skuld',
  moderator: 'Moderator',
};

type Props = {
  turns: AgentTurn[];
  status: ConsensusStatus;
  pipelineAgents: string[];
};

export const ConsensusWaitingBubble = forwardRef<HTMLLIElement, Props>(function ConsensusWaitingBubble(
  { turns, status, pipelineAgents },
  ref,
) {
  if (status !== 'streaming') return null;

  const order = pipelineAgents.length > 0 ? pipelineAgents : [];
  const completed = new Set(turns.map((t) => t.agent));
  const activeAgent = order.find((agent) => !completed.has(agent)) ?? null;
  const isFullPipeline = order.length >= 4;

  const isCompanionOnly = order.length === 1 && order[0] === 'verdandi';

  const hint =
    order.length === 0
      ? '応答方針を決めています…'
      : isCompanionOnly
        ? 'Verdandi が回答しています…'
        : activeAgent === 'moderator' && order.includes('moderator') && completed.size > 0
          ? 'Moderator が回答をまとめています…'
          : isFullPipeline
            ? '3 女神が合議しています…'
            : activeAgent
              ? `${STEP_LABEL[activeAgent] ?? activeAgent} が回答しています…`
              : '回答を準備しています…';

  return (
    <li ref={ref} className="message message--assistant message--pending" aria-busy="true">
      <span className="message__role">Norn</span>
      <div className="message__body">
        <p className="consensus-waiting__hint">
          <span className="consensus-waiting__pulse" aria-hidden="true" />
          {hint}
        </p>
        {order.length > 0 && (
          <ol className="consensus-waiting__steps" aria-label="応答の進行">
            {order.map((agent) => {
              const stepStatus = completed.has(agent)
                ? 'done'
                : agent === activeAgent
                  ? 'active'
                  : 'pending';
              return (
                <li
                  key={agent}
                  className={`consensus-waiting__step consensus-waiting__step--${agent} consensus-waiting__step--${stepStatus}`}
                >
                  <span className="consensus-waiting__step-label">
                    {STEP_LABEL[agent] ?? agent}
                  </span>
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </li>
  );
});
