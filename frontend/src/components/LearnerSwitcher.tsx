import type { UserLevel } from '../lib/userLevels';
import { TEST_LEARNERS, learnerByLevel } from '../lib/userLevels';

type Props = {
  level: UserLevel;
  onChange: (level: UserLevel) => void;
  disabled?: boolean;
};

export function LearnerSwitcher({ level, onChange, disabled = false }: Props) {
  const active = learnerByLevel(level);

  return (
    <div className="learner-switcher" role="group" aria-label="テスト用エンジニア切替">
      <span className="learner-switcher__label">テストユーザー</span>
      <div className="learner-switcher__options">
        {TEST_LEARNERS.map((learner) => {
          const isActive = learner.level === level;
          return (
            <button
              key={learner.level}
              type="button"
              className={`learner-switcher__btn${isActive ? ' learner-switcher__btn--active' : ''}`}
              aria-pressed={isActive}
              disabled={disabled}
              title={learner.hint}
              onClick={() => onChange(learner.level)}
            >
              <span className="learner-switcher__name">{learner.name}</span>
              <span className="learner-switcher__subtitle">{learner.subtitle}</span>
            </button>
          );
        })}
      </div>
      <p className="learner-switcher__hint">{active.hint}</p>
    </div>
  );
}
