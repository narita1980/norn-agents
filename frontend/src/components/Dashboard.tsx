import { useEffect, useState } from 'react';
import { PRODUCT_NAME_EN } from '../lib/brand';
import { GrowthTimeline } from './GrowthTimeline';
import { getDashboardStats, type DashboardStats } from '../lib/api';
import type { UserLevel } from '../lib/userLevels';
import { TEST_LEARNERS } from '../lib/userLevels';

const TONE_LABEL: Record<string, string> = {
  encouraging: '励まし',
  neutral: '中立',
  cautious: '慎重',
};

const SKILL_LABEL: Record<string, string> = {
  junior: '若手',
  mid: '中級',
  senior: '上級',
};

export function Dashboard({ userLevel = 'junior' }: { userLevel?: UserLevel }) {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getDashboardStats()
      .then((data) => {
        if (!cancelled) setStats(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <section className="dashboard">
        <h2 className="dashboard__title">組織の成長ダッシュボード</h2>
        <p className="dashboard__error">{error}</p>
      </section>
    );
  }

  if (!stats) {
    return (
      <section className="dashboard">
        <h2 className="dashboard__title">組織の成長ダッシュボード</h2>
        <p className="dashboard__loading">読み込み中…</p>
      </section>
    );
  }

  const toneTotal = Object.values(stats.by_tone).reduce((a, b) => a + b, 0);
  const toneEntries = Object.entries(stats.by_tone);

  return (
    <section className="dashboard">
      <h2 className="dashboard__title">組織の成長ダッシュボード</h2>
      <p className="dashboard__caption">
        {PRODUCT_NAME_EN} の合議が若手の成長とシニアの工数削減にどのくらい寄与しているかを可視化します。数値は実
        DB の統計とモック KPI の合算です。
      </p>

      <div className="dashboard__kpis">
        <article className="kpi">
          <span className="kpi__label">完了レビュー</span>
          <span className="kpi__value">{stats.sessions.completed}</span>
          <span className="kpi__sub">/ 累計 {stats.sessions.total}</span>
        </article>
        <article className="kpi kpi--accent">
          <span className="kpi__label">シニア工数の節約（推定）</span>
          <span className="kpi__value">{stats.mock.estimated_senior_hours_saved}h</span>
          <span className="kpi__sub">1 PR = 30 分換算</span>
        </article>
        <article className="kpi">
          <span className="kpi__label">若手の学習時間（推定）</span>
          <span className="kpi__value">{stats.mock.learning_minutes_total} min</span>
          <span className="kpi__sub">1 PR = 12 分換算</span>
        </article>
        <article className="kpi">
          <span className="kpi__label">レビュー採用率</span>
          <span className="kpi__value">{Math.round(stats.mock.completion_rate * 100)}%</span>
          <span className="kpi__sub">完了 / (完了+スキップ+失敗)</span>
        </article>
      </div>

      <div className="dashboard__columns">
        <article className="panel">
          <h3 className="panel__title">セッション状態</h3>
          <StatusBar label="完了" value={stats.sessions.completed} total={stats.sessions.total} tone="ok" />
          <StatusBar label="合議中" value={stats.sessions.running} total={stats.sessions.total} tone="running" />
          <StatusBar label="承認待ち" value={stats.sessions.pending} total={stats.sessions.total} tone="pending" />
          <StatusBar label="スキップ" value={stats.sessions.skipped} total={stats.sessions.total} tone="skipped" />
          <StatusBar label="失敗" value={stats.sessions.failed} total={stats.sessions.total} tone="failed" />
        </article>

        <article className="panel">
          <h3 className="panel__title">レビューのトーン</h3>
          {toneEntries.length === 0 ? (
            <p className="panel__empty">まだ集計データがありません。</p>
          ) : (
            toneEntries.map(([tone, count]) => (
              <StatusBar
                key={tone}
                label={TONE_LABEL[tone] ?? tone}
                value={count}
                total={toneTotal}
                tone={`tone-${tone}`}
              />
            ))
          )}
        </article>
      </div>

      <article className="panel">
        <h3 className="panel__title">最近の完了レビュー</h3>
        {stats.recent.length === 0 ? (
          <p className="panel__empty">まだ完了したレビューはありません。</p>
        ) : (
          <ul className="recent">
            {stats.recent.map((row) => (
              <li key={row.session_id} className="recent__item">
                <span className="recent__repo">{row.repository}</span>
                <span className="recent__pr">#{row.pr_number}</span>
                <span className="recent__when">{formatWhen(row.updated_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </article>

      {stats.learners && stats.learners.length > 0 && (
        <article className="panel">
          <h3 className="panel__title">若手のスキル推移（自動推定）</h3>
          <ul className="learner-stats">
            {stats.learners.map((learner) => {
              const label =
                TEST_LEARNERS.find((l) => l.level === learner.user_level)?.name ??
                learner.user_level;
              return (
                <li key={learner.user_level} className="learner-stats__item">
                  <span className="learner-stats__name">{label}</span>
                  <span className="learner-stats__skill">
                    {SKILL_LABEL[learner.skill_level] ?? learner.skill_level}
                  </span>
                  <span className="learner-stats__count">{learner.review_count} 回</span>
                  {learner.weak_areas.length > 0 && (
                    <span className="learner-stats__weak">
                      弱点: {learner.weak_areas.join('、')}
                    </span>
                  )}
                </li>
              );
            })}
          </ul>
        </article>
      )}

      <GrowthTimeline userLevel={userLevel} />
    </section>
  );
}

function StatusBar({
  label,
  value,
  total,
  tone,
}: {
  label: string;
  value: number;
  total: number;
  tone: string;
}) {
  const pct = total > 0 ? Math.round((value / total) * 100) : 0;
  return (
    <div className="bar">
      <div className="bar__label">
        <span>{label}</span>
        <span className="bar__count">
          {value} <span className="bar__pct">({pct}%)</span>
        </span>
      </div>
      <div className={`bar__track bar__track--${tone}`}>
        <div className="bar__fill" style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

function formatWhen(iso: string | null): string {
  if (!iso) return '';
  try {
    const dt = new Date(iso);
    return dt.toLocaleString('ja-JP', { dateStyle: 'short', timeStyle: 'short' });
  } catch {
    return iso;
  }
}
