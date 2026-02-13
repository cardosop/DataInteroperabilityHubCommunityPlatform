#!/usr/bin/env bash
# Run Phase 5 scheduled ingestion tests (process-file integrations, audit, metrics).
# First run can take 20-45 min if test DB is created/migrated; use --reuse-db for fast reruns.
# Requires: docker compose up (api-service, postgres, redis, minio at least).
set -e
cd "$(dirname "$0")/.."
TIMEOUT="${TIMEOUT:-2700}"  # 45 min default for first run with migrations
# PYTHONDONTWRITEBYTECODE=1 so container uses latest code from volume
# First run (no test DB): use long per-test timeout for migrations; later runs with --reuse-db are fast
docker compose exec -T api-service bash -c "cd /app && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/app python -m pytest \
  hub/apps/scheduled_ingestion/tests/test_phase5_integrations.py \
  hub/apps/scheduled_ingestion/tests/test_internal_worker_api.py::InternalWorkerAPITest::test_process_file_success_emits_audit_and_returns_201 \
  -v --tb=short --reuse-db --timeout=\${PYTEST_TIMEOUT:-600}"
