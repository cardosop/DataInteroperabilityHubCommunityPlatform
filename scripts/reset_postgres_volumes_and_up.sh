#!/usr/bin/env bash
# Reset Postgres-related Docker volumes (old data causing slow startup) and bring stack up.
# Use this when postgres/prefect-db take forever to start due to old/corrupt data.
#
# Usage: ./scripts/reset_postgres_volumes_and_up.sh [--detach]
# From repo root: ./scripts/reset_postgres_volumes_and_up.sh
#
# If you see "container name already in use" errors, run the script again, or:
#   docker rm -f $(docker ps -aq --filter 'name=hub-') 2>/dev/null; docker compose up -d

set -e
cd "$(dirname "$0")/.."
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-datainteroperabilityhub}"
DETACH=""
if [[ "${1:-}" == "--detach" ]]; then DETACH="--detach"; fi

echo "== Stopping stack (timeout 30s)..."
docker compose down -t 30 --remove-orphans || true

echo "== Removing any leftover hub-* containers (avoid name conflicts)..."
for id in $(docker ps -aq --filter "name=hub-" 2>/dev/null); do
  docker rm -f "$id" 2>/dev/null || true
done

echo "== Removing Postgres-related volumes..."
for v in "${COMPOSE_PROJECT_NAME}_pgdata" "${COMPOSE_PROJECT_NAME}_prefect-db-data" "${COMPOSE_PROJECT_NAME}_ckan-test-db-data"; do
  if docker volume inspect "$v" &>/dev/null; then
    docker volume rm "$v" 2>/dev/null || { echo "Warning: could not remove $v (may be in use)"; true; }
  fi
done

# Dev volume names if using docker-compose.dev.yml
for v in "${COMPOSE_PROJECT_NAME}_pgdata-dev" "${COMPOSE_PROJECT_NAME}_prefect-db-data-dev" "${COMPOSE_PROJECT_NAME}_ckan-test-db-data-dev"; do
  if docker volume inspect "$v" &>/dev/null; then
    docker volume rm "$v" 2>/dev/null || true
  fi
done

echo "== Starting stack..."
docker compose up $DETACH

if [[ -n "$DETACH" ]]; then
  echo "== Waiting 60s for healthchecks..."
  sleep 60
  docker compose ps
fi
