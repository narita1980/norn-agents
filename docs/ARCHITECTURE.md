# プロジェクト・アーキテクチャ設計書 — Project Norns (norn-agents)

本ドキュメントは、プロジェクト「Norns（ノルンズ）」のシステム構成、データフロー、およびマルチエージェント合議プロトコルの詳細を定義する技術仕様書です。記述は **main ブランチの実装** を正とします。

---

## 1. 全体システム構成

Norns は、イベント駆動型（Event-Driven）の疎結合なアーキテクチャを採用しています。**GitHub Draft PR の Webhook をトリガー**とし、FastAPI サーバーが中継を行います。Phase 4 以降、Webhook 受信時点では合議を自動開始せず、若手の承認（Human-in-the-loop）を経てから `NornOrchestrator` が非同期で合議を実行します [1]。

LLM 呼び出しには Semantic Kernel の `AzureChatCompletion` コネクタを利用しますが、合議ロジック自体はカスタム `NornOrchestrator`（`backend/norn/agents/orchestrator.py`）が担います。レビュー結果は独自チャット UI（Vite + React）と GitHub PR コメントの両方に出力します。

**本番（Azure）** は **Static Web Apps（UI）+ Container Apps（API）** の分割構成です（[AZURE_DEPLOY.md](hackathon/AZURE_DEPLOY.md)）。**ローカル開発** は Vite dev server のプロキシ、または `bun run build` で `backend/norn/static/` に出力して FastAPI から同一オリジン配信する方式も利用できます。

```
[GitHub Draft PR opened] ──(Webhook)──> [FastAPI: Webhook + Chat REST + SSE]
                                              │
                                    ReviewSession を pending_approval で登録
                                    chat_messages に Start/Skip プロンプト
                                              │
                              (POST /reviews/{id}/start — 若手が承認)
                                              │
                                    (BackgroundTasks)
                                              ▼
[GitHub PR Comment] <──(GitHub API)── [NornOrchestrator]
[Chat UI + SSE]     <──(REST/SSE)──   ├── urd / ウルド（メンター）
  ↑ SWA または FastAPI StaticFiles      ├── skuld / スクルド（キャリア）
                                      ├── verdandi / ヴェルダンディ（伴走）
                                      └── moderator / モデレーター（合議）
```

---

## 2. コア・コンポーネント仕様

### 2.1. Webhook レシーバー (FastAPI)

GitHub Webhook イベントを安全かつ高速に受信・処理します（`backend/norn/api/routes/github.py`）。

*   **認証・検証**：GitHub Webhook のシークレット（`X-Hub-Signature-256`）の HMAC-SHA256 検証を Depends 層で強制します。
*   **トリガー条件**：`pull_request` イベントの `action == "opened"` かつ `draft == true` のとき、`ReviewSession` を `pending_approval` で作成し Start/Skip プロンプトを書き込みます。その他の `action`（`synchronize`、`ready_for_review`、`closed` 等）や非 Draft の `opened` は `202 Accepted` で受領しつつログのみ残して素通りさせます。
*   **issue_comment 再合議**：PR 上の若手リプライ（`issue_comment` イベント）をトリガーに、会話履歴を引き継いで再合議を実行します。
*   **非同期ハンドリング**：Webhook 受信後、即座に `202 Accepted` を返却します。合議本体は `BackgroundTasks` にオフロードし、Webhook タイムアウトを防止します。

### 2.2. マルチエージェント・オーケストレーター

`NornOrchestrator`（`backend/norn/agents/orchestrator.py`）が合議プロセスを管理します。

*   **Orchestration Pattern**：`urd` → `skuld` → `verdandi` → `moderator` の **固定逐次合議**（GroupChat / ラウンドロビンは使用しない）。UI 表示名は [CONVENTIONS.md](CONVENTIONS.md) 参照。
*   **LLM コネクタ**：Semantic Kernel の `AzureChatCompletion` を `AzureLLMClient`（`backend/norn/agents/llm.py`）経由で利用。`tenacity` によるリトライ付き。
*   **無限ループ防止**：1 ラウンド（4 persona × 1 ターン）で固定し、Moderator が構造化 JSON（`ConsensusOutput`）を出力して収束。
*   **イベント配信**：`run(..., on_event=...)` コールバックで各ターン完了時に dict イベントを発火。`EventBus` 経由で SSE クライアントへ配信。
*   **状態永続化**：合議ターンは SQLAlchemy 経由で `agent_conversations` テーブルに保存。実行は FastAPI プロセス内の `BackgroundTasks` で行い、外部 Agent Service は使用しない。

