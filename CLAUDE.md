# CLAUDE.md — Project Norn (norn-agents)

このファイルは、Claude Code やその他の AI コーディングアシスタントがプロジェクト「Norn（ノルン）」を深く理解し、一貫した技術基準と開発フローに従ってコードを生成するためのルートドキュメントです。

---

## 1. プロジェクト概要

プロジェクト「Norn（ノルン）」は、若手エンジニアの成長支援・伴走を行うマルチエージェント・コードレビューシステムです。GitHub Draft PR をトリガーに発火し、Azure OpenAI（Semantic Kernel コネクタ経由 [1]）を用いた 3 つの専門エージェントが `NornOrchestrator` 内で合議を行い、独自のチャット UI および GitHub 上で人間味のあるコードレビューと伴走コメントを提供します。

Phase 4 以降、Draft PR opened 時点では合議を自動開始せず、若手がチャット UI から `[開始する]` を押すまで `pending_approval` 状態で待機します（Human-in-the-loop）。

### 1.1. コアバリュー

*   **心理的安全性の確保**：厳しいエラー指摘ではなく、挑戦を称え成長を促すメンタリング。
*   **シニアの工数削減**：定型的なコードレビューとメンタリングを自動化し、シニアエンジニアをスケールさせる。
*   **マルチエージェント合議**：技術、現在、未来の 3 つのペルソナが対話を経てバランスの取れた出力を生成 [1] [2]。

---

## 2. 開発コマンド・ワークフロー

Claude Code で作業する際、以下の標準コマンドを使用してテスト、ビルド、リンティングを実行してください。本プロジェクトのパッケージ管理は **uv** を使用します。

### 2.1. 環境セットアップ

リポジトリは `backend/`（Python・uv）と `frontend/`（React・bun）の 2 ワークスペース構成です。Python 関連コマンドは原則として `backend/` で実行します。

```bash
# バックエンド依存と .env（backend/.env を作成）
cd backend
uv sync
cp .env.example .env

# フロントエンド依存
cd ../frontend && bun install
```

### 2.2. テストの実行

すべて `backend/` 配下で実行します。

**注:** テストスイートは Phase 2+3 実装後（commit `7774acd`）に一度削除され、Phase 5 Task 5.1 で再作成予定です。`backend/tests/` は現時点で空です。`pyproject.toml` に pytest 設定と dev 依存は残っています。

```bash
cd backend

# 全テストの実行（現時点ではテストファイルなし）
uv run pytest

# カバレッジの測定
uv run pytest --cov=norn
```

### 2.3. リンティング・フォーマット

```bash
cd backend

# Ruff によるコードチェック
uv run ruff check .

# Ruff による自動フォーマット
uv run ruff format .
```

### 2.4. DB マイグレーション

SQLite（開発デフォルト）でも PostgreSQL（本番）でも、スキーマ変更は **Alembic** で管理します。

```bash
cd backend

# 既存マイグレーションを反映
uv run alembic upgrade head

# 新規マイグレーションの自動生成（モデル変更後）
uv run alembic revision --autogenerate -m "describe what changed"

# 直近 1 つを取り消し
uv run alembic downgrade -1
```

SQLite 起動時のテーブル作成は FastAPI の lifespan で自動実行されるため、開発時の単発起動なら `alembic upgrade head` をスキップしても動きます。Postgres へ切り替えるときは `DATABASE_URL` を `postgresql+asyncpg://...` 形式に差し替え、必ず `alembic upgrade head` を最初に走らせてください（`asyncpg` は Phase 5 で追加予定）。

### 2.5. ローカル開発サーバーの起動

バックエンドとフロントエンドはそれぞれ別ターミナルで起動し、Vite dev server が `/chat` `/webhook` `/reviews` `/dashboard` `/healthz` `/readyz` を FastAPI にプロキシします。Phase 4 で導入した SSE / in-memory イベントバスはシングルプロセス前提のため、開発・デモは **必ず `--workers 1`** で起動してください。

