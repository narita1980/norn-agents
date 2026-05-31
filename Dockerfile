# Norn — single-container image for Azure Container Apps / App Service
# Build: docker build -t norn .
# Run:   docker run -p 8000:8000 --env-file backend/.env norn

FROM oven/bun:1.2 AS frontend
WORKDIR /build
COPY frontend/package.json frontend/bun.lock ./frontend/
COPY frontend/ ./frontend/
RUN cd frontend && bun install --frozen-lockfile && bun run build

FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim AS backend
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /data

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend/ ./
COPY --from=frontend /build/backend/norn/static ./norn/static

COPY deploy/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PORT=8000
ENV DATABASE_URL=sqlite+aiosqlite:////data/norn.db
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
VOLUME ["/data"]

ENTRYPOINT ["/entrypoint.sh"]
