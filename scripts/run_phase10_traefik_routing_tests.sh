#!/usr/bin/env bash
# Run Phase 10 Traefik routing integration tests.
# Services must be running in Docker Compose; tests run inside api-service and hit Traefik via https://traefik:443.
# Usage: ./scripts/run_phase10_traefik_routing_tests.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Services required for Phase 10 tests (dependencies started automatically)
SERVICES=(traefik frontend api-gateway api-service)

echo "[INFO] Checking Docker Compose..."
docker compose version

echo "[INFO] Ensuring required services are up: ${SERVICES[*]} (and their dependencies)"
docker compose up -d "${SERVICES[@]}"

echo "[INFO] Waiting for Traefik, frontend, api-gateway, api-service to be healthy..."
for svc in api-service api-gateway frontend traefik; do
  timeout 300 bash -c "until docker compose ps --format json $svc 2>/dev/null | grep -q '\"Health\":\"healthy\"'; do echo \"  waiting for $svc...\"; sleep 5; done" || {
    echo "[WARN] $svc may not be healthy yet; continuing."
  }
done

echo "[INFO] Running Phase 10 Traefik routing tests inside api-service..."
docker compose exec -T -e PYTEST_DOCKER_COMPOSE_RUNTIME=1 -e TRAEFIK_BASE_URL=https://traefik:443 api-service bash -c \
  "cd /app && python -m pytest tests/integration/test_traefik_routing.py -v --tb=short -m 'integration and docker_compose_runtime'"

echo "[INFO] Phase 10 Traefik routing tests finished."
