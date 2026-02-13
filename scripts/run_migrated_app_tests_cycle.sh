#!/bin/bash
# Test execution script that runs tests in cycles until all pass
# Uses fixed TEST_DB_SUFFIX and SKIP_TEST_MIGRATIONS after initial setup

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

export TEST_DB_SUFFIX="migrated_tests"

echo "=========================================="
echo "Migrated App Tests - Cycle Execution"
echo "=========================================="
echo ""

# Step 1: Ensure test database is migrated (run once)
echo "Step 1: Ensuring test database is properly migrated..."
timeout 900 docker compose exec -T api-service bash -c "export TEST_DB_SUFFIX=migrated_tests && python /app/hub/manage.py test hub.apps.tenants.tests.test_tenant_config_job_integration.TenantConfigJobIntegrationTest.test_job_creation_with_platform_defaults --verbosity=0 --keepdb --no-input" > /dev/null 2>&1 || true
echo "Test database ready."
echo ""

# Test batches by app
declare -A TEST_BATCHES=(
    ["tenants"]="hub.apps.tenants.tests.test_tenant_config_file_upload_integration hub.apps.tenants.tests.test_tenant_config_compliance_integration hub.apps.tenants.tests.test_tenant_config_dq_integration hub.apps.tenants.tests.test_tenant_config_job_integration"
    ["assets"]="hub.apps.assets.tests.test_asset_relationships"
    ["auth"]="hub.apps.auth.tests.test_authorization hub.apps.auth.tests.test_register_me hub.apps.auth.tests.test_middleware"
    ["jobs"]="hub.apps.jobs.tests.test_job_processors"
    ["scheduled_ingestion"]="hub.apps.scheduled_ingestion.tests.test_services hub.apps.scheduled_ingestion.tests.test_ingestion hub.apps.scheduled_ingestion.tests.test_views"
    ["contracts_batch1"]="hub.apps.contracts.tests.test_caching_enhanced hub.apps.contracts.tests.test_lineage_reference_resolution hub.apps.contracts.tests.test_views_validation"
    ["contracts_batch2"]="hub.apps.contracts.tests.test_validation hub.apps.contracts.tests.test_ref_resolver_caching hub.apps.contracts.tests.test_ref_resolver"
    ["contracts_batch3"]="hub.apps.contracts.tests.test_ref_warming hub.apps.contracts.tests.test_odps_metrics hub.apps.contracts.tests.test_lineage_traversal"
    ["contracts_batch4"]="hub.apps.contracts.tests.test_lineage_visualization hub.apps.contracts.tests.test_lineage_service hub.apps.contracts.tests.test_services"
    ["contracts_batch5"]="hub.apps.contracts.tests.test_cli_client hub.apps.contracts.tests.test_odps_rate_limiting hub.apps.contracts.tests.test_odps_normalizer"
    ["contracts_batch6"]="hub.apps.contracts.tests.security.test_ref_resolver_security hub.apps.contracts.tests.test_rollback_odps_migration"
)

TOTAL_FAILURES=0
TOTAL_ERRORS=0
TOTAL_TESTS=0
FAILED_APPS=()

for app in "${!TEST_BATCHES[@]}"; do
    echo ""
    echo "=========================================="
    echo "Testing: $app"
    echo "=========================================="

    TEST_PATH="${TEST_BATCHES[$app]}"

    # Run tests with SKIP_TEST_MIGRATIONS=1 and timeout
    set +e
    OUTPUT=$(timeout 300 docker compose exec -T api-service bash -c "export TEST_DB_SUFFIX=migrated_tests && SKIP_TEST_MIGRATIONS=1 python /app/hub/manage.py test $TEST_PATH --verbosity=1 --keepdb --no-input 2>&1") || TEST_EXIT=$?
    set -e

    # Check for timeout
    if [ "${TEST_EXIT:-0}" = "124" ]; then
        echo "⏱️  TIMEOUT: Tests exceeded 5 minutes"
        FAILED_APPS+=("$app (timeout)")
        continue
    fi

    # Extract test results
    TESTS_RAN=$(echo "$OUTPUT" | grep -oP "Ran \d+ test" | grep -oP "\d+" || echo "0")
    FAILURES=$(echo "$OUTPUT" | grep -oP "FAILED \(failures=\d+" | grep -oP "\d+" || echo "0")
    ERRORS=$(echo "$OUTPUT" | grep -oP "ERROR.*errors=\d+" | grep -oP "\d+" || echo "0")

    if echo "$OUTPUT" | grep -q "OK"; then
        STATUS="✅ PASS"
    elif [ "$FAILURES" -gt 0 ] || [ "$ERRORS" -gt 0 ]; then
        STATUS="❌ FAIL"
        FAILED_APPS+=("$app")
    else
        STATUS="⚠️  UNKNOWN"
    fi

    echo "Status: $STATUS"
    echo "Tests: $TESTS_RAN | Failures: $FAILURES | Errors: $ERRORS"

    TOTAL_TESTS=$((TOTAL_TESTS + TESTS_RAN))
    TOTAL_FAILURES=$((TOTAL_FAILURES + FAILURES))
    TOTAL_ERRORS=$((TOTAL_ERRORS + ERRORS))

    # Show failures/errors if any
    if [ "$FAILURES" -gt 0 ] || [ "$ERRORS" -gt 0 ]; then
        echo ""
        echo "Failures/Errors for $app:"
        echo "$OUTPUT" | grep -A 15 -E "(FAILED|ERROR|Traceback)" | head -40
    fi
done

echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="
echo "Total Tests: $TOTAL_TESTS"
echo "Total Failures: $TOTAL_FAILURES"
echo "Total Errors: $TOTAL_ERRORS"

if [ ${#FAILED_APPS[@]} -gt 0 ]; then
    echo ""
    echo "Failed Apps/Batches:"
    printf '  - %s\n' "${FAILED_APPS[@]}"
fi

if [ $((TOTAL_FAILURES + TOTAL_ERRORS)) -eq 0 ] && [ ${#FAILED_APPS[@]} -eq 0 ]; then
    echo ""
    echo "✅ All tests passed!"
    exit 0
else
    echo ""
    echo "❌ Some tests failed. See details above."
    exit 1
fi
