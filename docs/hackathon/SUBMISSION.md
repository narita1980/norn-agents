# 提出チェックリスト — Microsoft Agent Hackathon 2026

**部門**: 個人部門  
**締切**: 2026/6/1 23:59  
**提出ページ**: https://zenn.dev/hackathons/microsoft-agent-hackathon-2026 （「申し込む」→ ログイン後に提出フォーム）

---

## コピペ用 URL 一覧

| フィールド | 値 |
|------------|-----|
| **成果物 URL（Web アプリ）** | https://gentle-mushroom-0e3c9b500.7.azurestaticapps.net/ |
| **Zenn 記事 URL** | （Zenn 公開後の URL を貼る。例: `https://zenn.dev/narita1980/articles/...`） |
| **デモ動画 URL** | （YouTube 限定公開 URL — [`record-demo.sh`](./record-demo.sh) / [`VIDEO_SCRIPT.md`](./VIDEO_SCRIPT.md) 参照） |
| **GitHub（任意）** | https://github.com/narita1980/norn-agents |

---

## Zenn 記事の公開手順

1. https://zenn.dev/dashboard にログイン
2. 「新規記事」→ エディタを開く
3. [`docs/hackathon/zenn-article.md`](../hackathon/zenn-article.md) の本文（frontmatter 除く or 含む）を貼り付け  
   - または GitHub 連携で `articles/norns-agent-hackathon-2026.md` を同期
4. `published: true` で公開
5. 公開 URL を上表「Zenn 記事 URL」に記入し、提出フォームに入力

---

## デモ動画の録画手順

台本: [`VIDEO_SCRIPT.md`](./VIDEO_SCRIPT.md)

1. シークレットウィンドウで https://gentle-mushroom-0e3c9b500.7.azurestaticapps.net/ を開く
2. `yuki` / `norn-demo` でログイン
3. 手動 PR 登録 → `[開始する]` → 合議 SSE（0:50–1:50 を等速で）
4. QuickTime / OBS で 1920×1080 録画（3〜5 分）
5. YouTube に **限定公開** でアップロード
6. URL を提出フォームに入力

---

## 審査員向けデモログイン

| ID | パスワード | レベル |
|----|-----------|--------|
| `yuki` | `norn-demo` | 若手 |
| `takeshi` | `norn-demo` | 中級 |
| `sakura` | `norn-demo` | 上級 |

**初回デプロイ後**、Container Apps でテストユーザを seed してください（未実行だとログイン 401）:

```bash
az containerapp exec --name norn --resource-group norn-agents-rg \
  --command "uv run alembic upgrade head && uv run python -m norn.cli seed-test-users"
```

---

## 提出前の最終確認

- [ ] SWA デモ URL が開き、ログインできる
- [ ] 手動 PR 登録 → 合議 → 右パネル SSE が動く
- [ ] Zenn 記事が公開済み（URL 取得）
- [ ] YouTube 動画がアップロード済み（URL 取得）
- [ ] GitHub リポジトリが public
- [ ] 提出フォーム送信完了
