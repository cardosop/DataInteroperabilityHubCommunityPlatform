#!/usr/bin/env bash
# Run frontend UX E2E tests (asset-dataset flow, dataset edit, files upload).
# Reference: tasks.md 29.66.15.4
#
# Prerequisites: backend (docker compose), frontend dev server (npm run dev).
# Usage: ./scripts/run_frontend_ux_tests.sh
# Or from frontend: npm run test:e2e -- e2e/use-cases/ux/ --project=chromium

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$REPO_ROOT/frontend"

cd "$FRONTEND_DIR"

PROJECT="${E2E_PROJECT:-chromium}"
TIMEOUT="${E2E_TIMEOUT:-120000}"

echo "=== Frontend UX E2E Tests ==="
echo "Running: e2e/use-cases/ux/ (asset-dataset-flow, dataset-edit, files-upload)"
echo "Project: $PROJECT"
echo ""

exec bash scripts/e2e-detect-api.sh \
  --project="$PROJECT" \
  --timeout="$TIMEOUT" \
  e2e/use-cases/ux/
