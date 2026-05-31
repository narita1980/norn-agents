import type { AgentTurn, Consensus } from '../lib/api';
import { agentLabel } from '../lib/personas';
import type { ConsensusStatus } from '../hooks/useThreadConsensus';

type Props = {
  threadId: string | null;
  turns: AgentTurn[];
  consensus: Consensus | null;
  status: ConsensusStatus;
};

export function ConsensusPanel({ threadId, turns, consensus, status }: Props) {
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
      {turns.length === 0 && status !== 'streaming' && (
        <p className="consensus__hint">まだ発言がありません。Draft PR が届くか合議が始まると、ここに発言が並びます。</p>
      )}
      {turns.length === 0 && status === 'streaming' && (
        <p className="consensus__hint">応答を準備しています…</p>
      )}
      <ul className="consensus__turns">
        {turns.map((turn, idx) => {
          const turnClass = turn.agent === 'companion' ? 'companion' : turn.agent;
          return (
          <li key={`${turn.agent}-${idx}`} className={`turn turn--${turnClass}`}>
            <span className="turn__role">{agentLabel(turn.agent, turn.role_label)}</span>
            <div className="turn__body">{turn.content}</div>
          </li>
          );
        })}
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
