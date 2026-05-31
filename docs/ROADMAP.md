# 開発ロードマップ & 実装タスクリスト — Project Norn (norn-agents)

本ドキュメントは、プロジェクト「Norn（ノルン）」をゼロから実装し、ハッカソンで優勝するための具体的な開発フェーズ、マイルストーン、および実装タスクを定義したものです。

**実装時のファイル配置・UI 規約**は [FILE_MAP.md](FILE_MAP.md) / [FRONTEND.md](FRONTEND.md) / [CONVENTIONS.md](CONVENTIONS.md) を参照（ロードマップよりこちらが現行実装に近い）。

---

## 1. 開発マイルストーン

プロジェクトの開発は、検証可能性と安定性を重視し、以下のフェーズに分けて進めます。

```
[Phase 1: 基盤構築] ──> [Phase 1.5: フロント + Draft トリガー] ──> [Phase 2: エージェント合議]
                                                                          │
                                                                          ▼
                                            [Phase 3: GitHub 連携・永続化] ──> [Phase 4: デモ磨き]
                                                                                      │
                                                                                      ▼
                                                                            [Phase 5: 品質・本番・拡張]
```

---

## 2. 詳細タスクリスト

各フェーズで実装すべき具体的なタスク、担当モジュール、および完了定義を整理しました。

### Phase 1: プロジェクト基盤 & Webhook レシーバーの構築（目標：1〜2 日目）

このフェーズでは、API の基礎と外部イベントの受信環境を構築します。

*   [x] **Task 1.1: プロジェクトの初期化とパッケージ管理設定**
    *   uv 環境をセットアップし、`FastAPI`, `uvicorn`, `pydantic-settings`, `semantic-kernel`, `PyGithub`, `httpx` などの依存関係を定義。
*   [x] **Task 1.2: FastAPI Webhook レシーバーの実装**
    *   GitHub Webhook (`/webhook/github`) のエンドポイントを実装。
    *   GitHub の署名（HMAC SHA256, `X-Hub-Signature-256`）検証ロジックを Depends 層で実装し、セキュリティを担保。
*   [x] **Task 1.3: 環境変数・設定管理の共通化**
    *   Pydantic Settings を用いて、API キー（Azure OpenAI, GitHub）や Webhook シークレットを安全に管理。

### Phase 1.5: フロントエンド再実装 & Draft PR 専用トリガー（目標：2〜3 日目）

Phase 1 のスキャフォールドを実運用に近づけるため、UI を React 化し、トリガー条件を絞り込みます。

*   [x] **Task 1.5.1: Vite + React + bun ベースの独自チャット UI の構築**
    *   `frontend/` を Vite + React (TypeScript) で構築し、bun でビルド。
    *   バックエンドは `backend/`（uv ワークスペース）に分離し、ビルド出力は `backend/norn/static/` に配置して FastAPI の `StaticFiles` 経由で同一オリジンで配信。
    *   Vite dev server (port 5173) から `/chat`、`/webhook`、`/healthz`、`/readyz` を FastAPI (port 8000) にプロキシする開発フローを整備。
*   [x] **Task 1.5.2: GitHub Draft PR 専用トリガーの実装**
    *   Webhook ハンドラで `pull_request` イベントの `action == "opened"` かつ `draft == true` のとき `ReviewSession` を `pending_approval` で登録（Phase 4 で HITL 化）。
    *   その他の `action` / 非 Draft はログのみ残して素通り。
*   [ ] **Task 1.5.3: Webhook トリガーの pytest 検証**
    *   `caplog` を使ったテストで「Draft PR opened → pending 登録ログ」「非 Draft → ignored ログ」を検証。
    *   注: commit `7774acd` で旧テストスイートが削除されたため、Phase 5 Task 5.1 で再作成予定。

### Phase 2: マルチエージェント（3 女神）の実装（目標：4〜6 日目）

このフェーズでは、合議プロトコルの核心部分を実装します。

*   [x] **Task 2.1: 3 女神エージェントのプロンプト・ペルソナ定義**
    *   `Urd` (技術), `Verdandi` (共感), `Skuld` (未来) のシステムプロンプトを定義。
    *   心理的安全性や教育的アプローチに特化した Few-Shot プロンプト（レビューの良い例・悪い例）を作成。
*   [x] **Task 2.2: NornOrchestrator と調停者（Moderator）の実装**
    *   Urd → Verdandi → Skuld → Moderator の **固定逐次合議** を `NornOrchestrator` で実装（GroupChat は不使用）。
    *   Semantic Kernel は LLM コネクタ（`AzureChatCompletion`）として利用。
    *   議論の無限ループを防止するため、1 ラウンド固定と Moderator による構造化 JSON 出力（`ConsensusOutput`）で収束 [2]。
