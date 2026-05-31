import { useEffect, useRef } from 'react';
import { ApprovalBanner } from './ApprovalBanner';
import { ConsensusWaitingBubble } from './ConsensusWaitingBubble';
import { MarkdownBody } from './MarkdownBody';
import type { ActionPayload, AgentTurn } from '../lib/api';
import type { ConsensusStatus } from '../hooks/useThreadConsensus';

export type Message = {
  message_id?: string;
  role: 'user' | 'assistant';
  content: string;
  action_payload?: ActionPayload | null;
};

type Props = {
  messages: Message[];
  onActionResolved: () => void;
  consensusTurns?: AgentTurn[];
  consensusStatus?: ConsensusStatus;
  pipelineAgents?: string[];
};

export function MessageList({
  messages,
  onActionResolved,
  consensusTurns = [],
  consensusStatus = 'idle',
  pipelineAgents = [],
}: Props) {
  const endRef = useRef<HTMLLIElement | null>(null);
  const isWaiting = consensusStatus === 'streaming';

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, isWaiting, consensusTurns.length, pipelineAgents.length]);

  // 最新の未解決 start_or_skip プロンプトだけアクション可能にする。
  const latestPendingIdx = findLatestPendingIndex(messages);

  return (
    <ul id="messages" aria-live="polite">
      {messages.map((msg, idx) => {
        const isLast = idx === messages.length - 1 && !isWaiting;
        const showApproval =
          idx === latestPendingIdx &&
          msg.action_payload &&
          msg.action_payload.type === 'start_or_skip';
        return (
          <li
            key={msg.message_id ?? idx}
            ref={isLast ? endRef : null}
            className={`message message--${msg.role}`}
          >
            <span className="message__role">{msg.role === 'user' ? 'あなた' : 'Norn'}</span>
            <div className="message__body">
              {msg.role === 'assistant' ? (
                <MarkdownBody content={msg.content} />
              ) : (
                msg.content
              )}
            </div>
            {showApproval && msg.action_payload && (
              <ApprovalBanner payload={msg.action_payload} onResolved={onActionResolved} />
            )}
          </li>
        );
      })}
      {isWaiting && (
        <ConsensusWaitingBubble
          ref={endRef}
          turns={consensusTurns}
          status={consensusStatus}
          pipelineAgents={pipelineAgents}
        />
      )}
    </ul>
  );
}

function findLatestPendingIndex(messages: Message[]): number {
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i].action_payload?.type === 'start_or_skip') {
      return i;
    }
  }
  return -1;
}
