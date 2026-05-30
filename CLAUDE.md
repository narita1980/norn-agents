# CLAUDE.md — Project Norn (norn-agents)

このファイルは、Claude Codeやその他のAIコーディングアシスタントがプロジェクト「Norn（ノルン）」を深く理解し、一貫した技術基準と開発フローに従ってコードを生成するためのルートドキュメントです。

---

## 1. プロジェクト概要

プロジェクト「Norn（ノルン）」は、若手エンジニアの成長支援・伴走を行うマルチエージェント・コードレビューシステムです。GitHub Draft PRをトリガーに発火し、Azure上のSemantic Kernel [1] を用いた3つの専門エージェントが裏で合議を行い、独自のチャットUIおよびGitHub上で人間味のあるコードレビューと伴走コメントを提供します。

### 1.1. コアバリュー
*   **心理的安全性の確保**：厳しいエラー指摘ではなく、挑戦を称え成長を促すメンタリング。
*   **シニアの工数削減**：定型的なコードレビューとメンタリングを自動化し、シニアエンジニアをスケールさせる。
*   **マルチエージェント合議**：技術、現在、未来の3つのペルソナが対話を経てバランスの取れた出力を生成 [1] [2]。

---

## 2. 開発コマンド・ワークフロー

Claude Codeで作業する際、以下の標準コマンドを使用してテスト、ビルド、リンティングを実行してください。本プロジェクトのパッケージ管理は **uv** を使用します。

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
```bash
cd backend

# 全テストの実行
uv run pytest

# 特定のテストファイルの実行
uv run pytest tests/test_webhooks.py

# カバレッジの測定
uv run pytest --cov=norn
```

### 2.3. リンティング・フォーマット
```bash
cd backend

# Ruffによるコードチェック
uv run ruff check .

# Ruffによる自動フォーマット
uv run ruff format .
```

### 2.4. ローカル開発サーバーの起動
バックエンドとフロントエンドはそれぞれ別ターミナルで起動し、Vite dev server が `/chat` `/webhook` `/healthz` `/readyz` を FastAPI にプロキシします。
```bash
# Terminal A: FastAPI Webhook + チャット REST API
cd backend && uv run uvicorn norn.api.main:app --reload --port 8000

# Terminal B: Vite + React dev server (http://localhost:5173)
cd frontend && bun install   # 初回のみ
cd frontend && bun dev
```
本番相当の確認（ビルド成果物を FastAPI で配信）には:
```bash
cd frontend && bun run build   # 出力先: ../backend/norn/static/
cd backend && uv run uvicorn norn.api.main:app --port 8000   # http://localhost:8000
```

---

## 3. 技術スタック & アーキテクチャ

*   **Orchestration Framework**: Microsoft Semantic Kernel (Python SDK) [1]
*   **Web Framework**: FastAPI (GitHub Webhook 受信 + チャット REST API + 静的フロントエンド配信)
*   **Frontend**: Vite + React (TypeScript)、bun でビルド。出力先 `norn/static/` を FastAPI StaticFiles 経由で配信
*   **Database/Storage**: PostgreSQL (SQLAlchemy) + Azure Blob Storage（Phase 3 以降）
*   **Runtime**: Python 3.11
*   **Package Manager**: uv (Python), bun (Frontend)
*   **APIs**: Azure OpenAI Service (GPT-4o / GPT-4o-mini), GitHub API (PyGithub)
*   **Trigger**: GitHub Webhook の `pull_request` イベントのうち `action == "opened"` かつ `draft == true` のみエージェントをディスパッチ（その他は素通り）

---

## 4. コードスタイル & 設計規約

AIがコードを生成または修正する際は、必ず以下のガイドラインを厳守してください。

### 4.1. 非同期（Async-first）設計
Semantic KernelおよびFastAPIは非同期実行を前提として設計されています。ネットワークI/O（APIコール、DBアクセス、Webhook処理）はすべて `async/await` を使用して記述してください。

### 4.2. 型定義（Type Hints）
すべてのPythonコードには厳密な型定義を付与してください。
```python
async def get_agent_consensus(pr_id: int, thread_id: str) -> str | None:
    # 実装コード
    pass
```

### 4.3. エージェント設計ルール（Phase 2 で Semantic Kernel ベースに再定義予定）
1.  **エージェントのペルソナ分離**：
    *   `UrdAgent`（技術）：厳格なLinter、セキュリティ、ベストプラクティス。
    *   `VerdandiAgent`（現在）：共感、労い、心理的安全性の確保、段階的な改善。
    *   `SkuldAgent`（未来）：成長機会、学習リソースの提示、将来のアーキテクチャ予言。
2.  **合議の無限ループ防止**：
    マルチエージェント対話を構築する際は、必ず最大ターン数を設定し、議論を収束させるための `ConsensusModerator` 相当のエージェントを配置してください [2]。

### 4.4. エラーハンドリング & 堅牢性
*   LLM APIのレート制限や一時的なタイムアウトに備え、`tenacity` 等を用いたリトライロジックを組み込んでください。
*   GitHub APIやチャット配信への書き込みが失敗した場合でも、FastAPIのWebhookスレッドをブロックしないよう、バックグラウンドタスクまたはタスクキューを使用してください（Phase 2 で導入）。

---

## 5. 参考文献
[1] Microsoft, "Semantic Kernel: Integrate cutting-edge LLM technology quickly and easily into your apps."
[2] SecondTalent, "How Enterprises Are Using AutoGen in 2026," May 2026.
