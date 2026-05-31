import { useEffect, useState } from 'react';
import { openEventStream, type AgentTurn, type Consensus, type StreamEvent } from '../lib/api';

import { FULL_CONSENSUS_PIPELINE } from '../lib/personas';

export type ConsensusStatus = 'idle' | 'streaming' | 'completed' | 'failed' | 'skipped';

const FULL_PIPELINE = [...FULL_CONSENSUS_PIPELINE] as const;

export type ConsensusSeed = {
  turns: AgentTurn[];
  consensus: Consensus | null;
  status: ConsensusStatus;
  pipelineAgents?: string[];
};

export function useThreadConsensus(
  threadId: string | null,
  seed: ConsensusSeed,
): ConsensusSeed {
  const [turns, setTurns] = useState(seed.turns);
  const [status, setStatus] = useState(seed.status);
  const [consensus, setConsensus] = useState(seed.consensus);
  const [pipelineAgents, setPipelineAgents] = useState<string[]>(
    seed.pipelineAgents ?? [...FULL_PIPELINE],
  );

  useEffect(() => {
    if (!threadId) {
      setTurns([]);
      setConsensus(null);
      setStatus('idle');
      setPipelineAgents([...FULL_PIPELINE]);
      return;
    }
    setTurns(seed.turns);
    setConsensus(seed.consensus);
    setStatus(seed.status);
    setPipelineAgents(seed.pipelineAgents ?? [...FULL_PIPELINE]);
  }, [threadId]);

  useEffect(() => {
    if (seed.status === 'idle' && seed.turns.length === 0 && seed.consensus === null) {
      return;
    }
    setTurns(seed.turns);
    setConsensus(seed.consensus);
    setStatus(seed.status);
    setPipelineAgents(seed.pipelineAgents ?? [...FULL_PIPELINE]);
  }, [seed.turns, seed.consensus, seed.status, seed.pipelineAgents]);

  useEffect(() => {
    if (!threadId) return;

    const source = openEventStream(threadId, (event: StreamEvent) => {
      switch (event.type) {
        case 'stream_open':
          break;
        case 'review_started':
          setStatus('streaming');
          setTurns([]);
          setConsensus(null);
          setPipelineAgents([]);
          break;
        case 'routing_decided':
          setStatus('streaming');
          setPipelineAgents(event.agents);
          break;
        case 'turn':
          setStatus('streaming');
          setTurns((prev) => [...prev, event.turn]);
          setPipelineAgents((prev) => {
            if (prev.includes(event.turn.agent)) return prev;
            return [...prev, event.turn.agent];
          });
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

  return { turns, consensus, status, pipelineAgents };
}
