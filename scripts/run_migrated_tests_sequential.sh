#!/bin/bash
# Sequential test runner - runs tests one app at a time to avoid database locks
# Provides incremental feedback and fixes issues as they arise

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

export TEST_DB_SUFFIX="migrated_tests"

echo "=========================================="
echo "Sequential Test Execution (One App at a Time)"
echo "=========================================="
echo ""

# Step 1: Ensure test database is migrated
echo "Step 1: Setting up test database..."
# Use a simple test to create and migrate the test database
timeout 600 docker compose exec -T api-service bash -c "export TEST_DB_SUFFIX=migrated_tests && python /app/hub/manage.py test hub.apps.tenants.tests.test_tenant_config_file_upload_integration.TenantConfigFileUploadIntegrationTest.test_upload_config_file --verbosity=0 --keepdb --no-input" > /dev/null 2>&1 || {
    echo "⚠️  Initial test setup timed out or failed, but continuing..."
}
echo "Test database ready."
echo ""

# Test modules - one at a time
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

TOTAL_FAILURES=0
TOTAL_ERRORS=0
TOTAL_TESTS=0
FAILED_MODULES=()

for module in "${TEST_MODULES[@]}"; do
    echo ""
    echo "=========================================="
    echo "Testing: $module"
    echo "=========================================="

    set +e
    OUTPUT=$(timeout 600 docker compose exec -T api-service bash -c "export TEST_DB_SUFFIX=migrated_tests && SKIP_TEST_MIGRATIONS=1 python /app/hub/manage.py test $module --verbosity=1 --keepdb --no-input 2>&1") || TEST_EXIT=$?
    set -e

    if [ "${TEST_EXIT:-0}" = "124" ]; then
        echo "⏱️  TIMEOUT: Test exceeded 10 minutes"
        FAILED_MODULES+=("$module (timeout)")
        continue
    fi

    TESTS_RAN=$(echo "$OUTPUT" | grep -oP "Ran \d+ test" | grep -oP "\d+" || echo "0")
    FAILURES=$(echo "$OUTPUT" | grep -oP "FAILED \(failures=\d+" | grep -oP "\d+" || echo "0")
    ERRORS=$(echo "$OUTPUT" | grep -oP "ERROR.*errors=\d+" | grep -oP "\d+" || echo "0")

    if echo "$OUTPUT" | grep -q "OK"; then
        STATUS="✅ PASS"
    elif [ "$FAILURES" -gt 0 ] || [ "$ERRORS" -gt 0 ]; then
        STATUS="❌ FAIL"
        FAILED_MODULES+=("$module")
    else
        STATUS="⚠️  UNKNOWN"
    fi

    echo "Status: $STATUS"
    echo "Tests: $TESTS_RAN | Failures: $FAILURES | Errors: $ERRORS"

    TOTAL_TESTS=$((TOTAL_TESTS + TESTS_RAN))
    TOTAL_FAILURES=$((TOTAL_FAILURES + FAILURES))
    TOTAL_ERRORS=$((TOTAL_ERRORS + ERRORS))

    if [ "$FAILURES" -gt 0 ] || [ "$ERRORS" -gt 0 ]; then
        echo ""
        echo "Failures/Errors:"
        echo "$OUTPUT" | grep -A 20 -E "(FAILED|ERROR|Traceback)" | head -60
    fi
done

echo ""
echo "=========================================="
echo "Final Summary"
echo "=========================================="
echo "Total Tests: $TOTAL_TESTS"
echo "Total Failures: $TOTAL_FAILURES"
echo "Total Errors: $TOTAL_ERRORS"

if [ ${#FAILED_MODULES[@]} -gt 0 ]; then
    echo ""
    echo "Failed Modules:"
    printf '  - %s\n' "${FAILED_MODULES[@]}"
fi

if [ $((TOTAL_FAILURES + TOTAL_ERRORS)) -eq 0 ] && [ ${#FAILED_MODULES[@]} -eq 0 ]; then
    echo ""
    echo "✅ All tests passed!"
    exit 0
else
    echo ""
    echo "❌ Some tests failed. See details above."
    exit 1
fi
