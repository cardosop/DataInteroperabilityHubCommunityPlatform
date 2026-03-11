#!/usr/bin/env bash
# Run Meshant design-system unit tests + E2E (Phase 29.0.7)
# No mocks/stubs; real API and real rendered UI.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$FRONTEND_DIR"

echo "=== Meshant Design System Tests (Phase 29.0) ==="

echo ""
echo "1. Unit tests (design-system + brand constants)..."
npm run test:run -- src/shared/design-system/ src/shared/constants/ || {
  echo "❌ Unit tests failed"
  exit 1
}

echo ""
echo "2. E2E design-system (meshant-brand, meshant-layout, meshant-typography)..."
npm run test:e2e -- e2e/design-system/ --project=chromium || {
  echo "❌ E2E design-system tests failed"
  exit 1
}

echo ""
echo "✅ All Meshant design-system tests passed"
