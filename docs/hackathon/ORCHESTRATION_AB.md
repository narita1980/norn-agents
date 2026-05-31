# オーケストレーション A/B 比較

`NORN_ORCHESTRATION_MODE` で固定逐次（`fixed`）と SK AgentGroupChat（`group_chat`）を切り替えられます。

## 環境変数

| 変数 | デフォルト | 説明 |
|------|-----------|------|
| `NORN_ORCHESTRATION_MODE` | `group_chat` | `fixed` または `group_chat` |
| `NORN_GROUP_CHAT_MAX_ITERATIONS` | `7` | GroupChat の女神ターン上限 |

## 比較手順

1. 同一 Draft PR（または手動登録）を用意
2. `NORN_ORCHESTRATION_MODE=fixed` で合議 → 所要時間・must_fix 件数を記録
3. スレッド削除 or 新規 PR で `NORN_ORCHESTRATION_MODE=group_chat` で再実行
4. 右パネル SSE・GitHub コメント・ダッシュボードを比較

## 記録シート

| # | モード | 女神ターン数 | 合議秒数 | must_fix | tone | メモ |
|---|--------|-------------|---------|----------|------|------|
| 1 | fixed | 3 | | | | |
| 2 | group_chat | 3–5 | | | | |

## ロールバック

品質やレイテンシが悪化した場合:

```bash
NORN_ORCHESTRATION_MODE=fixed
```

固定逐次は [`orchestrator.py`](../backend/norn/agents/orchestrator.py) の `_run_full` 内分岐で引き続き利用可能です。
