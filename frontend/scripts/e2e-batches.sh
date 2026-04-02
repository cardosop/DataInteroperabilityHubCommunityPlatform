#!/usr/bin/env bash
# Frontend E2E batch runner. Run subsets for iterate-and-fix cycles.
# Usage: npm run test:e2e:batch1 | test:e2e:batch2 | ... | test:e2e:batch8
# Or: bash scripts/e2e-batches.sh [1|2|3|4|5|6|7|8]
# Prerequisites: backend (docker compose), frontend dev server (npm run dev).
#
# By default runs chromium project only (each test runs once).
# Set E2E_VISIBLE=1 to add the headed+slowMo visible project for interactive debugging.
#
# Intentionally excluded from all batches (testIgnored in playwright.config.ts):
#   e2e/dimensions/  — network-failure/rate-limit tests; flaky by design; run manually
#   e2e/personas/    — very long-running full persona suites; run manually

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$FRONTEND_DIR"

# Default to chromium project only (each test runs once). Set E2E_ALL_PROJECTS=1 to run all 3.
# e2e-detect-api.sh adds --project=chromium automatically when no --project flag is passed.
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
  echo "Detecting backend and starting tests..."
  exec bash scripts/e2e-detect-api.sh "${PROJECT_ARGS[@]}" --timeout="$TIMEOUT" "$@"
}

