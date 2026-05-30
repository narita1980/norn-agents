# 開発ロードマップ & 実装タスクリスト — Project Norn (norn-agents)

本ドキュメントは、プロジェクト「Norn（ノルン）」をゼロから実装し、ハッカソンで優勝するための具体的な開発フェーズ、マイルストーン、および実装タスクを定義したものです。

---

## 1. 開発マイルストーン

プロジェクトの開発は、検証可能性と安定性を重視し、以下の4つのフェーズに分けて進めます。

```
[Phase 1: 基盤構築] ──> [Phase 2: エージェント合議] ──> [Phase 3: インテグレーション] ──> [Phase 4: デモ・磨き込み]
```

---

## 2. 詳細タスクリスト

各フェーズで実装すべき具体的なタスク、担当モジュール、および完了定義を整理しました。

### Phase 1: プロジェクト基盤 & Webhookレシーバーの構築（目標：1〜2日目）
このフェーズでは、APIの基礎と外部イベントの受信環境を構築します。

*   [ ] **Task 1.1: プロジェクトの初期化とパッケージ管理設定**
    *   Poetry環境をセットアップし、`FastAPI`, `uvicorn`, `autogen-core` (AG2) [1], `PyGithub`, `slack-bolt` などの依存関係を定義。
*   [ ] **Task 1.2: FastAPI Webhookレシーバーの実装**
    *   GitHub WebhookおよびSlack Events APIのエンドポイントを実装。
    *   GitHubの署名（HMAC SHA256）およびSlackの署名検証ロジックを実装し、セキュリティを担保。
*   [ ] **Task 1.3: 環境変数・設定管理の共通化**
    *   Pydantic Settingsを用いて、APIキー（Azure OpenAI, GitHub, Slack）やWebhookシークレットを安全に管理。

### Phase 2: AutoGenマルチエージェント（3女神）の実装（目標：3〜5日目）
このフェーズでは、合議プロトコルの核心部分を実装します。

*   [ ] **Task 2.1: 3女神エージェントのプロンプト・ペルソナ定義**
    *   `Urd` (技術), `Verdandi` (共感), `Skuld` (未来) のシステムプロンプトを定義。
    *   心理的安全性や教育的アプローチに特化したFew-Shotプロンプト（レビューの良い例・悪い例）を作成。
*   [ ] **Task 2.2: AutoGen GroupChatと調停者（Moderator）の実装**
    *   3女神が対話を行う `GroupChat` を構築。
    *   議論の無限ループを防止するため、最大ターン数（`max_round`）を設定し、合意を判定する `ConsensusModerator` を実装 [2]。
*   [ ] **Task 2.3: エージェントの単体テスト（Mock実行）**
    *   GitHub APIに依存せず、モックのコード差分（Diff）を入力として、3女神が期待通りのトーンで合議を行えるかを pytest で検証。

### Phase 3: GitHub × Slack 連携の実装（目標：6〜8日目）
エージェントを実際の開発環境に接続します。

*   [ ] **Task 3.1: GitHub Diff取得・解析ツールの実装**
    *   GitHub APIを呼び出し、Draft PRの変更ファイル、コード差分（Diff）、コミットメッセージを取得。
    *   Ruffなどの静的解析結果をメタデータとしてDiffに付与するツール（Tools）を実装し、エージェントに装備 [3]。
*   [ ] **Task 3.2: Slack Boltによるスレッド送信モジュールの実装**
    *   合議の結果得られた最終レビューを、Slackの特定チャンネル・スレッドにマークダウン形式（Slack Blocks）で送信。
    *   若手がSlack上でエージェントに質問を返した際、そのスレッドの会話履歴を引き継いで再合議を行う双方向対話ロジックの実装。
*   [ ] **Task 3.3: データベース（SQLite/PostgreSQL）によるセッション永続化**
    *   PRの番号とSlackのスレッドIDのマッピングを保存。
    *   エージェント間の議論ログを保存し、コンテキストの引き継ぎを可能にする。

### Phase 4: ハッカソン必勝の磨き込み & デモ演出（目標：9〜10日目）
審査員の心を動かすための演出とUXを実装します。

*   [ ] **Task 4.1: 「裏の合議プロセス」を可視化するDiscord/Slackチャンネルの実装**
    *   デモ中に審査員に見せるため、3女神が裏で「あーでもない、こーでもない」と議論している生ログを垂れ流す専用のSlackチャンネル（またはWebダッシュボード）を構築。
*   [ ] **Task 4.2: 若手の主導権（Human-in-the-loop）UIの実装**
    *   Draft PRが作られた際、勝手にレビューを始めず、Slack上で「Nornのレビューを開始しますか？ [開始する] [今回はスキップ]」というインタラクティブなボタンを提示するUXを実装 [4]。
*   [ ] **Task 4.3: シニア向け「組織の成長ダッシュボード」モックの作成**
    *   若手の理解度やNornの介入によって削減されたシニアの工数を可視化するダッシュボードの画面モック（Figma等、または静的HTML）を作成。

---

## 3. 参考文献
[1] Microsoft Research, "AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation," Microsoft Project AutoGen.  
[2] SecondTalent, "How Enterprises Are Using AutoGen in 2026," May 2026.  
[3] Reddit, "My Hackathon Project’s Near-Death Experience with AI Agents," September 2025.  
[4] Forbes, "Why Psychological Safety Matters More In AI-Enabled Teams," May 2026.