### 2.3. GitHub コネクター

PR のソースコード、差分（Diff）、およびコミット情報を取得し、エージェントが理解できるコンテキストに整形します（`backend/norn/github_tool/`）。

*   **静的解析統合**：コード差分を LLM に渡す前に `Ruff` を実行し、警告情報をメタデータとして付与します [3]。
*   **レビューコメント送信**：合議結果を Draft PR のレビューコメントとしてマークダウンで投稿します。チャット UI へのリンク（`NORN_APP_BASE_URL`）を含めます。

### 2.4. チャット UI (Vite + React)

Vite + React (TypeScript) で実装し、bun でビルドする独自チャット UI です。リポジトリは `backend/`（Python）と `frontend/`（React）の 2 ワークスペース構成です。

| 環境 | UI 配信 | API 接続 |
|------|---------|----------|
| **Azure 本番** | Static Web Apps（`bun run build:swa` → `frontend/dist`） | `VITE_API_BASE_URL` + CORS + `credentials: 'include'` |
| **ローカル開発** | Vite dev server (5173) | プロキシで FastAPI (8000) へ転送 |
| **一体確認** | `bun run build` → `backend/norn/static/` | FastAPI `StaticFiles` で同一オリジン |
| **Docker（API のみ）** | SWA または `bun dev` | Container / ローカル API を直接呼び出し |

*   **スレッド管理**：`thread_id` 単位（専用テーブルなし）。一覧は左ドロワー（通常非表示）、`DELETE /chat/threads/{id}` でメッセージ + 紐づく `ReviewSession` を削除。
*   **画面**：`chat` / `about`（Norns とは）/ `dashboard` — 詳細は [FRONTEND.md](FRONTEND.md)。
*   **REST API**：`lib/api.ts` 経由。スレッド CRUD・レビュー start/skip・手動 PR 登録。
*   **ライブ合議**：`ConsensusPanel` + SSE。表示名は `frontend/src/lib/personas.ts`。
*   **HITL**：`ApprovalBanner` → `POST /reviews/{id}/start` / `/skip`（`pending_approval` のみ。409 の意味は [CONVENTIONS.md](CONVENTIONS.md)）。
*   **開発時のプロキシ**：Vite (5173) → FastAPI (8000) の `/chat` `/webhook` `/reviews` `/dashboard` 等。
*   **セッションログイン**：ログイン ID/パスワードは `users` テーブル（bcrypt ハッシュ）のみ。`POST /auth/login` で JWT Cookie を発行し `/chat` `/reviews` `/dashboard` を常に保護（`SessionAuthMiddleware`）。UI は `LoginGate`（yuki/takeshi/sakura クイック選択）。デモユーザ seed: `uv run python -m norn.cli seed-test-users`（共通パスワード **`norn-demo`**）。LearnerSwitcher 切替: `POST /auth/switch-learner`（JWT を対応ユーザに再発行）。`/webhook/*` `/healthz` `/readyz` `/auth/*` は middleware 除外。

---

## 3. マルチエージェント合議プロトコル（3 女神合議）

Norns の最大の特徴である「3 女神の合議」は、以下のステップに従って決定論的かつ協調的に実行されます。

```
[GitHub Diff + Ruff] ──> (1. 解析) ──> [Urd (メンター)] ──> (指摘事項)
                                           │
                                       (2. 合議) ──> [Skuld (キャリア)] ──> (成長・学習提案)
                                           │
                                       (3. 伴走) ──> [Verdandi (伴走)] ──> (トーン調整・合議締め)
                                           │
                                           ▼
                                 [Consensus Moderator] ──> (4. 最終要約) ──> [Chat UI / GitHub PR Comment]
```

