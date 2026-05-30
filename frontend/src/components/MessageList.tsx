import { useEffect, useRef } from 'react';

export type Message = {
  role: 'user' | 'assistant';
  content: string;
};

type Props = {
  messages: Message[];
};

export function MessageList({ messages }: Props) {
  const endRef = useRef<HTMLLIElement | null>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length]);

  return (
    <ul id="messages" aria-live="polite">
      {messages.map((msg, idx) => {
        const isLast = idx === messages.length - 1;
        return (
          <li
            key={idx}
            ref={isLast ? endRef : null}
            className={`message message--${msg.role}`}
          >
            <span className="message__role">{msg.role === 'user' ? 'あなた' : 'Norn'}</span>
            <div className="message__body">{msg.content}</div>
          </li>
        );
      })}
    </ul>
  );
}
