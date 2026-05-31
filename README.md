# Norn（ノルン）

若手エンジニア向けマルチエージェント・コードレビュー伴走システム。

GitHub Draft PR をトリガーに、Urd（技術）・Verdandi（共感）・Skuld（未来）の 3 女神が合議し、心理的安全性を保ちながらコードレビューと成長支援を提供します。若手が `[開始する]` を押すまで合議は始まらない Human-in-the-loop（HITL）設計です。

## 機能概要

- **Draft PR トリガー** — GitHub Webhook で Draft PR opened を検知し、承認待ちセッションを作成
- **3 女神合議** — `NornOrchestrator` による固定逐次合議（Urd → Verdandi → Skuld → Moderator）
- **ライブ合議 SSE** — チャット UI 右パネルで合議プロセスをリアルタイム可視化
- **GitHub PR コメント** — 合議結果を Draft PR にマークダウンで投稿
- **双方向対話** — PR 上のリプライから再合議
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

## ドキュメント

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — システム構成・合議プロトコル・DB スキーマ・API 一覧
- [ROADMAP.md](docs/ROADMAP.md) — 開発フェーズとタスクリスト
- [CLAUDE.md](CLAUDE.md) — AI コーディングアシスタント向け開発ガイド

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
