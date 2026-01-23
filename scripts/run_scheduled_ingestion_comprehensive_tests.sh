#!/bin/bash
# Script to run scheduled ingestion comprehensive validation tests

set -e

echo "Running Scheduled Ingestion Comprehensive Validation Tests..."
echo "============================================================"

# Run tests in docker container
docker compose exec -T api-service python manage.py test \
    hub.apps.scheduled_ingestion.tests.test_scheduled_ingestion_comprehensive_validation \
    --verbosity=2 \
    --keepdb \
    2>&1 | tee /tmp/scheduled_ingestion_tests.log

echo ""
echo "Test execution completed. Check /tmp/scheduled_ingestion_tests.log for full output."
