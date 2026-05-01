#!/usr/bin/env bash
#
# Phase 228.F2.36 — Regenerate the OpenAPI snapshot.
#
# Wraps the existing `openapi-drift.spec.ts` workflow so the
# regen process is one command:
#
#     bash scripts/regenerate_openapi_snapshot.sh [staging|local]
#
# Behaviour:
#   - Default target is `staging` — the canonical path used by the
#     L9.4 closeout convention (regen against the deployed backend
#     to capture all routes drf-spectacular auto-discovered post-deploy).
#   - `local` target runs the spec against http://localhost:8000.
#
# Side effect: `frontend/e2e/dimensions/__snapshots__/openapi-drift.snapshot.json`
# is rewritten.  Commit the diff in a follow-up PR per the L9.4 pattern.
#
# Why a wrapper script: the regen is a multi-step ritual (env vars,
# proxy targets, project flag) easy to misremember.  This script
# encodes the canonical invocation so a future maintainer doesn't
# have to re-derive it from comments scattered across PR history.

set -euo pipefail

TARGET="${1:-staging}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

case "$TARGET" in
  staging)
    BASE_URL="${OPENAPI_REGEN_STAGING_URL:-https://api.stagingmeshant-internal.example.com}"
    ;;
  local)
    BASE_URL="${OPENAPI_REGEN_LOCAL_URL:-http://localhost:8000}"
    ;;
  *)
    echo "usage: $0 [staging|local]" >&2
    exit 1
    ;;
esac

echo "[openapi-regen] target=$TARGET base_url=$BASE_URL"

cd "$REPO_ROOT/frontend"

# Run the openapi-drift spec with the regen flag.  Playwright takes
# its base URL from PLAYWRIGHT_BASE_URL — but the spec itself reads
# the API URL from a separate env var (E2E_API_BASE_URL) so we set
# both to keep the spec's auth + probe paths lined up.
PLAYWRIGHT_BASE_URL="$BASE_URL" \
E2E_API_BASE_URL="$BASE_URL/api/v1" \
UPDATE_OPENAPI_SNAPSHOT=1 \
  npx playwright test e2e/dimensions/openapi-drift.spec.ts \
    --project=dimensions \
    --reporter=list

echo ""
echo "[openapi-regen] OK — review the diff:"
echo "  git diff frontend/e2e/dimensions/__snapshots__/openapi-drift.snapshot.json"
echo ""
echo "[openapi-regen] Phase 228.F2.36 reviewer checklist:"
echo "  - new path /api/v1/contracts/{id}/lineage/ with PATCH operation"
echo "  - new operation_id 'contract_lineage_edit'"
echo "  - response codes 200 / 400 / 403 / 404 / 412 / 413"
echo "  - existing F1 path /api/v1/marketplace/listings/{id}/lineage/"
echo "    with operation_id 'listing_lineage' still present"