*   [ ] **Task 2.3: エージェントの単体テスト（Mock 実行）**
    *   GitHub API に依存せず、モックのコード差分（Diff）を入力として、3 女神が期待通りのトーンで合議を行えるかを pytest で検証。
    *   注: commit `7774acd` で旧テストスイートが削除されたため、Phase 5 Task 5.1 で再作成予定。

### Phase 3: GitHub 連携と永続化（目標：7〜9 日目）

エージェントを実際の開発環境に接続し、状態を保持します。

*   [x] **Task 3.1: GitHub Diff 取得・解析ツールの実装**
    *   GitHub API を呼び出し、Draft PR の変更ファイル、コード差分（Diff）、コミットメッセージを取得。
    *   Ruff などの静的解析結果をメタデータとして Diff に付与するツール（Tools）を実装し、エージェントに装備 [3]。
*   [x] **Task 3.2: GitHub PR コメント送信モジュールの実装**
    *   合議の結果得られた最終レビューを、Draft PR のレビューコメントとしてマークダウン形式で送信。
    *   PR 上での若手からのリプライをトリガーに会話履歴を引き継いで再合議を行う双方向対話ロジックの実装。
*   [x] **Task 3.3: データベース（SQLite/PostgreSQL）によるセッション永続化**
    *   PR の番号とチャット UI のスレッド ID のマッピングを保存。
    *   エージェント間の議論ログを保存し、コンテキストの引き継ぎを可能にする。

### Phase 4: ハッカソン必勝の磨き込み & デモ演出（目標：10〜12 日目）

審査員の心を動かすための演出と UX を実装します。

*   [x] **Task 4.1: 「裏の合議プロセス」をチャット UI 上で可視化**
    *   `norn.events.bus` の in-memory pub-sub と `NornOrchestrator.run(..., on_event=...)` のコールバック化で、ターン単位のイベントを `GET /chat/threads/{thread_id}/events`（SSE）で配信。フロントは右パネル `ConsensusPanel` で Urd / Verdandi / Skuld / Moderator の発言を順に描画する。
*   [x] **Task 4.2: 若手の主導権（Human-in-the-loop）UI の実装**
    *   Draft PR opened の Webhook は自動発火せず、`ReviewSession.status = "pending_approval"` + `chat_messages.action_payload` に開始プロンプトを書き込む。`POST /reviews/{id}/start` / `/skip` で進行を制御し、フロントの `ApprovalBanner` から呼び出す。
*   [x] **Task 4.3: シニア向け「組織の成長ダッシュボード」モックの作成**
    *   `GET /dashboard/stats` で実 DB 統計（status 別件数 / tone 分布 / 最近の完了レビュー）にモック KPI（推定シニア工数削減 = 完了数 × 0.5h、若手学習時間 = 完了数 × 12 min 等）を合成して返却。フロントの `Dashboard` コンポーネントが KPI カード + CSS バーで描画する。

#### Phase 4 補足

*   in-memory イベントバスは **uvicorn `--workers 1`** 前提。複数プロセス運用への拡張は Phase 5 Task 5.5 を参照。

### Phase 5: 品質保証・本番運用・機能拡張（未着手）

Phase 1〜4 の機能実装完了後に着手する項目です。

*   [ ] **Task 5.1: pytest スイート再作成**
    *   HITL（`/reviews/{id}/start|skip`）、SSE、dashboard を含む Phase 4 フローに合わせて再作成。
    *   Webhook 署名検証、オーケストレータ、DB 永続化、GitHub ツール、chat API をカバー。
*   [ ] **Task 5.2: GitHub Actions CI**
    *   `ruff check`、`pytest`、`bun run typecheck`（任意: frontend build）を PR ごとに実行。
*   [ ] **Task 5.3: PostgreSQL 本番対応**
    *   `asyncpg` 依存追加、`readyz` で DB 接続確認、本番 `DATABASE_URL` 運用手順の整備。
*   [ ] **Task 5.4: `pending_approval` TTL 自動失効**
    *   放置された承認待ちセッションを一定時間後に `skipped` または失効状態へ遷移。
*   [ ] **Task 5.5: Redis EventBus（マルチワーカー）**
    *   in-memory `EventBus` を Redis Pub/Sub に差し替え、`uvicorn --workers N` 運用を可能にする。
*   [ ] **Task 5.6: `users` テーブル + skill_level**
    *   若手エンジニアの GitHub ユーザー名・スキルレベルを管理し、合議トーンのパーソナライズに活用。
*   [ ] **Task 5.7: Skuld RAG / 学習リソース検索**
    *   ベクトル DB / 社内 Wiki から関連学習ソースを検索・付与。

---

## 3. 参考文献

[1] Microsoft, "Semantic Kernel: Integrate cutting-edge LLM technology quickly and easily into your apps."  
[2] SecondTalent, "How Enterprises Are Using AutoGen in 2026," May 2026.  
[3] Reddit, "My Hackathon Project's Near-Death Experience with AI Agents," September 2025.  
[4] Forbes, "Why Psychological Safety Matters More In AI-Enabled Teams," May 2026.
