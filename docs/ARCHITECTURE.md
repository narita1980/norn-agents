# プロジェクト・アーキテクチャ設計書 — Project Norn (norn-agents)

本ドキュメントは、プロジェクト「Norn（ノルン）」のシステム構成、データフロー、およびマルチエージェント合議プロトコルの詳細を定義する技術仕様書です。記述は **main ブランチの実装** を正とします。

---

## 1. 全体システム構成

Norn は、イベント駆動型（Event-Driven）の疎結合なアーキテクチャを採用しています。**GitHub Draft PR の Webhook をトリガー**とし、FastAPI サーバーが中継を行います。Phase 4 以降、Webhook 受信時点では合議を自動開始せず、若手の承認（Human-in-the-loop）を経てから `NornOrchestrator` が非同期で合議を実行します [1]。

LLM 呼び出しには Semantic Kernel の `AzureChatCompletion` コネクタを利用しますが、合議ロジック自体はカスタム `NornOrchestrator`（`backend/norn/agents/orchestrator.py`）が担います。レビュー結果は FastAPI が同一オリジンで配信する独自チャット UI（Vite + React, StaticFiles 経由）と GitHub PR コメントの両方に出力します。

```
[GitHub Draft PR opened] ──(Webhook)──> [FastAPI: Webhook + Chat REST + Static Hosting]
                                              │
                                    ReviewSession を pending_approval で登録
                                    chat_messages に Start/Skip プロンプト
                                              │
                              (POST /reviews/{id}/start — 若手が承認)
                                              │
                                    (BackgroundTasks)
                                              ▼
[GitHub PR Comment] <──(GitHub API)── [NornOrchestrator]
[Chat UI + SSE]     <──(REST/SSE)──   ├── Urd (技術)
                                      ├── Verdandi (共感)
                                      ├── Skuld (未来)
                                      └── Moderator (要約)
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

*   **Orchestration Pattern**：Urd → Verdandi → Skuld → Moderator の **固定逐次合議**（GroupChat / ラウンドロビンは使用しない）。
*   **LLM コネクタ**：Semantic Kernel の `AzureChatCompletion` を `AzureLLMClient`（`backend/norn/agents/llm.py`）経由で利用。`tenacity` によるリトライ付き。
*   **無限ループ防止**：1 ラウンド（4 persona × 1 ターン）で固定し、Moderator が構造化 JSON（`ConsensusOutput`）を出力して収束。
*   **イベント配信**：`run(..., on_event=...)` コールバックで各ターン完了時に dict イベントを発火。`EventBus` 経由で SSE クライアントへ配信。
*   **状態永続化**：合議ターンは SQLAlchemy 経由で `agent_conversations` テーブルに保存。実行は FastAPI プロセス内の `BackgroundTasks` で行い、外部 Agent Service は使用しない。

### 2.3. GitHub コネクター

PR のソースコード、差分（Diff）、およびコミット情報を取得し、エージェントが理解できるコンテキストに整形します（`backend/norn/github_tool/`）。

*   **静的解析統合**：コード差分を LLM に渡す前に `Ruff` を実行し、警告情報をメタデータとして付与します [3]。
*   **レビューコメント送信**：合議結果を Draft PR のレビューコメントとしてマークダウンで投稿します。チャット UI へのリンク（`NORN_APP_BASE_URL`）を含めます。

### 2.4. チャット UI (Vite + React)

Vite + React (TypeScript) で実装し、bun でビルドする独自チャット UI です。ビルド出力は `backend/norn/static/` に配置され、FastAPI の `StaticFiles` 経由で API と同一オリジンで配信されます。リポジトリは `backend/`（Python）と `frontend/`（React）の 2 ワークスペース構成です。

*   **スレッド管理**：PR ごとの対話を `thread_id` 単位で保持し、チャット UI 上で完結させる。
*   **REST API**：`POST /chat/messages`、`GET /chat/threads`、`GET /chat/threads/{thread_id}` 経由でバックエンドと通信。
*   **ライブ合議**：右パネル `ConsensusPanel` が SSE（`GET /chat/threads/{thread_id}/events`）で Urd / Verdandi / Skuld / Moderator の発言を順に描画。
*   **HITL**：`ApprovalBanner` から `POST /reviews/{id}/start` / `/skip` を呼び出す。
*   **開発時のプロキシ**：Vite dev server (port 5173) が `/chat`、`/webhook`、`/reviews`、`/dashboard`、`/healthz`、`/readyz` を FastAPI (port 8000) にプロキシすることで、CORS 設定なしに同一オリジンの開発体験を保ちます。

---

## 3. マルチエージェント合議プロトコル（3 女神合議）

Norn の最大の特徴である「3 女神の合議」は、以下のステップに従って決定論的かつ協調的に実行されます。

```
[GitHub Diff + Ruff] ──> (1. 解析) ──> [Urd (技術)] ──> (指摘事項)
                                           │
                                       (2. 合議) ──> [Verdandi (共感)] ──> (トーン調整)
                                           │
                                       (3. 拡張) ──> [Skuld (未来)] ──> (学習リソース提案)
                                           │
                                           ▼
                                 [Consensus Moderator] ──> (4. 最終要約) ──> [Chat UI / GitHub PR Comment]
