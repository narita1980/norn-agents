# Norn API — Azure Container Apps (frontend is on Static Web Apps)
# Build: docker build -t norn-api .
# Run:   docker run -p 8000:8000 --env-file backend/.env -v norn-data:/data norn-api

FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && mkdir -p /data

COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev

COPY backend/ ./
COPY backend/docker-entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENV PORT=8000
ENV DATABASE_URL=sqlite+aiosqlite:////data/norn.db
ENV PYTHONUNBUFFERED=1

EXPOSE 8000
VOLUME ["/data"]

ENTRYPOINT ["/entrypoint.sh"]
