#!/usr/bin/env bash
# Generate frontend/staticwebapp.config.json with optional API reverse proxy.
#
# When NORN_API_BASE_URL is set, /chat /reviews /dashboard are proxied to the backend
# so the browser keeps same-origin requests (SSE / Basic Auth friendly).
#
# Usage:
#   NORN_API_BASE_URL=https://norn.xxx.azurecontainerapps.io ./deploy/generate-swa-config.sh
#   ./deploy/generate-swa-config.sh frontend/staticwebapp.config.json

set -euo pipefail

OUTPUT="${1:-frontend/staticwebapp.config.json}"
BACKEND="${NORN_API_BASE_URL:-}"
BACKEND="${BACKEND%/}"

mkdir -p "$(dirname "$OUTPUT")"

if [ -z "$BACKEND" ]; then
  cat > "$OUTPUT" << 'EOF'
{
  "navigationFallback": {
    "rewrite": "/index.html",
    "exclude": ["/assets/*", "/*.{css,scss,js,png,gif,ico,jpg,svg,woff,woff2,txt,json,map}"]
  }
}
EOF
  echo "Wrote $OUTPUT (static UI only — set NORN_API_BASE_URL to enable API proxy)"
  exit 0
fi

cat > "$OUTPUT" << EOF
{
  "routes": [
    { "route": "/chat/*", "rewrite": "${BACKEND}/chat/*" },
    { "route": "/reviews/*", "rewrite": "${BACKEND}/reviews/*" },
    { "route": "/dashboard/*", "rewrite": "${BACKEND}/dashboard/*" },
    { "route": "/healthz", "rewrite": "${BACKEND}/healthz" },
    { "route": "/readyz", "rewrite": "${BACKEND}/readyz" }
  ],
  "navigationFallback": {
    "rewrite": "/index.html",
    "exclude": [
      "/chat/*",
      "/reviews/*",
      "/dashboard/*",
      "/healthz",
      "/readyz",
      "/assets/*",
      "/*.{css,scss,js,png,gif,ico,jpg,svg,woff,woff2,txt,json,map}"
    ]
  }
}
EOF

echo "Wrote $OUTPUT (API proxy -> ${BACKEND})"
