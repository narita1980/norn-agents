import { useState } from 'react';
import { switchLearner } from '../lib/session';
import { learnerByLevel, TEST_LEARNERS, type UserLevel } from '../lib/userLevels';

type Props = {
  currentLevel: UserLevel;
  username: string | null;
  onSwitched: (level: UserLevel, username: string) => void;
};

export function LearnerSwitcher({ currentLevel, username, onSwitched }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!username) return null;

  async function handleSwitch(level: UserLevel) {
    if (busy || level === currentLevel) return;
    setBusy(true);
    setError(null);
    try {
      const session = await switchLearner(level);
      onSwitched(session.user_level ?? level, session.username);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  const current = learnerByLevel(currentLevel);

  return (
    <div className="learner-switcher">
      <span className="learner-switcher__label" title={`現在: ${current.name}`}>
        {current.name}
      </span>
      <div className="learner-switcher__options" role="group" aria-label="テストユーザー切替">
        {TEST_LEARNERS.map((learner) => (
          <button
            key={learner.level}
            type="button"
            className={`learner-switcher__btn${
              learner.level === currentLevel ? ' learner-switcher__btn--active' : ''
            }`}
            disabled={busy || learner.level === currentLevel}
            title={learner.subtitle}
            onClick={() => void handleSwitch(learner.level)}
          >
            {learner.name}
          </button>
        ))}
      </div>
      {error && <p className="learner-switcher__error">{error}</p>}
    </div>
  );
}
