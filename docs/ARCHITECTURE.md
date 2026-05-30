# プロジェクト・アーキテクチャ設計書 — Project Norn (norn-agents)

本ドキュメントは、プロジェクト「Norn（ノルン）」のシステム構成、データフロー、およびマルチエージェント合議プロトコルの詳細を定義する技術仕様書です。

---

## 1. 全体システム構成

Nornは、イベント駆動型（Event-Driven）の疎結合なアーキテクチャを採用しています。**GitHub Draft PR の Webhook を唯一のトリガー**とし、FastAPI サーバーが中継を行い、Azure AI Foundry（旧Azure AI Studio）上の AutoGen オーケストレーターが非同期でエージェント合議を実行します [1]。レビュー結果は FastAPI が同一オリジンで配信する独自チャット UI（Vite + React, StaticFiles 経由）と GitHub PR コメントの両方に出力します。

```
[GitHub (Draft PR opened)] ──(Webhook)──> [FastAPI: Webhook Receiver + Chat REST + Static Hosting]
                                                       │
                                               (Async Background Task)
                                                       │
                                                       ▼
   [GitHub PR Review Comment] <──(GitHub API)── [AutoGen Orchestrator (Azure)]
   [Chat UI (Vite + React)]   <──(REST)──         ├── UrdAgent (技術)
                                                   ├── VerdandiAgent (現在)
                                                   └── SkuldAgent (未来)
```

---

## 2. コア・コンポーネント仕様

システムを構成する主要モジュールについて、それぞれの役割と技術的仕様を定義します。

### 2.1. Webhookレシーバー (FastAPI)
GitHub Webhook イベントを安全かつ高速に受信・処理します。
*   **認証・検証**：GitHub Webhook のシークレット（`X-Hub-Signature-256`）の HMAC-SHA256 検証を Depends 層で強制します。
*   **トリガー条件**：`pull_request` イベントの `action == "opened"` かつ `draft == true` のときのみ合議をディスパッチし、その他の `action`（`synchronize`、`ready_for_review`、`closed` 等）や非 Draft の `opened` は `202 Accepted` で受領しつつログのみ残して素通りさせます。
*   **非同期ハンドリング**：イベント受信後、即座に `202 Accepted` を返却し、実際のエージェント処理は `BackgroundTasks` またはタスクキューにオフロードして Webhook のタイムアウトを防止します。

### 2.2. AutoGenマルチエージェント・オーケストレーター
Microsoft AutoGen v0.4（AG2）[2] を使用し、合議プロセスを管理します。
*   **Orchestration Pattern**: `GroupChat`（ラウンドロビン、または調停者による制御型）[2]。
*   **State Persistence**: Azure AI Foundry Agent Service [1] または Redis をバックエンドに用い、会話履歴とエージェントのコンテキスト状態を永続化します。

### 2.3. GitHubコネクター
PR のソースコード、差分（Diff）、および過去のコミット履歴を取得し、エージェントが理解できるコンテキストに整形します。
*   **静的解析統合**：コード差分を LLM に直接投げる前に、`Ruff` や `AST` 解析ツールを実行し、構造的な警告情報をメタデータとしてエージェントに提供します [3]。
*   **レビューコメント送信**：合議結果を Draft PR のレビューコメントとしてマークダウンで投稿し、若手が GitHub 上でそのまま受け取れるようにします。

### 2.4. チャット UI (Vite + React)
Vite + React (TypeScript) で実装し、bun でビルドする独自チャット UI です。ビルド出力は `backend/norn/static/` に配置され、FastAPI の `StaticFiles` 経由で API と同一オリジンで配信されます。リポジトリは `backend/`（Python）と `frontend/`（React）の 2 ワークスペース構成です。
*   **スレッド管理**：PR ごと（または会話ごと）の対話を `thread_id` 単位で保持し、チャット UI 上で完結させる。
*   **REST API**：`POST /chat/messages`、`GET /chat/threads/{thread_id}` 経由でバックエンドと通信。
*   **開発時のプロキシ**：Vite dev server (port 5173) が `/chat`、`/webhook`、`/healthz`、`/readyz` を FastAPI (port 8000) にプロキシすることで、CORS 設定なしに同一オリジンの開発体験を保ちます。

