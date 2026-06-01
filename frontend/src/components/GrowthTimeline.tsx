import { useEffect, useState } from 'react';
import { getGrowthTimeline, getLearnerProfile, type GrowthTimelineEntry, type LearnerProfile } from '../lib/api';
import type { UserLevel } from '../lib/userLevels';
import { learnerByLevel } from '../lib/userLevels';

const SKILL_LABEL: Record<string, string> = {
  junior: '若手',
  mid: '中級',
  senior: '上級',
};

type Props = {
  userLevel: UserLevel;
};

export function GrowthTimeline({ userLevel }: Props) {
  const [profile, setProfile] = useState<LearnerProfile | null>(null);
  const [entries, setEntries] = useState<GrowthTimelineEntry[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getLearnerProfile(userLevel), getGrowthTimeline(userLevel)])
      .then(([p, timeline]) => {
        if (!cancelled) {
          setProfile(p);
          setEntries(timeline);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      });
    return () => {
      cancelled = true;
    };
  }, [userLevel]);

  if (error) {
    return <p className="growth-timeline__error">{error}</p>;
  }

  if (!profile) {
    return <p className="growth-timeline__loading">成長データを読み込み中…</p>;
  }

  return (
    <section className="growth-timeline">
      <h3 className="growth-timeline__title">
        {learnerByLevel(userLevel).name}の成長記録
      </h3>
      <div className="growth-timeline__profile">
        <p>
          <strong>推定スキル:</strong> {SKILL_LABEL[profile.skill_level] ?? profile.skill_level}
          {' · '}
          <strong>レビュー回数:</strong> {profile.review_count}
        </p>
        {profile.growth_summary && (
          <p className="growth-timeline__summary">{profile.growth_summary}</p>
        )}
        {profile.active_goals.length > 0 && (
          <div>
            <strong>学習目標</strong>
            <ul>
              {profile.active_goals.map((goal) => (
                <li key={goal}>{goal}</li>
              ))}
            </ul>
          </div>
        )}
        {profile.weak_areas.length > 0 && (
          <div>
            <strong>改善中の領域</strong>
            <ul>
              {profile.weak_areas.map((area) => (
                <li key={area}>{area}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
      {entries.length > 0 && (
        <ol className="growth-timeline__list">
          {entries.map((entry) => (
            <li key={entry.message_id ?? entry.created_at} className="growth-timeline__item">
              <time className="growth-timeline__when">{formatWhen(entry.created_at)}</time>
              {entry.growth && <p className="growth-timeline__growth">{entry.growth}</p>}
              {entry.summary && <p className="growth-timeline__excerpt">{entry.summary}</p>}
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}

function formatWhen(iso: string | null): string {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleString('ja-JP', { dateStyle: 'short', timeStyle: 'short' });
  } catch {
    return iso;
  }
}
