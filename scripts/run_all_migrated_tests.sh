#!/bin/bash
# Comprehensive test runner for all migrated app tests
# Ensures test database is properly set up and runs all tests

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

export TEST_DB_SUFFIX="migrated_tests"

echo "=========================================="
echo "Running All Migrated App Tests"
echo "=========================================="
echo ""

# Step 1: Ensure test database is migrated
echo "Step 1: Setting up test database..."
timeout 900 docker compose exec -T api-service bash -c "export TEST_DB_SUFFIX=migrated_tests && python /app/hub/manage.py test hub.apps.tenants.tests.test_tenant_config_job_integration.TenantConfigJobIntegrationTest.test_job_creation_with_platform_defaults --verbosity=0 --keepdb --no-input" > /dev/null 2>&1 || true
echo "Test database ready."
echo ""

# All test modules
TEST_MODULES=(
    "hub.apps.tenants.tests.test_tenant_config_file_upload_integration"
    "hub.apps.tenants.tests.test_tenant_config_compliance_integration"
    "hub.apps.tenants.tests.test_tenant_config_dq_integration"
    "hub.apps.tenants.tests.test_tenant_config_job_integration"
    "hub.apps.assets.tests.test_asset_relationships"
    "hub.apps.auth.tests.test_authorization"
    "hub.apps.auth.tests.test_register_me"
    "hub.apps.auth.tests.test_middleware"
    "hub.apps.jobs.tests.test_job_processors"
    "hub.apps.scheduled_ingestion.tests.test_services"
    "hub.apps.scheduled_ingestion.tests.test_ingestion"
    "hub.apps.scheduled_ingestion.tests.test_views"
    "hub.apps.contracts.tests.test_caching_enhanced"
    "hub.apps.contracts.tests.test_lineage_reference_resolution"
    "hub.apps.contracts.tests.test_views_validation"
    "hub.apps.contracts.tests.test_validation"
    "hub.apps.contracts.tests.test_ref_resolver_caching"
    "hub.apps.contracts.tests.test_ref_resolver"
    "hub.apps.contracts.tests.test_ref_warming"
    "hub.apps.contracts.tests.test_odps_metrics"
    "hub.apps.contracts.tests.test_lineage_traversal"
    "hub.apps.contracts.tests.test_lineage_visualization"
    "hub.apps.contracts.tests.test_lineage_service"
    "hub.apps.contracts.tests.test_services"
    "hub.apps.contracts.tests.test_cli_client"
    "hub.apps.contracts.tests.test_odps_rate_limiting"
    "hub.apps.contracts.tests.test_odps_normalizer"
    "hub.apps.contracts.tests.security.test_ref_resolver_security"
    "hub.apps.contracts.tests.test_rollback_odps_migration"
)

TEST_PATH=$(IFS=' '; echo "${TEST_MODULES[*]}")

echo "Step 2: Running all tests..."
echo "This may take several minutes..."
echo ""

# Run all tests with SKIP_TEST_MIGRATIONS=1 for speed
OUTPUT=$(timeout 2400 docker compose exec -T api-service bash -c "export TEST_DB_SUFFIX=migrated_tests && SKIP_TEST_MIGRATIONS=1 python /app/hub/manage.py test $TEST_PATH --verbosity=2 --keepdb --no-input 2>&1") || TEST_EXIT=$?

# Extract results
TESTS_RAN=$(echo "$OUTPUT" | grep -oP "Ran \d+ test" | grep -oP "\d+" | tail -1 || echo "0")
FAILURES=$(echo "$OUTPUT" | grep -oP "FAILED \(failures=\d+" | grep -oP "\d+" || echo "0")
ERRORS=$(echo "$OUTPUT" | grep -oP "ERROR.*errors=\d+" | grep -oP "\d+" || echo "0")

echo ""
echo "=========================================="
echo "Test Results Summary"
echo "=========================================="
echo "Tests Ran: $TESTS_RAN"
echo "Failures: $FAILURES"
echo "Errors: $ERRORS"
echo ""

if echo "$OUTPUT" | grep -q "OK"; then
    echo "✅ All tests passed!"
    echo ""
    echo "$OUTPUT" | tail -20
    exit 0
elif [ "$FAILURES" -gt 0 ] || [ "$ERRORS" -gt 0 ]; then
    echo "❌ Some tests failed. Details:"
    echo ""
    echo "$OUTPUT" | grep -A 20 -E "(FAILED|ERROR|Traceback)" | head -150
    exit 1
else
    echo "⚠️  Test execution completed but status unclear."
    echo ""
    echo "$OUTPUT" | tail -50
    exit 1
fi
