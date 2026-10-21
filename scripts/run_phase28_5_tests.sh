#!/usr/bin/env bash
# Run Phase 28.5: Phase 27 Social Embed Test Updates
# E2E: social.spec.ts, JOURNEY-DC-008/009, JOURNEY-DPO-009/011/012, JOURNEY-CM-001/004, admin-audit-settings-routes
# Usage: ./scripts/run_phase28_5_tests.sh
# Requires: docker compose -f docker-compose.test.yml up (api-service-test), or e2e-detect-api will start stack
# E2E_SKIP_API_RESTART=1 avoids API restart (reduces auth/rate-limit flakiness when API already stable)
set -euo pipefail
cd "$(dirname "$0")/.."
[[ -f .env.test ]] && set -a && source .env.test && set +a

echo "===== Phase 28.5: Social Embed E2E (Phase 27) ====="
cd frontend
E2E_SKIP_API_RESTART="${E2E_SKIP_API_RESTART:-1}" bash scripts/e2e-detect-api.sh \
  e2e/features/social.spec.ts \
  e2e/journeys/dc/JOURNEY-DC-008.spec.ts \
  e2e/journeys/dc/JOURNEY-DC-009.spec.ts \
  e2e/journeys/dpo/JOURNEY-DPO-009.spec.ts \
  e2e/journeys/dpo/JOURNEY-DPO-011.spec.ts \
  e2e/journeys/dpo/JOURNEY-DPO-012.spec.ts \
  e2e/journeys/cm/JOURNEY-CM-001.spec.ts \
  e2e/journeys/cm/JOURNEY-CM-004.spec.ts \
  e2e/journeys/admin-audit-settings/admin-audit-settings-routes.spec.ts \
  e2e/phase7-social-ai-developer-baas-ml.spec.ts \
  --project=chromium \
  --workers=1 \
  --timeout=180000

echo "✅ Phase 28.5 tests complete"
