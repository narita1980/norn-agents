#!/usr/bin/env bash
# Deploy Norn to Azure Container Apps (hackathon submission URL).
#
# Prerequisites:
#   az login   (local only — GitHub Actions uses azure/login)
#   az extension add --name containerapp --upgrade
#
# Usage (local):
#   export RESOURCE_GROUP=norn-hackathon-rg
#   export LOCATION=japaneast
#   export ACA_ENV=norn-env
#   export ACA_APP=norn
#   export ACR_NAME=nornhackathon   # globally unique, lowercase alphanumeric
#   export IMAGE_TAG=v1
#   ./deploy/azure-deploy.sh
#
# Usage (CI — set by GitHub Actions):
#   USE_ACR_BUILD=1 IMAGE_TAG=$GITHUB_SHA ./deploy/azure-deploy.sh
#
# Optional secrets (local env or GitHub Actions secrets):
#   AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT
#   NORN_GITHUB_TOKEN (maps to GITHUB_TOKEN in the app), GITHUB_WEBHOOK_SECRET
#   NORN_BASIC_AUTH_USERNAME, NORN_BASIC_AUTH_PASSWORD

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

RESOURCE_GROUP="${RESOURCE_GROUP:-norn-hackathon-rg}"
LOCATION="${LOCATION:-japaneast}"
ACA_ENV="${ACA_ENV:-norn-env}"
ACA_APP="${ACA_APP:-norn}"
ACR_NAME="${ACR_NAME:-nornhackathon}"
IMAGE_TAG="${IMAGE_TAG:-latest}"
USE_ACR_BUILD="${USE_ACR_BUILD:-0}"

echo "==> Resource group: $RESOURCE_GROUP ($LOCATION)"
az group create --name "$RESOURCE_GROUP" --location "$LOCATION" --output none

echo "==> Azure Container Registry: $ACR_NAME"
if ! az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" &>/dev/null; then
  az acr create --resource-group "$RESOURCE_GROUP" --name "$ACR_NAME" --sku Basic --admin-enabled true --output none
fi

ACR_LOGIN_SERVER="$(az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" --query loginServer -o tsv)"
IMAGE="$ACR_LOGIN_SERVER/norn:$IMAGE_TAG"

echo "==> Build & push image: $IMAGE"
if [ "$USE_ACR_BUILD" = "1" ]; then
  az acr build --registry "$ACR_NAME" --image "norn:$IMAGE_TAG" --file Dockerfile .
else
  az acr login --name "$ACR_NAME"
  docker build -t "$IMAGE" .
  docker push "$IMAGE"
fi

echo "==> Container Apps environment: $ACA_ENV"
if ! az containerapp env show --name "$ACA_ENV" --resource-group "$RESOURCE_GROUP" &>/dev/null; then
  az containerapp env create \
    --name "$ACA_ENV" \
    --resource-group "$RESOURCE_GROUP" \
    --location "$LOCATION" \
    --output none
fi

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

echo "==> Sync NORN_APP_BASE_URL=$APP_URL"
az containerapp update \
  --name "$ACA_APP" \
  --resource-group "$RESOURCE_GROUP" \
  --set-env-vars "NORN_APP_BASE_URL=$APP_URL" \
  --output none

if [ -n "${AZURE_OPENAI_API_KEY:-}" ] && [ -n "${AZURE_OPENAI_ENDPOINT:-}" ]; then
  echo "==> Configure application secrets"
  DEPLOYMENT="${AZURE_OPENAI_DEPLOYMENT:-gpt-4.1-mini}"

  SECRET_ARGS=(
    "azure-openai-api-key=${AZURE_OPENAI_API_KEY}"
  )
  ENV_ARGS=(
    "AZURE_OPENAI_API_KEY=secretref:azure-openai-api-key"
    "AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT}"
    "AZURE_OPENAI_DEPLOYMENT=${DEPLOYMENT}"
  )

  if [ -n "${NORN_GITHUB_TOKEN:-}" ]; then
    SECRET_ARGS+=("github-token=${NORN_GITHUB_TOKEN}")
    ENV_ARGS+=("GITHUB_TOKEN=secretref:github-token")
  fi

  if [ -n "${GITHUB_WEBHOOK_SECRET:-}" ]; then
    SECRET_ARGS+=("github-webhook-secret=${GITHUB_WEBHOOK_SECRET}")
    ENV_ARGS+=("GITHUB_WEBHOOK_SECRET=secretref:github-webhook-secret")
  fi

  if [ -n "${NORN_BASIC_AUTH_USERNAME:-}" ] && [ -n "${NORN_BASIC_AUTH_PASSWORD:-}" ]; then
    SECRET_ARGS+=("basic-auth-password=${NORN_BASIC_AUTH_PASSWORD}")
    ENV_ARGS+=(
      "NORN_BASIC_AUTH_USERNAME=${NORN_BASIC_AUTH_USERNAME}"
      "NORN_BASIC_AUTH_PASSWORD=secretref:basic-auth-password"
    )
  fi

  if [ -n "${NORN_CORS_ORIGINS:-}" ]; then
    ENV_ARGS+=("NORN_CORS_ORIGINS=${NORN_CORS_ORIGINS}")
  fi

  az containerapp secret set \
    --name "$ACA_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --secrets "${SECRET_ARGS[@]}" \
    --output none

  az containerapp update \
    --name "$ACA_APP" \
    --resource-group "$RESOURCE_GROUP" \
    --set-env-vars "${ENV_ARGS[@]}" \
    --output none
else
  echo "==> Skipping secret sync (AZURE_OPENAI_API_KEY / AZURE_OPENAI_ENDPOINT not set)"
fi

echo ""
echo "Deployed: $APP_URL"
echo ""
echo "Next steps:"
echo "  1. Set secrets in Azure Portal or GitHub Actions secrets (if not configured)"
echo "  2. Configure GitHub Webhook: $APP_URL/webhook/github"
echo "  3. Health check: $APP_URL/healthz"
