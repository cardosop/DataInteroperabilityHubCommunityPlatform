#!/bin/bash
# Script to run Phase 27.2 tests in batches with optimized database setup

set -e

cd "$(dirname "$0")/.."

echo "=== Phase 27.2 Test Execution ==="
echo "Date: $(date)"
echo ""

# First, ensure test database is migrated (one time setup)
echo "Step 1: Ensuring test database is migrated..."
docker compose exec -T api-service bash -c "cd /app/hub && python manage.py migrate --run-syncdb --no-input" > /dev/null 2>&1 || true

# Now run tests with SKIP_TEST_MIGRATIONS to speed up
export SKIP_TEST_MIGRATIONS=1

# Integration Tests
echo ""
echo "=== Integration Tests ==="
echo "1. Billing APIs Comprehensive..."
docker compose exec -T api-service bash -c "cd /app/hub && SKIP_TEST_MIGRATIONS=1 python manage.py test tests.integration.test_billing_apis_comprehensive --verbosity=1 --keepdb 2>&1" | tee /tmp/billing_tests.log | tail -3

echo ""
echo "2. Tenant Onboarding Service..."
docker compose exec -T api-service bash -c "cd /app/hub && SKIP_TEST_MIGRATIONS=1 python manage.py test tests.integration.test_tenant_onboarding_service_comprehensive_validation --verbosity=1 --keepdb 2>&1" | tee /tmp/onboarding_tests.log | tail -3

echo ""
echo "3. Erasure Workflow Integration..."
docker compose exec -T api-service bash -c "cd /app/hub && SKIP_TEST_MIGRATIONS=1 python manage.py test tests.integration.test_erasure_workflow_integration --verbosity=1 --keepdb 2>&1" | tee /tmp/erasure_tests.log | tail -3

echo ""
echo "4. Scheduled Export APIs Comprehensive..."
docker compose exec -T api-service bash -c "cd /app/hub && SKIP_TEST_MIGRATIONS=1 python manage.py test tests.integration.test_scheduled_export_apis_comprehensive --verbosity=1 --keepdb 2>&1" | tee /tmp/scheduled_export_tests.log | tail -3

# E2E Tests
echo ""
echo "=== E2E Tests ==="
echo "5. Phase 25 Billing E2E..."
docker compose exec -T api-service bash -c "cd /app/hub && SKIP_TEST_MIGRATIONS=1 python manage.py test tests.e2e.test_phase25_billing_e2e --verbosity=1 --keepdb 2>&1" | tee /tmp/billing_e2e_tests.log | tail -3

echo ""
echo "6. Phase 25 Tenant Onboarding E2E..."
docker compose exec -T api-service bash -c "cd /app/hub && SKIP_TEST_MIGRATIONS=1 python manage.py test tests.e2e.test_phase25_tenant_onboarding_e2e --verbosity=1 --keepdb 2>&1" | tee /tmp/onboarding_e2e_tests.log | tail -3

echo ""
echo "7. Phase 25 GDPR Erasure E2E..."
docker compose exec -T api-service bash -c "cd /app/hub && SKIP_TEST_MIGRATIONS=1 python manage.py test tests.e2e.test_phase25_gdpr_erasure_e2e --verbosity=1 --keepdb 2>&1" | tee /tmp/erasure_e2e_tests.log | tail -3

# Regression Tests
echo ""
echo "=== Regression Tests ==="
echo "8. Phase 25 Regression..."
docker compose exec -T api-service bash -c "cd /app/hub && SKIP_TEST_MIGRATIONS=1 python manage.py test tests.regression.test_phase25_regression --verbosity=1 --keepdb 2>&1" | tee /tmp/regression_tests.log | tail -3

echo ""
echo "9. Phase 26 CLI/SDK Regression..."
docker compose exec -T api-service bash -c "cd /app/hub && SKIP_TEST_MIGRATIONS=1 python manage.py test tests.regression.test_phase26_cli_sdk_regression --verbosity=1 --keepdb 2>&1" | tee /tmp/cli_sdk_regression_tests.log | tail -3

# Security Tests
echo ""
echo "=== Security Tests ==="
echo "10. Phase 25 Security..."
docker compose exec -T api-service bash -c "cd /app/hub && SKIP_TEST_MIGRATIONS=1 python manage.py test tests.security.test_phase25_security --verbosity=1 --keepdb 2>&1" | tee /tmp/security_tests.log | tail -3

# Performance Tests
echo ""
echo "=== Performance Tests ==="
echo "11. Scheduled Export Performance..."
docker compose exec -T api-service bash -c "cd /app/hub && SKIP_TEST_MIGRATIONS=1 python manage.py test tests.performance.test_scheduled_export_performance --verbosity=1 --keepdb 2>&1" | tee /tmp/performance_tests.log | tail -3

echo ""
echo "=== Test Execution Complete ==="
echo "Check log files in /tmp/ for detailed results"
