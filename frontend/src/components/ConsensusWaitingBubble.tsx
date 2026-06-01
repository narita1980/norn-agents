import { forwardRef } from 'react';
import { PRODUCT_NAME_EN } from '../lib/brand';
import type { AgentTurn } from '../lib/api';
import {
  activeConsensusAgents,
  agentShort,
  parallelSpeakingHint,
  PARALLEL_DELIBERATION_AGENTS,
} from '../lib/personas';
import type { ConsensusStatus } from '../hooks/useThreadConsensus';

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
  const activeAgents = activeConsensusAgents(order, completed, true);

  const isCompanionOnly =
    order.length === 1 && (order[0] === 'companion' || order[0] === 'verdandi');

  const hint =
    order.length === 0
      ? '応答方針を決めています…'
      : activeAgents.length > 0
        ? parallelSpeakingHint(activeAgents)
        : '回答を準備しています…';

  const showSteps = order.length > 0;

  return (
    <li ref={ref} className="message message--assistant message--pending" aria-busy="true">
      <span className="message__role">{PRODUCT_NAME_EN}</span>
      <div className="message__body">
        <p className="consensus-waiting__hint">
          <span className="consensus-waiting__pulse" aria-hidden="true" />
          {hint}
        </p>
        {showSteps && (
          <ol className="consensus-waiting__steps" aria-label="合議の進行">
            <li className="consensus-waiting__parallel" aria-label="並行合議">
              {PARALLEL_DELIBERATION_AGENTS.filter((agent) => order.includes(agent)).map((agent) => {
                const stepStatus = completed.has(agent)
                  ? 'done'
                  : activeAgents.includes(agent)
                    ? 'active'
                    : 'pending';
                return (
                  <span
                    key={agent}
                    className={`consensus-waiting__step consensus-waiting__step--${agent} consensus-waiting__step--${stepStatus}`}
                  >
                    <span className="consensus-waiting__step-label">
                      {agentShort(agent)}
                    </span>
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
                const stepAgent = agent === 'verdandi' && isCompanionOnly ? 'companion' : agent;
                return (
                  <li
                    key={agent}
                    className={`consensus-waiting__step consensus-waiting__step--${stepAgent} consensus-waiting__step--${stepStatus}`}
                  >
                    <span className="consensus-waiting__step-label">
                      {agentShort(stepAgent)}
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
