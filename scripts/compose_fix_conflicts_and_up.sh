#!/usr/bin/env bash
# Remove only containers that cause "name already in use" and run compose up -d.
# Use when: docker compose up -d fails with Conflict but you don't want a full down.
# Removes the given names (ghost containers), then docker compose up -d.
#
# Usage: ./scripts/compose_fix_conflicts_and_up.sh [name1 name2 ...]
# With no args, removes commonly conflicting names then up -d.
# Example: ./scripts/compose_fix_conflicts_and_up.sh hub-worker hub-event-schema-registry

set -e
cd "$(dirname "$0")/.."

# App-layer only (do not remove postgres, redis, minio, etc.)
CONFLICTS=(
  hub-worker
  hub-event-schema-registry
  hub-api
  hub-prefect-server
  hub-semantic
  hub-traefik
  hub-api-gateway
  hub-frontend
  hub-webhook
  hub-search
  hub-workflow-registry
  hub-workflow-engine
  hub-event-bus-health
  hub-prefect-worker
  hub-prefect-worker-docker
  hub-prefect-integration
  hub-redis-exporter-cache
  hub-redis-exporter-channels
  hub-redis-exporter-events
  hub-redis-exporter-queue
)

if [[ $# -gt 0 ]]; then
  CONFLICTS=("$@")
fi

echo "== Removing conflicting containers (if present)..."
for c in "${CONFLICTS[@]}"; do
  docker rm -f "$c" 2>/dev/null || true
done

echo "== Starting stack..."
docker compose up -d
echo "== Done. Check: docker compose ps -a"