```bash
# Terminal A: FastAPI Webhook + チャット REST API + SSE
cd backend && uv run uvicorn norn.api.main:app --reload --port 8000 --workers 1

# Terminal B: Vite + React dev server (http://localhost:5173)
cd frontend && bun install   # 初回のみ
cd frontend && bun dev
```

本番相当の確認（ビルド成果物を FastAPI で配信）には:

```bash
cd frontend && bun run build   # 出力先: ../backend/norn/static/
cd backend && uv run uvicorn norn.api.main:app --port 8000 --workers 1   # http://localhost:8000
```

**Azure 本番** は Static Web Apps（UI）+ Container Apps（API）の分割構成です。UI は `bun run build:swa`、API は [`backend/Dockerfile`](backend/Dockerfile) を GitHub Actions「Deploy to Azure」でデプロイします（[docs/hackathon/AZURE_DEPLOY.md](docs/hackathon/AZURE_DEPLOY.md)）。

```bash
# API のみ Docker 確認（UI は bun dev または Static Web Apps）
docker build -t norn-api:local -f backend/Dockerfile backend
docker run --rm -p 8000:8000 --env-file backend/.env -v norn-data:/data norn-api:local
```

---

## 3. 技術スタック & アーキテクチャ

*   **Orchestration**: カスタム `NornOrchestrator`（ウルド → スクルド → ヴェルダンディ → モデレーターの固定逐次合議）。Semantic Kernel は **LLM コネクタのみ** [1]
*   **Web Framework**: FastAPI (GitHub Webhook 受信 + チャット REST API + SSE)。ローカル一体確認時のみ `StaticFiles` で UI 配信可
*   **Frontend**: Vite + React (TypeScript)、bun でビルド。**Azure 本番** は Static Web Apps（`build:swa`）。ローカル一体確認は `norn/static/` へ出力して FastAPI 配信
*   **Azure 本番**: Static Web Apps（UI）+ Container Apps（API、`backend/Dockerfile`）。`VITE_API_BASE_URL` + `NORN_CORS_ORIGINS` でクロスオリジン接続
*   **Database/Storage**: SQLite (開発デフォルト, `aiosqlite`) / PostgreSQL (本番, `asyncpg` — Phase 5 予定)。SQLAlchemy 2.x async + Alembic でマイグレーション管理
*   **Runtime**: Python 3.11
*   **Package Manager**: uv (Python), bun (Frontend)
*   **APIs**: Azure OpenAI Service (gpt-4.1-mini), GitHub API (PyGithub)
*   **Trigger**: GitHub Webhook の `pull_request` イベントのうち `action == "opened"` かつ `draft == true` で `pending_approval` セッションを作成（合議は HITL 承認後に開始）

### 3.1. 環境変数（`backend/norn/config.py`）

| 変数 | デフォルト | 用途 |
|------|-----------|------|
| `AZURE_OPENAI_API_KEY` | — | Azure OpenAI API キー |
| `AZURE_OPENAI_ENDPOINT` | — | Azure OpenAI エンドポイント |
| `AZURE_OPENAI_API_VERSION` | `2025-04-14` | API バージョン |
| `AZURE_OPENAI_DEPLOYMENT` | `gpt-4.1-mini` | デプロイメント名 |
| `GITHUB_WEBHOOK_SECRET` | — | Webhook HMAC 署名検証 |
| `GITHUB_TOKEN` | — | GitHub API（Diff 取得・PR コメント） |
| `DATABASE_URL` | `sqlite+aiosqlite:///./norn.db` | DB 接続文字列 |
| `NORN_APP_BASE_URL` | `http://localhost:5173` | PR コメント内のチャットリンク |
| `NORN_CORS_ORIGINS` | — | SWA 等のフロント URL（カンマ区切り）。設定時 CORS を有効化 |
| `RUFF_EXECUTABLE` | `ruff` | 静的解析コマンドパス |
| `LOG_LEVEL` | `INFO` | ログレベル |
| `PAYLOAD_SIZE_LIMIT_BYTES` | `1048576` | Webhook ペイロード上限 |
| `NORN_AUTH_SECRET` | — | JWT 署名鍵（本番必須。未設定時は開発用にプロセスごと自動生成） |
| `NORN_AUTH_TOKEN_TTL_HOURS` | `168` | セッション有効期限（時間） |
**セッションログイン**: ログイン ID/パスワードは **`users` テーブル（DB）** のみ。`POST /auth/login` で JWT Cookie を発行し `/chat` `/reviews` `/dashboard` を常に保護。UI は `LoginGate`（デモ用クイック選択付き）。テストユーザー seed: `uv run python -m norn.cli seed-test-users`（yuki/takeshi/sakura、共通パスワード **`norn-demo`**）。LearnerSwitcher 切替は `POST /auth/switch-learner`。管理者追加: `uv run python -m norn.cli create-user --username ID --password PASS`。

