# プロジェクト規約

実装・レビュー・ユーザー向け文言の一貫性のための参照です。

## プロダクト名

| 表記 | 用途 |
|------|------|
| **Norns** | ロゴ・英語表記・チャット/UI・PR コメント |
| **ノルンズ** | 日本語読み（ナビサブタイトル・About で明示） |

内部コード（`norn` パッケージ、`NornOrchestrator`、`NORN_*` 環境変数等）は変更しない。

## 合議エージェント（3 女神 + モデレーター）

### 内部 ID（変更しない）

`urd`, `verdandi`, `skuld`, `moderator` — DB・SSE・オーケストレータのキー。

### ユーザー向け表示（カタカナ + 役割）

| ID | 表示名 | 更新箇所 |
|----|--------|----------|
| `urd` | ウルド（メンター） | `frontend/src/lib/personas.ts`, `backend/norn/agents/personas.py` |
| `verdandi` | ヴェルダンディ（伴走） | 同上 |
| `skuld` | スクルド（キャリア） | 同上 |
| `moderator` | モデレーター（合議） | 同上 |

プロンプト内の相互参照もカタカナで書く（例: 「ウルドの指摘」）。英語名（Urd）を UI に出さない。

## ReviewSession とテストユーザー（user_level）

| 項目 | 内容 |
|------|------|
| 一意キー | `(repository_name, pr_number, user_level)` — 同一 PR でも junior / mid / senior で別セッション |
| Webhook | Draft PR opened は **`junior` のみ** 自動登録 |
| 手動登録 | `POST /reviews/manual` — 選択中のテストユーザー（`user_level`）ごとに独立 |
| チャットスレッド | 各セッションは `chat_thread_id` と 1:1。スレッドの `user_level` は先頭メッセージで決まる |

## ReviewSession.status

| 値 | 日本語（サイドバー） | 意味 |
|----|----------------------|------|
| `pending_approval` | 承認待ち | Start/Skip 可能 |
| `running` | 合議中 | 合議バックグラウンド実行中 |
| `completed` | 完了 | 正常終了 |
| `failed` | 失敗 | 合議または投稿失敗 |
| `skipped` | スキップ | 若手がスキップ選択 |

### HITL API の制約

`POST /reviews/{session_id}/start` と `/skip` は **`pending_approval` のときだけ** 成功する。

それ以外の状態で呼ぶと **409** と次の `detail`（英語）:

```text
session is not pending_approval (current: running)
```

| `current` | ユーザーへの説明 |
|-----------|------------------|
| `running` | すでに合議開始済み。待つか合議ライブを見る。二重「開始する」や古い承認バナーからの再押下で起きやすい |
| `completed` / `failed` / `skipped` | 終了済み。新しい Draft PR または手動登録で新セッション |

**改善メモ（未実装）**: API `detail` の日本語化、または `running` 時は `ApprovalBanner` を出さない（`session.status` をフロントで参照）。

## スレッド削除

`DELETE /chat/threads/{thread_id}`:

1. 全 `chat_messages`（当該 `thread_id`）
2. `review_sessions.chat_thread_id` が一致する行があれば **セッションごと削除**（`agent_conversations` は CASCADE）

`running` 中も削除可（バックグラウンド合議は失敗しうる）。

## チャットメッセージの HITL

承認 UI は `chat_messages.action_payload`:

```json
{ "type": "start_or_skip", "session_id": "...", "repository": "...", "pr_number": 1, ... }
```

フロントは **最新 1 件** の `start_or_skip` にだけボタン表示（`MessageList.findLatestPendingIndex`）。セッション状態とは未連動のため、上記 409 と組み合わさることがある。

## エラーメッセージ方針

- **API**: FastAPI `HTTPException(detail=...)` — 現状英語が多い
- **フロント**: `api.ts` の `jsonOrThrow` が `detail` をそのまま `Error.message` にする
- 新規ユーザー向け機能では **日本語 `detail`** またはフロントでマッピングを推奨

## コミット・PR

リポジトリのユーザールールに従い、**明示指示がない限り git commit / push しない**。