### 合議ステップ詳細

| ステップ | 担当エージェント | 処理内容 | 技術的アプローチ |
| :--- | :--- | :--- | :--- |
| **1. 技術解析** | **ウルド（メンター）** `urd` | コード差分を読み込み、バグ、脆弱性、パフォーマンス、設計規約違反を抽出。 | Ruff の出力をベースに、厳格なコードレビュープロンプトを適用。 |
| **2. キャリア・成長拡張** | **スクルド（キャリア）** `skuld` | ウルドの指摘を踏まえ、学習リソース・成長機会・キャリア視点を提案。 | プロンプト生成（RAG は未実装 — §7）。 |
| **3. 伴走・トーン調整** | **ヴェルダンディ（伴走）** `verdandi` | ウルドとスクルドの発言を統合し、若手が挫折しないよう「言い方」を調整して合議を締める。 | 心理的安全性に基づくトーン調整 [4]。 |
| **4. 合意形成と要約** | **モデレーター（合議）** `moderator` | 3 視点を要約し、チャット / GitHub 用 JSON を生成。 | `ConsensusOutput` で 1 ラウンド収束。 |

---

## 4. データベース設計（スキーマ）

会話履歴およびレビューセッションを管理するコアテーブル設計です（`backend/norn/db/models.py`）。Postgres 互換を保つため JSON / `DateTime(timezone=True)` / `String(36)` UUID を使用します。

### 4.1. `review_sessions` テーブル

PR ごとのレビューセッションを追跡します。チャット UI スレッドと 1:1 です。

*   `id` (String(36), Primary Key — UUID)
*   `repository_name` (String(255))
*   `pr_number` (Integer)
*   `user_level` (String(16): `junior` / `mid` / `senior` — テストユーザー別。`(repository_name, pr_number, user_level)` で一意)
*   `chat_thread_id` (String(36), Unique)
*   `status` (String(32): `pending_approval` / `running` / `completed` / `failed` / `skipped`)
*   `payload_json` (JSON, nullable — HITL で `/start` 時に再生する webhook payload)
*   `created_at` (DateTime with timezone)
*   `updated_at` (DateTime with timezone)

### 4.2. `agent_conversations` テーブル

合議中の 1 ターン分の永続化レコードです。

*   `id` (Integer, Primary Key, autoincrement)
*   `session_id` (String(36), Foreign Key to `review_sessions`)
*   `agent_name` (String(64): `urd`, `verdandi`, `skuld`, `moderator`)
*   `role_label` (String(128))
*   `message_content` (Text)
*   `created_at` (DateTime with timezone)

### 4.3. `chat_messages` テーブル

チャット UI の 1 メッセージ（`user` / `assistant`）。

*   `id` (Integer, Primary Key, autoincrement)
*   `message_id` (String(36), Unique)
*   `thread_id` (String(36))
*   `role` (String(16))
*   `content` (Text)
*   `consensus_json` (JSON, nullable — 合議結果の構造化データ)
*   `transcript_json` (JSON, nullable — 合議トランスクリプト)
*   `action_payload` (JSON, nullable — HITL の Start/Skip ボタン等)
*   `created_at` (DateTime with timezone)

### 4.4. `users` テーブル

ログイン認証用。テストユーザーは `user_level` で LearnerSwitcher と 1:1。

*   `id` (Integer, Primary Key, autoincrement)
*   `username` (String(64), Unique)
*   `password_hash` (String(255))
*   `user_level` (String(16), nullable, Unique — `junior` / `mid` / `senior`。管理者は NULL 可)
*   `created_at` (DateTime with timezone)

---

## 5. REST API 一覧

