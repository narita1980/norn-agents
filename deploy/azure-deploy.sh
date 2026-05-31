#!/usr/bin/env bash
# Deploy Norn to Azure Container Apps (hackathon submission URL).
#
# Prerequisites:
#   az login
#   az extension add --name containerapp --upgrade
#
# Usage:
#   export RESOURCE_GROUP=norn-hackathon-rg
#   export LOCATION=japaneast
#   export ACA_ENV=norn-env
#   export ACA_APP=norn
#   export ACR_NAME=nornhackathon   # globally unique, lowercase alphanumeric
#   export IMAGE_TAG=v1
#   ./deploy/azure-deploy.sh
#
# After deploy, set secrets (Azure OpenAI, GitHub) via Portal or:
#   az containerapp secret set -g "$RESOURCE_GROUP" -n "$ACA_APP" \
#     --secrets azure-openai-api-key=... github-token=... github-webhook-secret=...

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RESOURCE_GROUP="${RESOURCE_GROUP:-norn-hackathon-rg}"
LOCATION="${LOCATION:-japaneast}"
ACA_ENV="${ACA_ENV:-norn-env}"
ACA_APP="${ACA_APP:-norn}"
ACR_NAME="${ACR_NAME:-nornhackathon}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
SKU="${SKU:-Consumption}"

echo "==> Resource group: $RESOURCE_GROUP ($LOCATION)"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

echo "==> Azure Container Registry: $ACR_NAME"
if ! az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" &>/dev/null; then
  az acr create --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" --sku Basic --admin-enabled true --output none
fi

ACR_LOGIN_SERVER="$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query loginServer -o tsv)"
IMAGE="$ACR_LOGIN_SERVER/norn:$IMAGE_TAG"

echo "==> Build & push image: $IMAGE"
az acr login --name "$ACR_NAME"
docker build -t "$IMAGE" .
docker push "$IMAGE"

echo "==> Container Apps environment: $ACA_ENV"
if ! az containerapp env show --name "$ACA_ENV" --resource-group "$RESOURCE_GROUP" &>/dev/null; then
  az containerapp env create \
    --name "$ACA_ENV" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --output none
fi

ENV_ID="$(az containerapp env show --name "$ACA_ENV" --resource-group "$RESOURCE_GROUP" --query id -o tsv)"
ACR_USER="$(az acr credential show --name "$ACR_NAME" --query username -o tsv)"
ACR_PASS="$(az acr credential show --name "$ACR_NAME" --query 'passwords[0].value' -o tsv)"

if az containerapp show --name "$ACA_APP" --resource-group "$RESOURCE_GROUP" &>/dev/null; then
  echo "==> Update existing Container App: $ACA_APP"
  az containerapp update \
    --name "$ACA_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --image "$IMAGE" \
    --output none
else
  echo "==> Create Container App: $ACA_APP"
  az containerapp create \
    --name "$ACA_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --environment "$ACA_ENV" \
    --image "$IMAGE" \
    --registry-server "$ACR_LOGIN_SERVER" \
    --registry-username "$ACR_USER" \
    --registry-password "$ACR_PASS" \
    --target-port 8000 \
    --ingress external \
    --min-replicas 1 \
    --max-replicas 1 \
    --cpu 1.0 \
    --memory 2.0Gi \
    --env-vars \
      LOG_LEVEL=INFO \
      DATABASE_URL=sqlite+aiosqlite:////data/norn.db \
      NORN_APP_BASE_URL=https://placeholder.example.com \
    --output none
fi

FQDN="$(az containerapp show --name "$ACA_APP" --resource-group "$RESOURCE_GROUP" --query properties.configuration.ingress.fqdn -o tsv)"
APP_URL="https://${FQDN}"

echo ""
echo "Deployed: $APP_URL"
echo ""
echo "Next steps:"
echo "  1. Set secrets in Azure Portal (Container App > Secrets) or az containerapp secret set"
echo "  2. Update env: NORN_APP_BASE_URL=$APP_URL"
echo "  3. Configure GitHub Webhook: $APP_URL/webhook/github"
echo "  4. Health check: $APP_URL/healthz"
