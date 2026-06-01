import { useState, type ChangeEvent } from 'react';
import { switchLearner } from '../lib/session';
import { TEST_LEARNERS, type UserLevel } from '../lib/userLevels';

type Props = {
  currentLevel: UserLevel;
  onSwitched: (level: UserLevel, username: string) => void;
};

export function LearnerSwitcher({ currentLevel, onSwitched }: Props) {
  const [busy, setBusy] = useState(false);

  async function handleChange(event: ChangeEvent<HTMLSelectElement>) {
    const level = event.target.value as UserLevel;
    if (busy || level === currentLevel) return;
    setBusy(true);
    try {
      const session = await switchLearner(level);
      onSwitched(session.user_level ?? level, session.username);
    } catch {
      event.target.value = currentLevel;
    } finally {
      setBusy(false);
    }
  }

  return (
    <select
      className="learner-switcher__select"
      value={currentLevel}
      disabled={busy}
      aria-label="デモユーザー切替"
      onChange={(event) => void handleChange(event)}
    >
      {TEST_LEARNERS.map((learner) => (
        <option key={learner.level} value={learner.level}>
          {learner.name}（{learner.subtitle}）
        </option>
      ))}
    </select>
  );
}
