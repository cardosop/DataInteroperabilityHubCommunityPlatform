#!/usr/bin/env bash
# Start the test stack after stopping the main dev stack.
# Use when: port conflicts or OOM (exit 137) because both stacks run together.
#
# Usage: ./scripts/start-test-stack-alone.sh
# From repo root.
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

ENV_ARGS=""
[[ -f .env.test ]] && ENV_ARGS="--env-file .env.test"

echo "== Stopping main dev stack (frees ports and memory)..."
docker compose down -t 30 2>/dev/null || true

echo ""
echo "== Starting test stack..."
docker compose -f docker-compose.test.yml $ENV_ARGS up -d

echo ""
echo "Wait ~2–3 min for all services to become healthy, then:"
echo "  curl -s http://localhost:8001/health/"
echo "  ./scripts/verify_test_stack.sh"
echo ""
echo "To switch back to dev stack: docker compose up -d"
echo ""
