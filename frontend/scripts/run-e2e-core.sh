#!/usr/bin/env bash
# Phase 313.4 — run the core-only Playwright subset (frontend/e2e/core-only.txt)
# against a HUB_CORE_ONLY=1 backend on the core test stack (api on 8001).
#
# Mirrors the public repo's frontend-core.yml e2e job and is used by the
# private CI e2e-core job. No mocks/stubs — the backend MUST be running in
# core mode (docker-compose.test.core.yml sets HUB_CORE_ONLY=1 on the
# serving gunicorn since 313.DoD.4 round 4).
#
# Two phases because Playwright forbids collecting a persona aggregator
# alongside the journey specs it imports ("should not import test file"):
#   1. feature areas + cross-cutting entries → --grep against the chromium
#      project (personas are testIgnore'd there by design);
#   2. persona entries → explicit persona aggregator FILE paths on the
#      chromium-core project (their documented individual-run mode; the
#      imported journeys register once and run).

set -euo pipefail

# ── OpenAPI drift snapshot (Phase 2.5) ────────────────────────────────────
# The core subset includes the OpenAPI-drift dimension test, which compares
# the live core-mode schema hash against
# e2e/dimensions/__snapshots__/openapi-drift.core.snapshot.json. When an
# API-shape change to the CORE schema is deliberate, regenerate the snapshot
# (never hand-edit the hash):
#
#   E2E_CORE_ONLY=1 UPDATE_OPENAPI_SNAPSHOT=1 \
#     npx playwright test e2e/dimensions/openapi-drift.spec.ts --project=chromium-core
#
# then commit the new snapshot — its diff is the structured changelog of
# the API-shape change (the full-mode snapshot regenerates the same way
# without E2E_CORE_ONLY).

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$FRONTEND_DIR"

SUBSET_FILE="e2e/core-only.txt"
if [ ! -f "$SUBSET_FILE" ]; then
    echo "❌ $SUBSET_FILE missing — the core subset list is tracked; restore it." >&2
    exit 1
fi

# The core backend must be the SERVING test stack (gunicorn with
# HUB_CORE_ONLY=1), not merely a pytest process with the flag.
if ! curl -sf --connect-timeout 5 http://localhost:8001/health/ > /dev/null 2>&1; then
    echo "❌ Core backend not reachable at http://localhost:8001" >&2
    echo "   Boot it with: docker compose -f docker-compose.test.yml \\" >&2
    echo "     -f docker-compose.test.core.yml up -d --build --wait" >&2
    exit 1
fi

# Idempotent manage-command seeding (|| true by design: paid-layer commands
# are absent in core mode, and the core ones are best-effort for the subset).
COMPOSE_ARGS=(-f "$REPO_ROOT/docker-compose.test.yml" -f "$REPO_ROOT/docker-compose.test.core.yml")
[ -f "$REPO_ROOT/.env.test" ] && COMPOSE_ARGS+=(--env-file "$REPO_ROOT/.env.test")
docker compose "${COMPOSE_ARGS[@]}" exec -T api-service-test \
    python hub/manage.py ensure_e2e_user_roles 2>/dev/null || true
docker compose "${COMPOSE_ARGS[@]}" exec -T api-service-test \
    python hub/manage.py ensure_e2e_subscription 2>/dev/null || true

# Env wiring — same as e2e-detect-api.sh's test-stack branch (8001) plus the
# core flag that (a) selects the chromium-core Playwright project and
# (b) makes the OpenAPI drift spec resolve the core snapshot.
export E2E_CORE_ONLY=1
export VITE_API_BASE_URL=/api/v1
export VITE_PROXY_TARGET=http://localhost:8001
export E2E_API_BASE_URL=http://localhost:8001/api/v1
export E2E_WEB_PORT="${E2E_WEB_PORT:-5184}"

# Classify subset entries: persona lines ("Persona RBAC: X") map to their
# aggregator files; every other non-comment line joins the area grep.
PERSONA_FILES=()
AREA_ENTRIES=()
while IFS= read -r line; do
    case "$line" in
        ""|\#*) continue ;;
        "Persona RBAC: "*)
            name="${line#Persona RBAC: }"
            PERSONA_FILES+=("e2e/personas/$(printf '%s' "$name" | tr 'A-Z ' 'a-z-').spec.ts")
            ;;
        *) AREA_ENTRIES+=("$line") ;;
    esac
done < "$SUBSET_FILE"

# The setup-auth title is pinned so the storageState is written for the
# storageState-consuming projects (chromium / chromium-core dependency).
AREA_PATTERN="($(printf '%s|' "${AREA_ENTRIES[@]}" | sed 's/|$//'))|save authenticated session"

# Zero-match guard: every entry must select at least one spec — a dead
# entry silently shrinks the subset. ONE --list pass, then substring
# checks in the shell (no per-entry playwright startups). --list does
# not need a backend.
LIST_OUT="$(npx playwright test --project=chromium --list --grep "$AREA_PATTERN" 2>/dev/null)" || true
for entry in "${AREA_ENTRIES[@]}"; do
    if ! grep -qF "$entry" <<< "$LIST_OUT"; then
        echo "❌ core-only.txt entry matches zero specs: $entry" >&2
        echo "   Validate with: npx playwright test --project=chromium --list --grep '$entry'" >&2
        exit 1
    fi
done
for f in "${PERSONA_FILES[@]}"; do
    [ -f "$f" ] || { echo "❌ persona aggregator missing: $f" >&2; exit 1; }
done

# Both phases MUST run (a phase-1 failure must never hide persona
# coverage); the exit code aggregates.
rc=0

echo "Phase 1/2 — core feature areas + cross-cutting (chromium project, --grep)"
npx playwright test --project=chromium --grep "$AREA_PATTERN" "$@" || rc=1

echo "Phase 2/2 — core personas (chromium-core project, explicit aggregators)"
npx playwright test --project=chromium-core "${PERSONA_FILES[@]}" "$@" || rc=1

exit $rc
