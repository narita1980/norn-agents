import type { UserLevel } from './userLevels';

export const SKILL_LABEL: Record<UserLevel, string> = {
  junior: '若手',
  mid: '中級',
  senior: '上級',
};

export function skillLabel(level: string): string {
  return SKILL_LABEL[level as UserLevel] ?? level;
}
