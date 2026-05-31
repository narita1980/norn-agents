# ファイルマップ — どこを触るか

AI コーディングや機能追加時に、まずこの表を参照してください。詳細はリンク先ドキュメントを見ます。

## ドキュメント索引

| ファイル | 内容 |
|----------|------|
| [README.md](../README.md) | セットアップ・デモ手順 |
| [CLAUDE.md](../CLAUDE.md) | 開発コマンド・環境変数・最小規約 |
| [ARCHITECTURE.md](ARCHITECTURE.md) | システム構成・DB・API・SSE |
| [FRONTEND.md](FRONTEND.md) | React 画面構成・UI パターン |
| [CONVENTIONS.md](CONVENTIONS.md) | 表示名・ステータス・エラー・削除の意味 |
| [ROADMAP.md](ROADMAP.md) | フェーズ・未実装タスク |

## バックエンド（`backend/norn/`）

| やりたいこと | 主なファイル |
|--------------|--------------|
| 合議ロジック・ルーティング | `agents/orchestrator.py` |
| ペルソナ・プロンプト・`role_label` | `agents/personas.py` |
| 構造化出力スキーマ | `agents/schemas.py` |
| Azure OpenAI 呼び出し | `agents/llm.py` |
| DB モデル | `db/models.py` |
| DB 操作（スレッド削除含む） | `db/repositories.py` |
| チャット REST / DELETE スレッド | `api/routes/chat.py` |
| HITL start / skip / 手動 PR | `api/routes/reviews.py` |
| GitHub Webhook・合議バックグラウンド | `api/routes/github.py` |
| ダッシュボード統計 | `api/routes/dashboard.py` |
| SSE EventBus | `events/bus.py` |
| PR コメント Markdown | `github_tool/markdown.py` |
| 設定 | `config.py` |
| ルーター登録 | `api/main.py` |

## フロントエンド（`frontend/src/`）

| やりたいこと | 主なファイル |
|--------------|--------------|
| 画面切替・スレッド state | `App.tsx` |
| ナビ・「Norn とは」タブ | `components/TopNav.tsx` |
| サービス説明ページ | `components/AboutPage.tsx` |
| スレッド一覧（ドロワー・削除） | `components/Sidebar.tsx` |
| メッセージ・承認バナー | `components/MessageList.tsx`, `ApprovalBanner.tsx` |
| 合議ライブ | `components/ConsensusPanel.tsx`, `hooks/useThreadConsensus.ts` |
| 合議待ち UI | `components/ConsensusWaitingBubble.tsx` |
| API クライアント | `lib/api.ts` |
| **エージェント表示名（カタカナ）** | `lib/personas.ts` ← UI はここを正とする |
| 手動 PR 登録 | `components/ManualReviewForm.tsx` |
| グローバル CSS | `styles.css` |

## データの考え方（要約）

- **スレッド** = `chat_messages.thread_id`（専用テーブルなし）
- **PR レビュー** = `review_sessions` が `chat_thread_id` で 1:1 紐づくことが多い
- **スレッド削除** = 該当 `chat_messages` 全削除 + 紐づく `review_sessions` があれば削除（`delete_thread_by_id`）

## ビルド・配信

| 用途 | コマンド |
|------|----------|
| **Azure 本番 UI** | `cd frontend && bun run build:swa`（`VITE_API_BASE_URL` 設定）→ SWA デプロイ |
| **Azure 本番 API** | `backend/Dockerfile` → Container Apps（[AZURE_DEPLOY.md](hackathon/AZURE_DEPLOY.md)） |
| **ローカル一体確認** | `cd frontend && bun run build` → `backend/norn/static/`、続けて uvicorn |
| **ローカル開発** | `frontend/` で `bun dev`（API プロキシ付き） |
