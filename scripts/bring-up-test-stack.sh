#!/usr/bin/env bash
# Bring up the full test stack and ensure all services start.
# Use when: docker compose up -d leaves some services in "Created" (not started).
#
# Root cause: Complex depends_on chains; parallel startup can leave api-service-test
# and its dependents in Created until dependencies are healthy. A second up -d
# or explicit start of those services fixes it.
#
# Usage: ./scripts/bring-up-test-stack.sh
# From repo root. Uses docker-compose.test.yml and .env.test if present.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.test.yml}"
ENV_ARGS=""
[[ -f .env.test ]] && ENV_ARGS="--env-file .env.test"
COMPOSE_CMD="docker compose -f $COMPOSE_FILE $ENV_ARGS"

echo "== Bringing up test stack (COMPOSE_FILE=$COMPOSE_FILE) =="
echo ""

# Step 1: Initial up -d
echo "Step 1: docker compose up -d --wait (wait for infra to be healthy)..."
$COMPOSE_CMD up -d --wait 2>&1 || true

# Step 2: Check for Created containers (created but not started)
CREATED=$($COMPOSE_CMD ps -a --format json 2>/dev/null | grep -c '"State":"created"' || echo "0")
if [[ "$CREATED" -gt 0 ]]; then
  echo ""
  echo "Step 2: Found $CREATED container(s) in Created state. Starting them..."
  # Start api-service-test first (many depend on it)
  $COMPOSE_CMD up -d api-service-test 2>&1 || true
  sleep 5
  # Start the rest
  $COMPOSE_CMD up -d worker-service-test api-gateway-test prometheus-test grafana-test alertmanager-test prefect-worker-test frontend-test 2>&1 || true
  sleep 10
  # Observability depends on prometheus healthy
  $COMPOSE_CMD up -d observability-service-test 2>&1 || true
  echo ""
else
  echo "Step 2: No Created containers; all started."
fi

# Step 3: Final status
echo ""
echo "== Final status =="
$COMPOSE_CMD ps -a 2>/dev/null | head -60

echo ""
echo "If any service is still Created or unhealthy:"
echo "  1. Check logs: docker compose -f $COMPOSE_FILE logs <service-name>"
echo "  2. Re-run: ./scripts/bring-up-test-stack.sh"
echo "  3. Or clean: ./scripts/clean-test-stack.sh && ./scripts/bring-up-test-stack.sh"
echo ""
