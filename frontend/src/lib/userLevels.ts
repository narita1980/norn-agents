/** テスト用エンジニアレベル（backend/norn/agents/user_levels.py と同期）。 */

export type UserLevel = 'junior' | 'mid' | 'senior';

export type TestLearner = {
  level: UserLevel;
  name: string;
  subtitle: string;
  hint: string;
};

export const TEST_LEARNERS: TestLearner[] = [
  {
    level: 'junior',
    name: 'ゆき',
    subtitle: '若手（1年目）',
    hint: '用語解説・小さなステップ多め',
  },
  {
    level: 'mid',
    name: 'たけし',
    subtitle: '中級（3年目）',
    hint: '標準のバランス',
  },
  {
    level: 'senior',
    name: 'さくら',
    subtitle: '上級（5年目）',
    hint: '簡潔・設計・トレードオフ重視',
  },
];

/** backend/norn/agents/user_levels.py TEST_LOGIN_USERS と同期 */
export const LOGIN_USERNAME_BY_LEVEL: Record<UserLevel, string> = {
  junior: 'yuki',
  mid: 'takeshi',
  senior: 'sakura',
};

export const DEFAULT_USER_LEVEL: UserLevel = 'junior';

const STORAGE_KEY = 'norn-test-learner-level';
const THREADS_STORAGE_KEY = 'norn-active-thread-by-level';

export function loadStoredUserLevel(): UserLevel {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === 'junior' || raw === 'mid' || raw === 'senior') return raw;
  } catch {
    // ignore
  }
  return DEFAULT_USER_LEVEL;
}

export function storeUserLevel(level: UserLevel): void {
  try {
    localStorage.setItem(STORAGE_KEY, level);
  } catch {
    // ignore
  }
}

type ThreadMap = Partial<Record<UserLevel, string>>;

function loadThreadMap(): ThreadMap {
  try {
    const raw = localStorage.getItem(THREADS_STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw) as unknown;
    if (typeof parsed !== 'object' || parsed === null) return {};
    return parsed as ThreadMap;
  } catch {
    return {};
  }
}

function saveThreadMap(map: ThreadMap): void {
  try {
    localStorage.setItem(THREADS_STORAGE_KEY, JSON.stringify(map));
  } catch {
    // ignore
  }
}

export function loadStoredThreadId(level: UserLevel): string | null {
  const id = loadThreadMap()[level];
  return typeof id === 'string' && id.length > 0 ? id : null;
}

export function storeThreadId(level: UserLevel, threadId: string | null): void {
  const map = loadThreadMap();
  if (threadId) {
    map[level] = threadId;
  } else {
    delete map[level];
  }
  saveThreadMap(map);
}

export function learnerByLevel(level: UserLevel): TestLearner {
  return TEST_LEARNERS.find((l) => l.level === level) ?? TEST_LEARNERS[0];
}
