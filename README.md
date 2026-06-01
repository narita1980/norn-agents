# Norns（ノルンズ）

若手エンジニア向けマルチエージェント・コードレビュー伴走システム。

GitHub Draft PR をトリガーに、**ウルド（技術）・ヴェルダンディ（共感）・スクルド（未来）** の 3 視点が合議し、心理的安全性を保ちながらコードレビューと成長支援を提供します。若手が `[開始する]` を押すまで合議は始まらない Human-in-the-loop（HITL）設計です。

## 機能概要

- **Draft PR トリガー** — GitHub Webhook で Draft PR opened を検知し、承認待ちセッションを作成
- **3 女神合議** — `NornOrchestrator` による並行合議（ウルド・ヴェルダンディ・スクルド → モデレーター統合）
- **ライブ合議 SSE** — チャット UI 右パネルで合議プロセスをリアルタイム可視化
- **GitHub PR コメント** — 合議結果を Draft PR にマークダウンで投稿
- **双方向対話** — PR 上のリプライから再合議
- **スレッド管理** — 一覧（ドロワー）・個別削除・新規チャット
- **Norns とは** — 読み方・サービス説明ページ（ナビから）
- **成長ダッシュボード** — レビュー統計と KPI（シニア工数削減の推定値等）

## 前提

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)（Python パッケージ管理）
- [bun](https://bun.sh/)（フロントエンドビルド）
- Azure OpenAI リソース（API キー・エンドポイント・デプロイメント）
- GitHub Personal Access Token（repo スコープ）

## セットアップ

```bash
# バックエンド
cd backend
uv sync
cp .env.example .env
# .env に Azure OpenAI / GitHub の認証情報を記入

# フロントエンド
cd ../frontend
bun install
```

## 開発サーバー

2 つのターミナルで起動します。SSE / in-memory イベントバスの都合上、**uvicorn は必ず `--workers 1`** で起動してください。

```bash
# Terminal A: FastAPI (port 8000)
cd backend
uv run uvicorn norn.api.main:app --reload --port 8000 --workers 1

# Terminal B: Vite dev server (http://localhost:5173)
cd frontend
bun dev
```

Vite dev server が `/chat` `/webhook` `/reviews` `/dashboard` `/healthz` `/readyz` を FastAPI にプロキシするため、ブラウザは **http://localhost:5173** を開いてください。

### 本番相当の確認

```bash
cd frontend && bun run build   # 出力先: ../backend/norn/static/
cd ../backend && uv run uvicorn norn.api.main:app --port 8000 --workers 1
# http://localhost:8000
```

## デモ手順

1. リポジトリに GitHub Webhook を設定（`pull_request` + `issue_comment` イベント、`/webhook/github` エンドポイント）
2. **Draft PR** を open → チャット UI に承認待ち（`pending_approval`）が表示される
3. `[開始する]` をクリック → SSE で 3 女神の合議が右パネルに流れる
4. 合議完了 → GitHub PR にレビューコメントが投稿され、ダッシュボードに反映される
5. PR 上でリプライ → 再合議が走る

## デモ環境（Azure）

**Static Web Apps（UI）+ Container Apps（API）** の分割構成です。詳細は [docs/hackathon/AZURE_DEPLOY.md](docs/hackathon/AZURE_DEPLOY.md)。

| 項目 | URL |
|------|-----|
| **UI（Static Web Apps）** | https://gentle-mushroom-0e3c9b500.7.azurestaticapps.net/ |
| **API / Webhook（Container Apps）** | https://norn.agreeablesky-b0ed548a.japaneast.azurecontainerapps.io |
| Webhook エンドポイント | `https://norn.agreeablesky-b0ed548a.japaneast.azurecontainerapps.io/webhook/github` |
| ヘルスチェック | `https://norn.agreeablesky-b0ed548a.japaneast.azurecontainerapps.io/healthz` |

### ログイン認証

ログイン ID/パスワードは **DB（`users` テーブル）** のみです。UI はログイン画面を表示し、API（`/chat` 等）は JWT セッション Cookie で常に保護されます。

**デモ用テストユーザー**（LearnerSwitcher と 1:1）:

| ログイン ID | 表示名 | user_level |
|-------------|--------|------------|
| `yuki` | ゆき | `junior` |
| `takeshi` | たけし | `mid` |
| `sakura` | さくら | `senior` |

**共通パスワード（デモ用）:** `norn-demo`（3人とも同じ。画面には表示しません）

```bash
cd backend
uv run alembic upgrade head
uv run python -m norn.cli seed-test-users
```

ログイン後、LearnerSwitcher で切替えると `POST /auth/switch-learner` が JWT を対応ユーザに再発行します。管理者用の追加ユーザーは `create-user` で作成できます。

| 環境変数 / Secret | 説明 |
|-------------------|------|
| `NORN_AUTH_SECRET` | JWT 署名鍵（本番必須） |

詳細は `backend/.env.example` を参照してください。

## Microsoft Agent Hackathon 2026 提出物

| ファイル | 内容 |
|----------|------|
| [docs/hackathon/AZURE_DEPLOY.md](docs/hackathon/AZURE_DEPLOY.md) | Azure Container Apps デプロイ |
| [docs/hackathon/DEMO_SCRIPT.md](docs/hackathon/DEMO_SCRIPT.md) | 固定デモシナリオ |
| [docs/hackathon/SUBMISSION.md](docs/hackathon/SUBMISSION.md) | **提出用 URL 一覧・チェックリスト** |
| [docs/hackathon/zenn-article.md](docs/hackathon/zenn-article.md) | Zenn 記事（公開用ドラフト） |
| [docs/hackathon/VIDEO_SCRIPT.md](docs/hackathon/VIDEO_SCRIPT.md) | デモ動画台本（3–5 分） |
| [docs/hackathon/PITCH.md](docs/hackathon/PITCH.md) | 6/18 最終審査ピッチ原稿 |
| [docs/hackathon/ORCHESTRATION_AB.md](docs/hackathon/ORCHESTRATION_AB.md) | fixed vs group_chat A/B 比較 |

**ハッカソン提出**: [SUBMISSION.md](docs/hackathon/SUBMISSION.md) の URL を [Microsoft Agent Hackathon 2026](https://zenn.dev/hackathons/microsoft-agent-hackathon-2026) フォームに入力してください。

```bash
# API のみ Docker 確認（UI は bun dev または Static Web Apps）
docker build -t norn-api:local -f backend/Dockerfile backend
docker run --rm -p 8000:8000 --env-file backend/.env \
  -e NORN_APP_BASE_URL=http://localhost:5173 -v norn-data:/data norn-api:local

curl http://localhost:8000/healthz

# Azure デプロイ → GitHub Actions「Deploy to Azure」を実行
```

## ドキュメント

| ファイル | 内容 |
|----------|------|
| [docs/FILE_MAP.md](docs/FILE_MAP.md) | **変更箇所の早見表**（まずここ） |
| [docs/FRONTEND.md](docs/FRONTEND.md) | React 画面・UI パターン |
| [docs/CONVENTIONS.md](docs/CONVENTIONS.md) | 表示名・セッション状態・よくあるエラー |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | システム構成・DB・API・SSE |
| [docs/ROADMAP.md](docs/ROADMAP.md) | 開発フェーズとタスク |
| [CLAUDE.md](CLAUDE.md) | 開発コマンド・環境変数 |

## 現状と制約

| 項目 | 状態 |
|------|------|
| Phase 1〜4 機能 | 実装済み |
| pytest テストスイート | 未整備（Phase 5 予定） |
| GitHub Actions CI | 未整備（Phase 5 予定） |
| EventBus | in-memory（`--workers 1` 必須） |
| `/readyz` | shallow チェックのみ（DB 到達性未検証） |
| Skuld RAG / users テーブル | 未実装（Phase 5 予定） |

## ライセンス

（未設定）
