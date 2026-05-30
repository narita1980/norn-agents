import { useEffect, useRef } from 'react';
import { ApprovalBanner } from './ApprovalBanner';
import { MarkdownBody } from './MarkdownBody';
import type { ActionPayload } from '../lib/api';

export type Message = {
  message_id?: string;
  role: 'user' | 'assistant';
  content: string;
  action_payload?: ActionPayload | null;
};

type Props = {
  messages: Message[];
  onActionResolved: () => void;
};

export function MessageList({ messages, onActionResolved }: Props) {
  const endRef = useRef<HTMLLIElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length]);

  // 最新の未解決 start_or_skip プロンプトだけアクション可能にする。
  const latestPendingIdx = findLatestPendingIndex(messages);

  return (
    <ul id="messages" aria-live="polite">
      {messages.map((msg, idx) => {
        const isLast = idx === messages.length - 1;
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
