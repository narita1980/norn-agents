# フロントエンド構成

Vite + React (TypeScript)、状態管理は **Context なし**（`App.tsx` の `useState` のみ）。URL ルーティングなし。

## 画面（`AppView`）

| 値 | 内容 |
|----|------|
| `chat` | メイン。メッセージ + 合議パネル + ツールバー |
| `about` | `AboutPage` — Norn の読み方・サービス説明 |
| `dashboard` | `Dashboard` — 組織 KPI |

`TopNav` で切替。ブランド（Norn ロゴ）クリックでも `about` へ。

## チャット画面レイアウト

```
app__body (grid: 1fr | 340px)
├── Sidebar（ドロワー、通常非表示）
├── main.chat
│   ├── chat__toolbar … 「スレッド」「新規チャット」
│   ├── MessageList
│   ├── ManualReviewForm
│   └── Composer
└── ConsensusPanel（合議ライブ）
```

- **スレッド一覧**: 初期は非表示。`chat__toolbar` の「スレッド」で左ドロワーを開く（オーバーレイ + Esc で閉じる）。スレッド選択で自動クローズ。
- **新規チャット**: ツールバーまたはドロワー内の ＋。`threadId === null` の状態。
- **スレッド削除**: ドロワー各行の × → `DELETE /chat/threads/{id}`。表示中スレッドなら `App` が state をクリア。

## 主要コンポーネントの責務

| コンポーネント | 責務 |
|----------------|------|
| `MessageList` | メッセージ表示。最新の `action_payload.type === 'start_or_skip'` にだけ `ApprovalBanner` |
| `ApprovalBanner` | `POST /reviews/{session_id}/start` or `/skip` |
| `useThreadConsensus` | SSE 購読、合議ターン・ステータス |
| `ConsensusWaitingBubble` | `streaming` 中の進行表示（`lib/personas.ts` の短縮名） |
| `ConsensusPanel` | 完了ターン一覧 + 合議サマリ |

## API クライアント（`lib/api.ts`）

| 関数 | メソッド | パス |
|------|----------|------|
| `postMessage` | POST | `/chat/messages` |
| `listThreads` | GET | `/chat/threads` |
| `getThread` | GET | `/chat/threads/{id}` |
| `deleteThread` | DELETE | `/chat/threads/{id}` |
| `openEventStream` | SSE | `/chat/threads/{id}/events` |
| `startReview` / `skipReview` | POST | `/reviews/{session_id}/start` \| `/skip` |
| `registerManualReview` | POST | `/reviews/manual` |
| `getDashboardStats` | GET | `/dashboard/stats` |

## エージェント表示名

**ユーザー向けはカタカナ。** 内部 ID（`urd` 等）は API/SSE のまま。

| ID | 表示（`lib/personas.ts`） |
|----|---------------------------|
| `urd` | ウルド（技術） |
| `verdandi` | ヴェルダンディ（共感） |
| `skuld` | スクルド（未来） |
| `moderator` | モデレーター（合議） |

新しい UI でエージェント名を出すときは `agentLabel()` / `agentShort()` を使い、文字列を直書きしない。

バックエンドの `personas.py` の `role_label` も同じ表記に揃える（DB に保存された transcript は古い表記のまま残る場合あり）。

## スタイル

単一の `styles.css`。BEM 風プレフィックス:

- `top-nav__`, `sidebar__`, `chat__`, `consensus__`, `about__`, `dashboard__`, `approval__`

エージェント色 CSS 変数: `--color-urd`, `--color-verdandi`, `--color-skuld`, `--color-moderator`

## 変更時のチェックリスト

- [ ] `bun run build` が通る
- [ ] 合議パネル・待機バブルで表示名が `personas.ts` 経由か
- [ ] About ページと実 UI の用語が一致しているか
- [ ] 新 API は `api.ts` + 必要なら `ARCHITECTURE.md` §5 を更新