---

## 4. コードスタイル & 設計規約

AI がコードを生成または修正する際は、必ず以下のガイドラインを厳守してください。

### 4.1. 非同期（Async-first）設計

Semantic Kernel および FastAPI は非同期実行を前提として設計されています。ネットワーク I/O（API コール、DB アクセス、Webhook 処理）はすべて `async/await` を使用して記述してください。

### 4.2. 型定義（Type Hints）

すべての Python コードには厳密な型定義を付与してください。

```python
async def get_agent_consensus(pr_id: int, thread_id: str) -> str | None:
    # 実装コード
    pass
```

### 4.3. エージェント設計ルール

詳細・表示名・ステータスは [docs/CONVENTIONS.md](docs/CONVENTIONS.md) を参照。

1.  **ペルソナ**（`backend/norn/agents/personas.py`）— 内部 ID は `urd` / `verdandi` / `skuld` / `moderator`。ユーザー向け `role_label` は **ウルド（メンター）・ヴェルダンディ（伴走）・スクルド（キャリア）・モデレーター（合議）**（[frontend/src/lib/personas.ts](frontend/src/lib/personas.ts) と同期）。
2.  **合議**：`NornOrchestrator` は上記 4 役の **1 ラウンド固定**（GroupChat 不使用）[2]。
3.  **HITL**：Draft PR opened → `pending_approval` → `POST /reviews/{id}/start` → `running` → `completed` / `failed`。start/skip は `pending_approval` のみ（他状態は 409）。

### 4.4. エラーハンドリング & 堅牢性

*   LLM API のレート制限や一時的なタイムアウトに備え、`tenacity` 等を用いたリトライロジックを組み込んでください（`AzureLLMClient` に実装済み）。
*   GitHub API や合議処理への書き込みが失敗した場合でも、FastAPI の Webhook スレッドをブロックしないよう、`BackgroundTasks` を使用してください（導入済み）。

### 4.5. ReviewSession.status

`pending_approval` / `running` / `completed` / `failed` / `skipped` の 5 値。enum 制約は DB に設けず、コード側で扱います。

---

## 5. ドキュメント索引（機能追加時）

| ドキュメント | 用途 |
|--------------|------|
| [docs/FILE_MAP.md](docs/FILE_MAP.md) | **変更箇所の早見表**（バックエンド / フロント） |
| [docs/FRONTEND.md](docs/FRONTEND.md) | 画面構成・ドロワー・API クライアント・CSS |
| [docs/CONVENTIONS.md](docs/CONVENTIONS.md) | カタカナ表示名・HITL 409・スレッド削除 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | システム構成・DB・REST/SSE 一覧 |
| [docs/ROADMAP.md](docs/ROADMAP.md) | フェーズ・未実装 |

フロントの製品説明は `frontend/src/components/AboutPage.tsx`（ナビ「Norn とは」）。

---

## 6. 参考文献

[1] Microsoft, "Semantic Kernel: Integrate cutting-edge LLM technology quickly and easily into your apps."  
[2] SecondTalent, "How Enterprises Are Using AutoGen in 2026," May 2026.
