#!/usr/bin/env bash
# Remove any hub-* containers (fix "container name already in use") and start the stack.
# Use when: docker compose up -d fails with Conflict / container name already in use.
#
# Usage: ./scripts/compose_start_clean.sh [--detach]
# From repo root: ./scripts/compose_start_clean.sh

set -e
cd "$(dirname "$0")/.."
DETACH="${1:-}"

echo "== Stopping stack..."
docker compose down -t 15 --remove-orphans 2>/dev/null || true

echo "== Removing all hub-* containers by name (clears conflicts)..."
while IFS= read -r name; do
  [[ -z "$name" ]] && continue
  docker rm -f "$name" 2>/dev/null || true
done < <(docker ps -a --filter "name=hub-" --format "{{.Names}}" 2>/dev/null || true)
# Explicit list so we never miss a conflict (matches docker-compose.yml container_name / service names)
for c in hub-api hub-api-gateway hub-ckan-test-db hub-ckan-test-redis hub-ckan-test-solr \
  hub-compliance hub-datacontract hub-dq hub-event-bus-health hub-event-schema-registry \
  hub-frontend hub-fuseki hub-jaeger hub-mailhog hub-minio hub-mock-server \
  hub-odh-inference-scheduler hub-odh-training-operator hub-postgres hub-prefect-db \
  hub-prefect-integration hub-prefect-server hub-prefect-worker hub-prefect-worker-docker \
  hub-redis-cache hub-redis-channels hub-redis-events hub-redis-queue \
  hub-redis-exporter-cache hub-redis-exporter-channels hub-redis-exporter-events hub-redis-exporter-queue \
  hub-search hub-semantic hub-traefik hub-webhook hub-worker hub-workflow-engine hub-workflow-registry; do
  docker rm -f "$c" 2>/dev/null || true
done

echo "== Starting stack (retrying on conflict)..."
for attempt in 1 2 3 4 5 6 7 8 9 10; do
  out=$(docker compose up -d 2>&1) || true
  if echo "$out" | grep -q "Error response from daemon: Conflict"; then
    # Remove by name (all mentioned in error)
    while read -r name; do
      [[ -z "$name" ]] && continue
      echo "== Conflict: removing $name"
      docker rm -f "$name" 2>/dev/null || true
    done < <(echo "$out" | sed -n 's/.*container name "\([^"]*\)".*/\1/p')
    # Also remove by container ID from error (e.g. "by container \"abc123...\"")
    while read -r id; do
      [[ -z "$id" ]] && continue
      echo "== Removing conflicting container id: ${id:0:12}"
      docker rm -f "$id" 2>/dev/null || true
    done < <(echo "$out" | sed -n 's/.*by container "\([a-f0-9]\{64\}\).*/\1/p')
  else
    echo "$out"
    echo "== Done. Wait 2–3 minutes for Postgres/Prefect-DB, then: docker compose ps -a"
    exit 0
  fi
done
echo "== Giving up after 10 attempts. Run: docker rm -f \$(docker ps -aq --filter 'name=hub-'); docker compose up -d"
exit 1