| Method | Path | 用途 |
|--------|------|------|
| POST | `/webhook/github` | GitHub Webhook 受信 |
| POST | `/chat/messages` | チャットメッセージ送信 |
| GET | `/chat/threads` | スレッド一覧 |
| GET | `/chat/threads/{thread_id}` | スレッド詳細・メッセージ履歴 |
| GET | `/chat/threads/{thread_id}/events` | SSE ライブ合議ストリーム |
| DELETE | `/chat/threads/{thread_id}` | スレッド削除（メッセージ + 紐づく ReviewSession） |
| POST | `/reviews/manual` | 手動 PR 登録（Webhook なし） |
| POST | `/reviews/{session_id}/start` | HITL — 合議開始（`pending_approval` のみ） |
| POST | `/reviews/{session_id}/skip` | HITL — 今回スキップ（`pending_approval` のみ） |
| GET | `/dashboard/stats` | 成長ダッシュボード統計 |
| GET | `/healthz` | ライブネスチェック |
| GET | `/readyz` | レディネスチェック（現状は常に `ok` — §7 参照） |
| POST | `/auth/login` | ログイン（JWT Cookie 発行） |
| POST | `/auth/logout` | ログアウト |
| GET | `/auth/session` | セッション確認（`username`, `user_level`） |
| POST | `/auth/switch-learner` | テストユーザー切替（JWT 再発行） |

---

## 6. ライブ配信プロトコル (SSE) と Human-in-the-loop

Phase 4 で導入されたデモ演出は、以下のイベントを `GET /chat/threads/{thread_id}/events` (`text/event-stream`) でクライアントへストリーミングします。

| イベント type | 発火タイミング | ペイロード抜粋 |
| :-- | :-- | :-- |
| `stream_open` | SSE 接続確立直後 | `thread_id` |
| `review_pending` | Draft PR opened の Webhook 受信時 | `session_id`, `repository`, `pr_number`, `pr_title` |
| `review_started` | `POST /reviews/{id}/start` 受領後 | `session_id`, `pr_number` |
| `turn` | 各エージェント / Moderator のターン完了直後 | `turn.agent`, `turn.role_label`, `turn.content` |
| `consensus_ready` | Moderator JSON 出力完了直後 | `consensus`（ConsensusOutput） |
| `review_completed` | DB 反映 + PR コメント送信完了 | `session_id`, `consensus` |
| `review_failed` | 合議パイプラインで例外 | `session_id` |
| `review_skipped` | `POST /reviews/{id}/skip` 後 | `session_id` |

サーバ側は `norn.events.bus.EventBus` の in-memory pub-sub で配信。**uvicorn `--workers 1`** が前提です。

Human-in-the-loop の状態遷移は `ReviewSession.status` を以下のとおり扱います。

```
[Draft PR opened] ─> pending_approval ─(POST /reviews/{id}/start)─> running ─> completed / failed
                              │
                              └─(POST /reviews/{id}/skip)─> skipped
```

`pending_approval` の状態では `chat_messages.action_payload = {"type":"start_or_skip", ...}` が 1 件書き込まれ、フロントは最新の未解決プロンプトに `[開始する] [今回はスキップ]` を提示します。

---

## 7. 将来フェーズ（未実装）

以下は設計上の候補であり、**現時点のコードベースには含まれません**（ROADMAP Phase 5 参照）。

| 項目 | 概要 |
|------|------|
| `users` テーブル拡張 | `github_username` 等による本番プロファイル管理（`user_level` 列はテストユーザー連携済み） |
| Skuld RAG | ベクトル DB / 社内 Wiki から学習リソースを検索・付与 |
| Redis EventBus | マルチワーカー運用時の SSE イベント配信（現状 in-memory） |
| `pending_approval` TTL | 放置された承認待ちセッションの自動失効 |
| Azure Blob Storage | 添付ファイル・ログのアーカイブ |
| AST 静的解析 | Ruff 以外の構造解析 |
| readyz 深いチェック | DB 接続 / Azure OpenAI / GitHub API 到達性の検証 |
| PostgreSQL 本番対応 | `asyncpg` 依存追加、本番 `DATABASE_URL` 運用 |

---

## 8. 参考文献

[1] Microsoft, "Semantic Kernel: Integrate cutting-edge LLM technology quickly and easily into your apps."  
[2] SecondTalent, "How Enterprises Are Using AutoGen in 2026," May 2026.  
[3] Reddit, "My Hackathon Project's Near-Death Experience with AI Agents," September 2025.  
[4] Forbes, "Why Psychological Safety Matters More In AI-Enabled Teams," May 2026.
