#!/usr/bin/env bash
# Clean and start the test stack (docker-compose.test.yml).
# Use when: "Conflict. The container name ... is already in use" (e.g. hash-prefixed
# containers from a different compose project: 0f4a75f7827d_hub-test-redis-events).
#
# Usage: ./scripts/clean-test-stack.sh [--volumes]
#   --volumes   Remove volumes (postgres-test-data, prefect-db-test-data, etc.).
#               Use when old data causes slow Postgres startup. Fresh init on next up.
#
# From repo root: export COMPOSE_FILE=docker-compose.test.yml; ./scripts/clean-test-stack.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

export COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.test.yml}"
REMOVE_VOLUMES=""
[[ "${1:-}" == "--volumes" ]] && REMOVE_VOLUMES="-v"
ENV_ARGS=""
[[ -f .env.test ]] && ENV_ARGS="--env-file .env.test"

echo "== Stopping test stack (COMPOSE_FILE=$COMPOSE_FILE)${REMOVE_VOLUMES:+ with volumes}..."
docker compose -f "$COMPOSE_FILE" $ENV_ARGS down $REMOVE_VOLUMES --remove-orphans -t 90 2>/dev/null || true

echo "== Removing any remaining test containers (incl. hash-prefixed names)..."
removed=0
while IFS= read -r name; do
  [[ -z "$name" ]] && continue
  if docker rm -f "$name" 2>/dev/null; then
    echo "  removed: $name"
    removed=$((removed + 1))
  fi
done < <(docker ps -a --format "{{.Names}}" 2>/dev/null | grep -E 'hub-test|_hub-test-' || true)
[[ $removed -gt 0 ]] && echo "  ($removed container(s) removed)" || echo "  (none found)"

echo "== Starting test stack (all services matching docker-compose.yml)..."
docker compose -f "$COMPOSE_FILE" $ENV_ARGS up -d

echo "== Done. Wait for health (e.g. 60–90s for api), then: docker compose ps -a"
