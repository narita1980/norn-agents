# プロジェクト・アーキテクチャ設計書 — Project Norn (norn-agents)

本ドキュメントは、プロジェクト「Norn（ノルン）」のシステム構成、データフロー、およびマルチエージェント合議プロトコルの詳細を定義する技術仕様書です。

---

## 1. 全体システム構成

Nornは、イベント駆動型（Event-Driven）の疎結合なアーキテクチャを採用しています。GitHubおよびSlackからのイベントをトリガーに、FastAPIサーバーが中継を行い、Azure AI Foundry（旧Azure AI Studio）上のAutoGenオーケストレーターが非同期でエージェント合議を実行します [1]。

```
[GitHub (Draft PR)] ────(Webhook)────> [FastAPI (Webhook Receiver)]
                                               │
                                       (Async Background Task)
                                               │
                                               ▼
[Slack (Bolt API)] <───(Slack Bot)─── [AutoGen Orchestrator (Azure)]
                                        ├── UrdAgent (技術)
                                        ├── VerdandiAgent (現在)
                                        └── SkuldAgent (未来)
```

---

## 2. コア・コンポーネント仕様

システムを構成する4つの主要モジュールについて、それぞれの役割と技術的仕様を定義します。

### 2.1. Webhookレシーバー (FastAPI)
GitHubおよびSlackからのイベントを安全かつ高速に受信・処理します。
*   **認証・検証**：GitHub Webhookのシークレット（`X-Hub-Signature-256`）およびSlackの署名（`X-Slack-Signature`）の検証をミドルウェア層で強制します。
*   **非同期ハンドリング**：イベント受信後、即座に `202 Accepted` を返却し、実際のエージェント処理は `BackgroundTasks` またはタスクキューにオフロードしてWebhookのタイムアウトを防止します。

### 2.2. AutoGenマルチエージェント・オーケストレーター
Microsoft AutoGen v0.4（AG2）[2] を使用し、合議プロセスを管理します。
*   **Orchestration Pattern**: `GroupChat`（ラウンドロビン、または調停者による制御型）[2]。
*   **State Persistence**: Azure AI Foundry Agent Service [1] または Redis をバックエンドに用い、会話履歴とエージェントのコンテキスト状態を永続化します。

### 2.3. GitHubコネクター
PRのソースコード、差分（Diff）、および過去のコミット履歴を取得し、エージェントが理解できるコンテキストに整形します。
*   **静的解析統合**：コード差分をLLMに直接投げる前に、`Ruff` や `AST` 解析ツールを実行し、構造的な警告情報をメタデータとしてエージェントに提供します [3]。

### 2.4. Slackコネクター
Slack Bolt for Pythonを使用し、若手エンジニアとの双方向の対話を可能にします。
*   **スレッド管理**：PRごとのレビューは、Slack上の特定のスレッド（Thread）内に閉じ込めることで、チャンネル全体のノイズを最小限に抑えます。

---

## 3. マルチエージェント合議プロトコル（3女神合議）

Nornの最大の特徴である「3女神の合議」は、以下のステップに従って決定論的かつ協調的に実行されます。

```
[GitHub Diff] ──> (1. 解析) ──> [Urd (技術)] ──> (指摘事項)
                                    │
                                (2. 合議) ──> [Verdandi (共感)] ──> (トーン調整)
                                    │
                                (3. 拡張) ──> [Skuld (未来)] ──> (学習リソース)
                                    │
                                    ▼
                          [Consensus Moderator] ──> (4. 最終要約) ──> [Slack]
```

### 合議ステップ詳細

| ステップ | 担当エージェント | 処理内容 | 技術的アプローチ |
| :--- | :--- | :--- | :--- |
| **1. 技術解析** | **Urd（技術）** | コード差分を読み込み、バグ、脆弱性、パフォーマンス、設計規約違反を抽出。 | 静的解析ツールの出力をベースに、厳格なコードレビュープロンプトを適用。 |
| **2. 共感・トーン調整** | **Verdandi（現在）** | Urdの指摘をレビューし、若手が挫折しないように「言い方」をマイルドに修正。段階的な改善ステップを提案。 | 心理的安全性（Psychological Safety）のフレームワークに基づいたトーン調整 [4]。 |
| **3. キャリア・成長拡張** | **Skuld（未来）** | 指摘された技術要素に関連する公式ドキュメント、社内のWiki、過去のベストプラクティスを推薦。 | ベクトルデータベース（RAG）から関連する社内知識や学習ソースを検索・付与 [2]。 |
| **4. 合意形成と要約** | **Consensus Moderator** | 3女神の対話を要約し、Slack用の構造化されたマークダウンメッセージ（またはインタラクティブブロック）を生成。 | 議論の無限ループを検知・遮断し、フォーマットを固定化するための構造化出力（Structured Outputs）。 |

---

## 4. データベース設計（スキーマ）

会話履歴、学習の進捗、およびレビュー基準の同期を管理するためのコアテーブル設計です。

### 4.1. `users` テーブル
若手エンジニアの情報を管理します。
*   `id` (UUID, Primary Key)
*   `github_username` (String, Unique)
*   `slack_user_id` (String, Unique)
*   `skill_level` (Enum: `junior`, `mid`, `senior`)
*   `created_at` (Timestamp)

### 4.2. `review_sessions` テーブル
PRごとのレビューセッションを追跡します。
*   `id` (UUID, Primary Key)
*   `pr_number` (Integer)
*   `repository_name` (String)
*   `slack_thread_ts` (String, Slackのスレッドタイムスタンプ)
*   `status` (Enum: `running`, `completed`, `failed`)
*   `created_at` (Timestamp)

### 4.3. `agent_conversations` テーブル
AutoGen内の合議履歴を保存し、RAGや将来の学習に活用します。
*   `id` (UUID, Primary Key)
*   `session_id` (UUID, Foreign Key to `review_sessions`)
*   `agent_name` (String: `urd`, `verdandi`, `skuld`, `moderator`)
*   `message_content` (Text)
*   `created_at` (Timestamp)

---

## 5. 参考文献
[1] Microsoft Reactor, "Microsoft AI Genius: Build your own code-first AI agent using Azure AI Foundry Agent Service," August 2025.  
[2] SecondTalent, "How Enterprises Are Using AutoGen in 2026," May 2026.  
[3] Reddit, "My Hackathon Project’s Near-Death Experience with AI Agents," September 2025.  
[4] Forbes, "Why Psychological Safety Matters More In AI-Enabled Teams," May 2026.