```

### 合議ステップ詳細

| ステップ | 担当エージェント | 処理内容 | 技術的アプローチ |
| :--- | :--- | :--- | :--- |
| **1. 技術解析** | **Urd（技術）** | コード差分を読み込み、バグ、脆弱性、パフォーマンス、設計規約違反を抽出。 | Ruff の出力をベースに、厳格なコードレビュープロンプトを適用。 |
| **2. 共感・トーン調整** | **Verdandi（現在）** | Urd の指摘をレビューし、若手が挫折しないように「言い方」をマイルドに修正。段階的な改善ステップを提案。 | 心理的安全性（Psychological Safety）のフレームワークに基づいたトーン調整 [4]。 |
| **3. キャリア・成長拡張** | **Skuld（未来）** | 指摘された技術要素に関連する学習リソース・成長機会を提案。 | プロンプト指示による LLM 生成（RAG / ベクトル DB は未実装 — §7 参照）。 |
| **4. 合意形成と要約** | **Consensus Moderator** | 3 女神の対話を要約し、チャット UI および GitHub PR コメント用の構造化されたマークダウンメッセージを生成。 | 固定 1 ラウンドで収束。Moderator の Structured Output（`ConsensusOutput`）でフォーマットを固定化。 |

---

## 4. データベース設計（スキーマ）

会話履歴およびレビューセッションを管理するコアテーブル設計です（`backend/norn/db/models.py`）。Postgres 互換を保つため JSON / `DateTime(timezone=True)` / `String(36)` UUID を使用します。

### 4.1. `review_sessions` テーブル

PR ごとのレビューセッションを追跡します。チャット UI スレッドと 1:1 です。

*   `id` (String(36), Primary Key — UUID)
*   `repository_name` (String(255))
*   `pr_number` (Integer)
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

---

## 5. REST API 一覧

| Method | Path | 用途 |
|--------|------|------|
| POST | `/webhook/github` | GitHub Webhook 受信 |
| POST | `/chat/messages` | チャットメッセージ送信 |
| GET | `/chat/threads` | スレッド一覧 |
| GET | `/chat/threads/{thread_id}` | スレッド詳細・メッセージ履歴 |
| GET | `/chat/threads/{thread_id}/events` | SSE ライブ合議ストリーム |
| POST | `/reviews/{session_id}/start` | HITL — 合議開始 |
| POST | `/reviews/{session_id}/skip` | HITL — 今回スキップ |
| GET | `/dashboard/stats` | 成長ダッシュボード統計 |
| GET | `/healthz` | ライブネスチェック |
| GET | `/readyz` | レディネスチェック（現状は常に `ok` — §7 参照） |

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
| `users` テーブル | `github_username`, `skill_level`（`junior` / `mid` / `senior`）による若手プロファイル管理 |
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
