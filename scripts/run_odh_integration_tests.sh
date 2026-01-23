#!/bin/bash
# Script to run ODH Integration Comprehensive Validation Tests
# These tests use TransactionTestCase which can take 10-15 minutes for first run

set -e

echo "=========================================="
echo "ODH Integration Comprehensive Validation Tests"
echo "=========================================="
echo ""
echo "Note: TransactionTestCase tests can take 10-15 minutes for first run"
echo "      Subsequent runs are faster (2-5 minutes) with --keepdb"
echo ""

cd /home/ph/Desktop/DataInteroperabilityHub

# Run tests with proper timeout and output
docker compose exec -T api-service bash -c "cd /app && python hub/manage.py test hub.apps.ml.tests.test_odh_integration_comprehensive_validation --verbosity=2 --keepdb --no-input" 2>&1 | tee /tmp/odh_integration_test_results.log

echo ""
echo "=========================================="
echo "Test execution complete. Results saved to /tmp/odh_integration_test_results.log"
echo "=========================================="
