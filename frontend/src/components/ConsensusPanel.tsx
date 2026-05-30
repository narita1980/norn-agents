import { useEffect, useState } from 'react';
import { openEventStream, type AgentTurn, type Consensus, type StreamEvent } from '../lib/api';

type Props = {
  threadId: string | null;
};

type Status = 'idle' | 'streaming' | 'completed' | 'failed' | 'skipped';

const PERSONA_LABEL: Record<string, string> = {
  urd: 'Urd（技術）',
  verdandi: 'Verdandi（共感）',
  skuld: 'Skuld（未来）',
  moderator: 'Moderator（合議）',
};

export function ConsensusPanel({ threadId }: Props) {
  const [turns, setTurns] = useState<AgentTurn[]>([]);
  const [status, setStatus] = useState<Status>('idle');
  const [consensus, setConsensus] = useState<Consensus | null>(null);

  useEffect(() => {
    if (!threadId) {
      setTurns([]);
      setStatus('idle');
      setConsensus(null);
      return;
    }
    setTurns([]);
    setStatus('idle');
    setConsensus(null);

    const source = openEventStream(threadId, (event: StreamEvent) => {
      switch (event.type) {
        case 'stream_open':
          break;
        case 'review_started':
          setStatus('streaming');
          setTurns([]);
          setConsensus(null);
          break;
        case 'turn':
          setStatus('streaming');
          setTurns((prev) => [...prev, event.turn]);
          break;
        case 'consensus_ready':
          setConsensus(event.consensus);
          break;
        case 'review_completed':
          setStatus('completed');
          setConsensus(event.consensus);
          break;
        case 'review_failed':
          setStatus('failed');
          break;
        case 'review_skipped':
          setStatus('skipped');
          break;
        default:
          break;
      }
    });

    return () => {
      source.close();
    };
  }, [threadId]);

  if (!threadId) {
    return (
      <section className="consensus consensus--empty">
        <h2 className="consensus__title">合議ライブ</h2>
        <p className="consensus__hint">スレッドを選ぶと、ここに 3 女神の発言がリアルタイムに流れます。</p>
      </section>
    );
  }

  return (
    <section className="consensus">
      <header className="consensus__header">
        <h2 className="consensus__title">合議ライブ</h2>
        <span className={`consensus__status consensus__status--${status}`}>
          {statusLabel(status)}
        </span>
      </header>
      {turns.length === 0 && (
        <p className="consensus__hint">まだ発言がありません。Draft PR が届くか合議が始まると、ここに発言が並びます。</p>
      )}
      <ul className="consensus__turns">
        {turns.map((turn, idx) => (
          <li key={`${turn.agent}-${idx}`} className={`turn turn--${turn.agent}`}>
            <span className="turn__role">{PERSONA_LABEL[turn.agent] ?? turn.role_label}</span>
            <div className="turn__body">{turn.content}</div>
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

function statusLabel(status: Status): string {
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
