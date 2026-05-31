#!/bin/sh
set -eu

PORT="${PORT:-8000}"

# Apply Alembic migrations when the DB URL is not the default dev sqlite file.
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  uv run alembic upgrade head || echo "alembic upgrade skipped or failed — continuing"
fi

exec uv run uvicorn norn.api.main:app \
  --host 0.0.0.0 \
  --port "${PORT}" \
  --workers 1
