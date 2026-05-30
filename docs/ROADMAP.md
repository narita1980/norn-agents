# 開発ロードマップ & 実装タスクリスト — Project Norn (norn-agents)

本ドキュメントは、プロジェクト「Norn（ノルン）」をゼロから実装し、ハッカソンで優勝するための具体的な開発フェーズ、マイルストーン、および実装タスクを定義したものです。

---

## 1. 開発マイルストーン

プロジェクトの開発は、検証可能性と安定性を重視し、以下のフェーズに分けて進めます。

```
[Phase 1: 基盤構築] ──> [Phase 1.5: フロント + Draft トリガー] ──> [Phase 2: エージェント合議]
                                                                          │
                                                                          ▼
                                            [Phase 3: GitHub 連携・永続化] ──> [Phase 4: デモ磨き]
```

---

## 2. 詳細タスクリスト

各フェーズで実装すべき具体的なタスク、担当モジュール、および完了定義を整理しました。

### Phase 1: プロジェクト基盤 & Webhookレシーバーの構築（目標：1〜2日目）
このフェーズでは、API の基礎と外部イベントの受信環境を構築します。

*   [x] **Task 1.1: プロジェクトの初期化とパッケージ管理設定**
    *   uv 環境をセットアップし、`FastAPI`, `uvicorn`, `pydantic-settings`, `semantic-kernel`, `PyGithub`, `httpx` などの依存関係を定義。
*   [x] **Task 1.2: FastAPI Webhookレシーバーの実装**
    *   GitHub Webhook (`/webhook/github`) のエンドポイントを実装。
    *   GitHub の署名（HMAC SHA256, `X-Hub-Signature-256`）検証ロジックを Depends 層で実装し、セキュリティを担保。
*   [x] **Task 1.3: 環境変数・設定管理の共通化**
    *   Pydantic Settings を用いて、API キー（Azure OpenAI, GitHub）や Webhook シークレットを安全に管理。

### Phase 1.5: フロントエンド再実装 & Draft PR 専用トリガー（目標：2〜3日目）
Phase 1 のスキャフォールドを実運用に近づけるため、UI を React 化し、トリガー条件を絞り込みます。

*   [x] **Task 1.5.1: Vite + React + bun ベースの独自チャット UI の構築**
    *   `frontend/` を Vite + React (TypeScript) で構築し、bun でビルド。
    *   バックエンドは `backend/`（uv ワークスペース）に分離し、ビルド出力は `backend/norn/static/` に配置して FastAPI の `StaticFiles` 経由で同一オリジンで配信。
    *   Vite dev server (port 5173) から `/chat`、`/webhook`、`/healthz`、`/readyz` を FastAPI (port 8000) にプロキシする開発フローを整備。
*   [x] **Task 1.5.2: GitHub Draft PR 専用トリガーの実装**
    *   Webhook ハンドラで `pull_request` イベントの `action == "opened"` かつ `draft == true` のときのみ合議ディスパッチを発火（Phase 2 で実体を投入）。
    *   その他の `action` / 非 Draft はログのみ残して素通り。
    *   `caplog` を使ったテストで「Draft PR opened → dispatch ログ」「非 Draft → ignored ログ」を検証。

### Phase 2: マルチエージェント（3女神）の実装（目標：4〜6日目）
このフェーズでは、合議プロトコルの核心部分を実装します。

*   [x] **Task 2.1: 3女神エージェントのプロンプト・ペルソナ定義**
    *   `Urd` (技術), `Verdandi` (共感), `Skuld` (未来) のシステムプロンプトを定義。
    *   心理的安全性や教育的アプローチに特化した Few-Shot プロンプト（レビューの良い例・悪い例）を作成。
*   [x] **Task 2.2: GroupChat と調停者（Moderator）の実装**
    *   3女神が対話を行う `GroupChat` を構築。
    *   議論の無限ループを防止するため、最大ターン数（`max_round`）を設定し、合意を判定する `ConsensusModerator` を実装 [2]。
*   [x] **Task 2.3: エージェントの単体テスト（Mock 実行）**
    *   GitHub API に依存せず、モックのコード差分（Diff）を入力として、3女神が期待通りのトーンで合議を行えるかを pytest で検証。

### Phase 3: GitHub 連携と永続化（目標：7〜9日目）
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

### Phase 4: ハッカソン必勝の磨き込み & デモ演出（目標：10〜12日目）
審査員の心を動かすための演出と UX を実装します。

*   [ ] **Task 4.1: 「裏の合議プロセス」をチャット UI 上で可視化**
    *   デモ中に審査員に見せるため、3女神が裏で「あーでもない、こーでもない」と議論している生ログを、Vite + React チャット UI のサイドパネルや専用 view にリアルタイムで垂れ流す。
*   [ ] **Task 4.2: 若手の主導権（Human-in-the-loop）UI の実装**
    *   Draft PR が作られた際、勝手にレビューを始めず、チャット UI 上で「Norn のレビューを開始しますか？ [開始する] [今回はスキップ]」というインタラクティブなボタンを提示する UX を実装 [4]。
*   [ ] **Task 4.3: シニア向け「組織の成長ダッシュボード」モックの作成**
    *   若手の理解度や Norn の介入によって削減されたシニアの工数を可視化するダッシュボードの画面モック（Figma 等、または React 静的ページ）を作成。

---

## 3. 参考文献
[1] Microsoft Research, "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation," Microsoft Project AutoGen.  
[2] SecondTalent, "How Enterprises Are Using AutoGen in 2026," May 2026.  
[3] Reddit, "My Hackathon Project's Near-Death Experience with AI Agents," September 2025.  
[4] Forbes, "Why Psychological Safety Matters More In AI-Enabled Teams," May 2026.
