#!/usr/bin/env bash
# Frontend E2E batch runner. Run subsets for iterate-and-fix cycles.
# Usage: npm run test:e2e:batch1 | test:e2e:batch2 | ... | test:e2e:batch7
# Or: bash scripts/e2e-batches.sh [1|2|3|4|5|6|7]
# Prerequisites: backend (docker compose), frontend dev server (npm run dev).
#
# By default runs ALL projects (chromium, visible, chromium-routes) to match full run (1924 tests).
# Same ~642 unique tests run 3x across projects. Set E2E_PROJECT=chromium for faster runs (642 tests).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$FRONTEND_DIR"

# Run all projects by default (matches npm run test:e2e → 1924 tests). Use E2E_PROJECT=chromium for 642.
PROJECT_ARGS=()
if [[ -n "${E2E_PROJECT:-}" ]]; then
  PROJECT_ARGS=(--project="$E2E_PROJECT")
fi
TIMEOUT="${E2E_TIMEOUT:-120000}"

run_batch() {
  local batch_num="$1"
  local description="$2"
  shift 2
  echo "=== E2E Batch $batch_num ($description) ==="
  exec bash scripts/e2e-detect-api.sh "${PROJECT_ARGS[@]}" --timeout="$TIMEOUT" "$@"
}

case "${1:-}" in
  1)
    run_batch 1 "auth, setup, cross-cutting" \
      e2e/auth-visitor-journeys.spec.ts \
      e2e/login-app-shell.spec.ts \
      e2e/features/auth.spec.ts \
      e2e/cross-cutting/ \
      e2e/setup/ \
      e2e/a11y/
    ;;
  2)
    run_batch 2 "routes" \
      e2e/journeys/contracts-odps/ \
      e2e/journeys/marketplace-dc/ \
      e2e/journeys/dq-compliance-governance/ \
      e2e/journeys/mesh-virtualization-search-ai/ \
      e2e/journeys/integrations-jobs-webhooks/ \
      e2e/journeys/admin-audit-settings/ \
      e2e/cross-cutting/alternate-flows-failure.spec.ts
    ;;
  3)
    run_batch 3 "DPO journeys" \
      e2e/journeys/dpo/
    ;;
  4)
    run_batch 4 "auth, DC, DE journeys" \
      e2e/journeys/auth/ \
      e2e/journeys/dc/ \
      e2e/journeys/de/
    ;;
  5)
    run_batch 5 "TA, PA, Dev, Aud journeys" \
      e2e/journeys/ta/ \
      e2e/journeys/pa/ \
      e2e/journeys/dev/ \
      e2e/journeys/aud/
    ;;
  6)
    run_batch 6 "CPO, DS, DMO, DA, CM, Marketplace journeys" \
      e2e/journeys/cpo/ \
      e2e/journeys/ds/ \
      e2e/journeys/dmo/ \
      e2e/journeys/da/ \
      e2e/journeys/cm/ \
      e2e/journeys/marketplace/
    ;;
  7)
    run_batch 7 "features, phase, governance, scheduled" \
      e2e/features/ \
      e2e/phase2-catalog-journey.spec.ts \
      e2e/phase6-mesh-virtualization.spec.ts \
      e2e/phase7.5-features-gap-closure.spec.ts \
      e2e/phase7-social-ai-developer-baas-ml.spec.ts \
      e2e/phase8-hardening.spec.ts \
      e2e/journeys/governance-retention/ \
      e2e/journeys/scheduled-export/ \
      e2e/journeys/scheduled-ingestion/
    ;;
  list)
    echo "E2E Batches (run with: npm run test:e2e:batchN or bash scripts/e2e-batches.sh N)"
    echo "  1: auth, setup, cross-cutting (79 tests)"
    echo "  2: routes - contracts, marketplace, dq, mesh, integrations, admin (121 tests)"
    echo "  3: DPO journeys (253 tests)"
    echo "  4: auth, DC, DE journeys (376 tests)"
    echo "  5: TA, PA, Dev, Aud journeys (352 tests)"
    echo "  6: CPO, DS, DMO, DA, CM, Marketplace journeys (364 tests)"
    echo "  7: features, phase specs, governance, scheduled (400 tests)"
    echo ""
    echo "Total: ~1945 tests in 7 batches (same as npm run test:e2e)"
    echo ""
    echo "Faster iteration: E2E_PROJECT=chromium npm run test:e2e:batch1  (runs ~27 tests)"
    ;;
  *)
    echo "Usage: $0 <1|2|3|4|5|6|7|list>"
    echo "  Run batch N for iterate-and-fix cycles. Use 'list' to see batch definitions."
    exit 1
    ;;
esac