case "${1:-}" in
  1)
    # Auth, setup, cross-cutting, design system, tenant onboarding
    # Reduce workers to 2: every test in this batch requires a full login cycle.
    # 4 workers saturate the backend login/capabilities endpoints causing PostgreSQL
    # statement timeouts (500) and rate-limit cascades (429) that fail 15+ tests.
    # Note: alternate-flows-failure.spec.ts is already included via cross-cutting/ glob.
    # Enable authenticated a11y scans (axe on 10 routes) — batch 1 includes e2e/a11y/.
    export E2E_A11Y=1
    run_batch 1 "auth, setup, cross-cutting, design-system, tenant" \
      --workers=2 \
      e2e/auth-visitor-journeys.spec.ts \
      e2e/login-app-shell.spec.ts \
      e2e/features/auth.spec.ts \
      e2e/cross-cutting/ \
      e2e/setup/ \
      e2e/a11y/ \
      e2e/design-system/ \
      e2e/use-cases/auth/ \
      e2e/journeys/tenant/ \
      e2e/security/
    ;;
  2)
    # Route-level smoke tests for all major feature areas
    run_batch 2 "routes (contracts, marketplace, dq, mesh, integrations, admin)" \
      e2e/journeys/core-data-routes/ \
      e2e/journeys/contracts-odps/ \
      e2e/journeys/marketplace-dc/ \
      e2e/journeys/dq-compliance-governance/ \
      e2e/journeys/mesh-virtualization-search-ai/ \
      e2e/journeys/integrations-jobs-webhooks/ \
      e2e/journeys/admin-audit-settings/
    ;;
  3)
    # DPO journeys + asset/contract/ODPS use cases (all Data Product Owner flows)
    # Reduce workers to 2: eases backend load (ECONNRESET/auth flakiness under 4 workers)
    run_batch 3 "DPO journeys + asset/contract/ODPS use cases" \
      --workers=2 \
      e2e/journeys/dpo/ \
      e2e/use-cases/assets/ \
      e2e/use-cases/contracts/ \
      e2e/use-cases/odps/
    ;;
  4)
    # Auth journeys + Data Consumer + Data Engineer + integrations use cases
    # Reduce workers to 2: eases backend load (consumer login connection errors under 4 workers)
    run_batch 4 "auth, DC, DE journeys + integrations use cases" \
      --workers=2 \
      e2e/journeys/auth/ \
      e2e/journeys/dc/ \
      e2e/journeys/de/ \
      e2e/use-cases/integrations/
    ;;
  5)
    # TA, PA, Dev, Aud journeys + cross-persona value-chain and isolation tests + webhook use cases
    # Reduce workers to 2: PA/TA admin ops + cross-persona isolation tests are RAM-heavy (12 Chrome
    # instances at 4 workers cause OOM kills between test 150-200 on a 61GiB host with Fuseki+API load)
    run_batch 5 "TA, PA, Dev, Aud, cross-persona journeys + webhook use cases" \
      --workers=2 \
      e2e/journeys/ta/ \
      e2e/journeys/pa/ \
      e2e/journeys/dev/ \
      e2e/journeys/aud/ \
      e2e/journeys/cross-persona/ \
      e2e/use-cases/webhooks/
    ;;
  6)
    # CPO, DS, DMO, DA, CM, Marketplace journeys + compliance/DQ/marketplace use cases
    # Reduce workers to 2: ~390 tests × 3 projects; same OOM risk as batch5 at 4 workers
    run_batch 6 "CPO, DS, DMO, DA, CM, Marketplace journeys + compliance/DQ/marketplace use cases" \
      --workers=2 \
      e2e/journeys/cpo/ \
      e2e/journeys/ds/ \
      e2e/journeys/dmo/ \
      e2e/journeys/da/ \
      e2e/journeys/cm/ \
      e2e/journeys/marketplace/ \
      e2e/use-cases/compliance/ \
      e2e/use-cases/dq/ \
      e2e/use-cases/marketplace/
    ;;
  7)
    # Feature smoke tests + phase7.5/phase8 + governance + scheduled journeys.
    # phase2–phase7 removed: superseded by journey specs in batches 3–6.
    # They remain on disk (run manually via batch 9) until deletion sign-off.
    # Reduce workers to 2: ~220 tests × 3 projects; same OOM risk as batch5 at 4 workers
    run_batch 7 "features, phase7.5, phase8, governance, scheduled" \
      --workers=2 \
      e2e/features/ \
      e2e/phase7.5-features-gap-closure.spec.ts \
      e2e/phase8-hardening.spec.ts \
      e2e/journeys/governance-retention/ \
      e2e/journeys/scheduled-export/ \
      e2e/journeys/scheduled-ingestion/
    ;;
  9)
    # Deprecated phase specs (manual regression only — not in CI).
    # These are superseded by journey specs in batches 3–6. Run before deleting.
    run_batch 9 "deprecated phase specs (manual regression)" \
      e2e/phase2-catalog-journey.spec.ts \
      e2e/phase3-quality-gates.spec.ts \
      e2e/phase4-marketplace-journey.spec.ts \
      e2e/phase5-odps-journey.spec.ts \
      e2e/phase6-mesh-virtualization.spec.ts \
      e2e/phase7-social-ai-developer-baas-ml.spec.ts
    ;;
  8)
    # UX flows: resource pickers, asset-dataset flows, files upload, dataset edit, ODPS link
    run_batch 8 "UX flows (pickers, asset-dataset, files-upload, dataset-edit, ODPS link)" \
      e2e/use-cases/ux/
    ;;
  list)
    echo "E2E Batches (run with: npm run test:e2e:batchN or bash scripts/e2e-batches.sh N)"
    echo "  1: auth, setup, cross-cutting, design-system, tenant, security (~100 tests, workers=2)"
    echo "  2: routes - contracts, marketplace, dq, mesh, integrations, admin (~115 tests)"
    echo "  3: DPO journeys + asset/contract/ODPS use cases (~275 tests)"
    echo "  4: auth, DC, DE journeys + integrations use cases (~385 tests)"
    echo "  5: TA, PA, Dev, Aud, cross-persona journeys + webhook use cases (~375 tests)"
    echo "  6: CPO, DS, DMO, DA, CM, Marketplace journeys + compliance/DQ/marketplace use cases (~390 tests)"
    echo "  7: features, phase7.5, phase8, governance, scheduled (~220 tests)"
    echo "  8: UX - pickers, asset-dataset flow, dataset edit, files upload, ODPS link (~25 tests)"
    echo "  9: deprecated phase specs — manual regression only, not in CI (~210 tests)"
    echo ""
    echo "Intentionally excluded (testIgnored in playwright.config.ts — run manually):"
    echo "  e2e/dimensions/  — network-failure/rate-limit/timeout/concurrent tests (flaky by design)"
    echo "  e2e/personas/    — full persona journey suites (very long-running)"
    echo ""
    echo "Total: ~1885 tests across 8 CI batches (batch 9 is manual-only)"
    echo ""
    echo "Faster iteration: E2E_PROJECT=chromium npm run test:e2e:batch1  (runs ~34 tests)"
    echo "Skip API restart (avoids socket hang up): E2E_SKIP_API_RESTART=1 npm run test:e2e:batch3"
    ;;
  *)
    echo "Usage: $0 <1|2|3|4|5|6|7|8|9|list>"
    echo "  Run batch N for iterate-and-fix cycles. Use 'list' to see batch definitions."
    echo "  Batch 9 = deprecated phase specs (manual regression only, not in CI)."
    exit 1
    ;;
esac