---

## 3. マルチエージェント合議プロトコル（3女神合議）

Norn の最大の特徴である「3女神の合議」は、以下のステップに従って決定論的かつ協調的に実行されます。

```
[GitHub Diff] ──> (1. 解析) ──> [Urd (技術)] ──> (指摘事項)
                                    │
                                (2. 合議) ──> [Verdandi (共感)] ──> (トーン調整)
                                    │
                                (3. 拡張) ──> [Skuld (未来)] ──> (学習リソース)
                                    │
                                    ▼
                          [Consensus Moderator] ──> (4. 最終要約) ──> [Chat UI / GitHub PR Comment]
```

### 合議ステップ詳細

| ステップ | 担当エージェント | 処理内容 | 技術的アプローチ |
| :--- | :--- | :--- | :--- |
| **1. 技術解析** | **Urd（技術）** | コード差分を読み込み、バグ、脆弱性、パフォーマンス、設計規約違反を抽出。 | 静的解析ツールの出力をベースに、厳格なコードレビュープロンプトを適用。 |
| **2. 共感・トーン調整** | **Verdandi（現在）** | Urd の指摘をレビューし、若手が挫折しないように「言い方」をマイルドに修正。段階的な改善ステップを提案。 | 心理的安全性（Psychological Safety）のフレームワークに基づいたトーン調整 [4]。 |
| **3. キャリア・成長拡張** | **Skuld（未来）** | 指摘された技術要素に関連する公式ドキュメント、社内の Wiki、過去のベストプラクティスを推薦。 | ベクトルデータベース（RAG）から関連する社内知識や学習ソースを検索・付与 [2]。 |
| **4. 合意形成と要約** | **Consensus Moderator** | 3女神の対話を要約し、チャット UI および GitHub PR コメント用の構造化されたマークダウンメッセージを生成。 | 議論の無限ループを検知・遮断し、フォーマットを固定化するための構造化出力（Structured Outputs）。 |

---

## 4. データベース設計（スキーマ）

会話履歴、学習の進捗、およびレビュー基準の同期を管理するためのコアテーブル設計です。

### 4.1. `users` テーブル
若手エンジニアの情報を管理します。
*   `id` (UUID, Primary Key)
*   `github_username` (String, Unique)
*   `skill_level` (Enum: `junior`, `mid`, `senior`)
*   `created_at` (Timestamp)

### 4.2. `review_sessions` テーブル
PR ごとのレビューセッションを追跡します。
*   `id` (UUID, Primary Key)
*   `pr_number` (Integer)
*   `repository_name` (String)
*   `chat_thread_id` (String, チャット UI のスレッド ID)
*   `status` (Enum: `running`, `completed`, `failed`)
*   `created_at` (Timestamp)

### 4.3. `agent_conversations` テーブル
AutoGen 内の合議履歴を保存し、RAG や将来の学習に活用します。
*   `id` (UUID, Primary Key)
*   `session_id` (UUID, Foreign Key to `review_sessions`)
*   `agent_name` (String: `urd`, `verdandi`, `skuld`, `moderator`)
*   `message_content` (Text)
*   `created_at` (Timestamp)

---

## 5. 参考文献
[1] Microsoft Reactor, "Microsoft AI Genius: Build your own code-first AI agent using Azure AI Foundry Agent Service," August 2025.  
[2] SecondTalent, "How Enterprises Are Using AutoGen in 2026," May 2026.  
[3] Reddit, "My Hackathon Project's Near-Death Experience with AI Agents," September 2025.  
[4] Forbes, "Why Psychological Safety Matters More In AI-Enabled Teams," May 2026.
