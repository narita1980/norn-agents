import { useEffect, useRef, useState } from 'react';
import { PRODUCT_NAME_EN } from '../lib/brand';
import { ApprovalBanner } from './ApprovalBanner';
import { ChatOnboarding } from './ChatOnboarding';
import { ConsensusWaitingBubble } from './ConsensusWaitingBubble';
import { MarkdownBody } from './MarkdownBody';
import type { ActionPayload, AgentTurn } from '../lib/api';
import { postMessageFeedback } from '../lib/api';
import type { UserLevel } from '../lib/userLevels';
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
  reviewStatus?: string | null;
  showOnboarding?: boolean;
  userLevel?: UserLevel;
};

export function MessageList({
  messages,
  onActionResolved,
  consensusTurns = [],
  consensusStatus = 'idle',
  pipelineAgents = [],
  reviewStatus = null,
  showOnboarding = false,
  userLevel = 'junior',
}: Props) {
  const endRef = useRef<HTMLLIElement | null>(null);
  const isWaiting = consensusStatus === 'streaming';

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, isWaiting, consensusTurns.length, pipelineAgents.length]);

  // 最新の未解決 start_or_skip プロンプトだけアクション可能にする。
  const latestPendingIdx = findLatestPendingIndex(messages);

  const canShowApproval =
    reviewStatus === null || reviewStatus === 'pending_approval';

  return (
    <ul id="messages" className="chat__messages" aria-live="polite">
      {showOnboarding && messages.length === 0 && !isWaiting && <ChatOnboarding />}
      {messages.length === 0 && !isWaiting && !showOnboarding && (
        <li className="chat__messages-empty" aria-hidden="true">
          <p className="chat__messages-empty-title">メッセージはここに表示されます</p>
          <p className="chat__messages-empty-hint">下の入力欄から質問や相談を送ってみましょう</p>
        </li>
      )}
      {messages.map((msg, idx) => {
        const isLast = idx === messages.length - 1 && !isWaiting;
        const showApproval =
          canShowApproval &&
          idx === latestPendingIdx &&
          msg.action_payload &&
          msg.action_payload.type === 'start_or_skip';
        return (
          <li
            key={msg.message_id ?? idx}
            ref={isLast ? endRef : null}
            className={`message message--${msg.role}`}
          >
            <span className="message__role">{msg.role === 'user' ? 'あなた' : PRODUCT_NAME_EN}</span>
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
            {msg.role === 'assistant' && msg.message_id && (
              <MessageFeedback messageId={msg.message_id} userLevel={userLevel} />
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

function MessageFeedback({
  messageId,
  userLevel,
}: {
  messageId: string;
  userLevel: UserLevel;
}) {
  const [sent, setSent] = useState<'up' | 'down' | null>(null);

  async function send(rating: -1 | 1, label: 'up' | 'down') {
    if (sent) return;
    try {
      await postMessageFeedback(messageId, rating, userLevel);
      setSent(label);
    } catch (err) {
      console.warn('feedback failed', err);
    }
  }

  return (
    <div className="message__feedback" aria-label="この応答へのフィードバック">
      <button
        type="button"
        className={`message__feedback-btn${sent === 'up' ? ' message__feedback-btn--active' : ''}`}
        onClick={() => void send(1, 'up')}
        disabled={sent !== null}
        title="役に立った"
      >
        👍
      </button>
      <button
        type="button"
        className={`message__feedback-btn${sent === 'down' ? ' message__feedback-btn--active' : ''}`}
        onClick={() => void send(-1, 'down')}
        disabled={sent !== null}
        title="改善してほしい"
      >
        👎
      </button>
    </div>
  );
}
