#!/usr/bin/env bash
# Bring the stack up without contacting a registry.
set -euo pipefail

BUNDLE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE=(docker compose --project-name material-platform -f "$BUNDLE/app/docker-compose.yml")

if [[ ! -f "$BUNDLE/app/.env" ]]; then
  echo "missing $BUNDLE/app/.env — copy .env.example and set secrets" >&2
  exit 1
fi

mkdir -p "$BUNDLE/inbox"
ln -sfn "$BUNDLE/inbox" "$BUNDLE/app/inbox"
ln -sfn "$BUNDLE/app/.env" "$BUNDLE/.env"
# Compose volume ./dagster.yaml is relative to the compose file directory.
if [[ ! -f "$BUNDLE/app/dagster.yaml" ]]; then
  echo "missing app/dagster.yaml" >&2
  exit 1
fi

cd "$BUNDLE/app"
"${COMPOSE[@]}" up -d --pull never --no-build

echo "== alembic =="
"${COMPOSE[@]}" run --rm --no-deps api alembic upgrade head

echo "stack is up."
echo "  API        http://127.0.0.1:8000"
echo "  Dagster    http://127.0.0.1:3000"
echo "  Langfuse   http://127.0.0.1:3100"
echo "Inbox: $BUNDLE/inbox"
echo "Web UI: cd $BUNDLE/web && npm run preview -- --host 127.0.0.1 --port 5173"
