#!/usr/bin/env bash
# Bootstrap Azure Static Web Apps for Norn frontend.
#
# Prerequisites: az login
#
# Usage:
#   export RESOURCE_GROUP=norn-hackathon-rg
#   export SWA_NAME=norn-frontend
#   export LOCATION=eastasia   # SWA は japaneast 非対応のため East Asia を推奨
#   ./deploy/azure-swa-bootstrap.sh
#
# 出力されたデプロイトークンを GitHub Secret AZURE_STATIC_WEB_APPS_API_TOKEN に登録。

set -euo pipefail

RESOURCE_GROUP="${RESOURCE_GROUP:-norn-hackathon-rg}"
SWA_NAME="${SWA_NAME:-norn-frontend}"
LOCATION="${LOCATION:-eastasia}"
SKU="${SKU:-Free}"

echo "==> Resource group: $RESOURCE_GROUP ($LOCATION)"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

echo "==> Static Web App: $SWA_NAME"
if ! az staticwebapp show --name "$SWA_NAME" --resource-group "$RESOURCE_GROUP" &>/dev/null; then
  az staticwebapp create \
    --name "$SWA_NAME" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --sku "$SKU" \
    --output none
fi

HOSTNAME="$(az staticwebapp show \
  --name "$SWA_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query defaultHostname -o tsv)"
TOKEN="$(az staticwebapp secrets list \
  --name "$SWA_NAME" \
  --resource-group "$RESOURCE_GROUP" \
  --query properties.apiKey -o tsv)"

echo ""
echo "Static Web App URL: https://${HOSTNAME}"
echo ""
echo "GitHub Secret を登録:"
echo "  AZURE_STATIC_WEB_APPS_API_TOKEN=${TOKEN}"
echo ""
echo "バックエンド構築後（Container Apps 等）:"
echo "  1. GitHub Secret NORN_API_BASE_URL=https://<backend-fqdn>"
echo "  2. GitHub Secret NORN_CORS_ORIGINS=https://${HOSTNAME}  （直接 API 接続時）"
echo "  3. Container Apps の NORN_APP_BASE_URL=https://${HOSTNAME}"
echo "  4. frontend ワークフローを再実行（API プロキシ設定が反映される）"
