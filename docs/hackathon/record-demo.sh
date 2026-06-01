#!/usr/bin/env bash
# Norns デモ動画録画の補助スクリプト（macOS + QuickTime 推奨）
# 使い方: ./docs/hackathon/record-demo.sh
# 手動: QuickTime → 新規画面収録 → VIDEO_SCRIPT.md に従って操作

set -euo pipefail

DEMO_URL="https://gentle-mushroom-0e3c9b500.7.azurestaticapps.net/"
OUTPUT="${1:-./norns-demo-$(date +%Y%m%d).mp4}"

echo "=== Norns デモ動画録画 ==="
echo "デモ URL: ${DEMO_URL}"
echo "ログイン: yuki / norn-demo"
echo "台本: docs/hackathon/VIDEO_SCRIPT.md"
echo ""
echo "1. ブラウザでデモ URL を開く"
open "${DEMO_URL}" 2>/dev/null || echo "   → ${DEMO_URL}"
echo ""
echo "2. QuickTime Player → ファイル → 新規画面収録（または OBS）"
echo "3. 手動 PR 登録 → [開始する] → 合議 SSE を等速で録画（3〜5 分）"
echo "4. YouTube に限定公開でアップロード"
echo "5. URL を docs/hackathon/SUBMISSION.md に追記し、提出フォームに入力"
echo ""

if command -v ffmpeg >/dev/null 2>&1; then
  echo "ffmpeg 検出: 画面録画例（要 macOS 画面収録権限）"
  echo "  ffmpeg -f avfoundation -i \"1:0\" -r 30 \"${OUTPUT}\""
  echo "  Ctrl+C で停止"
fi
