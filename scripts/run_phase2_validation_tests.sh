#!/usr/bin/env bash
# Run Phase 2 validation tests (tasks.md 45-75) inside api-service.
# Requires: docker compose with api-service and postgres running.
#
# Phase 2.4 (Job record): internal job creation, create_job executed_by_prefect, RQ no-op.
# Run with: ./scripts/run_phase2_validation_tests.sh
#
# Full internal worker API (9 tests): single TransactionTestCase, allow ~20 min:
#   docker compose exec api-service bash -c "cd /app && TESTING=1 python -m pytest hub/apps/scheduled_ingestion/tests/test_internal_worker_api.py -v --tb=short --reuse-db"
#
# Phase 2.5 Prefect full-flow integration test (requires prefect in api-service):
#   docker compose build api-service   # ensure requirements.txt (prefect) is installed
#   docker compose exec api-service bash -c "cd /app && TESTING=1 python -m pytest hub/apps/scheduled_ingestion/tests/test_prefect_full_flow_integration.py -v -m integration"

set -e
cd "$(dirname "$0")/.."
COMPOSE="${COMPOSE:-docker compose}"

# One of the three tests uses TransactionTestCase; allow 5–10 min total.
echo "Phase 2 validation tests (executed_by_prefect, internal job API, RQ no-op)..."
$COMPOSE exec -T api-service bash -c "cd /app && TESTING=1 python -m pytest \
  hub/apps/jobs/tests/test_job_creation_processing.py::JobCreationProcessingTest::test_create_job_executed_by_prefect_not_enqueued \
  hub/apps/jobs/tests/test_scheduled_ingestion_job.py::ScheduledIngestionJobTest::test_process_job_executed_by_prefect_no_op \
  hub/apps/scheduled_ingestion/tests/test_internal_worker_api.py::InternalWorkerAPITest::test_internal_create_job_creates_prefect_executed_job \
  -v --tb=short --reuse-db"
