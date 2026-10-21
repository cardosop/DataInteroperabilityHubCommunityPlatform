#!/bin/bash
# Test execution script for migrated app tests - runs in batches by app
# Uses --keepdb for faster runs after initial database creation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "Running Migrated App Tests (Batch Mode)"
echo "=========================================="
echo ""

# Test batches by app
declare -A TEST_BATCHES=(
    ["scheduled_ingestion"]="hub.apps.scheduled_ingestion.tests.test_services hub.apps.scheduled_ingestion.tests.test_ingestion hub.apps.scheduled_ingestion.tests.test_views"
    ["auth"]="hub.apps.auth.tests.test_authorization hub.apps.auth.tests.test_register_me hub.apps.auth.tests.test_middleware"
    ["jobs"]="hub.apps.jobs.tests.test_job_processors"
    ["contracts"]="hub.apps.contracts.tests.test_caching_enhanced hub.apps.contracts.tests.test_lineage_reference_resolution hub.apps.contracts.tests.test_views_validation hub.apps.contracts.tests.test_validation hub.apps.contracts.tests.test_ref_resolver_caching hub.apps.contracts.tests.test_ref_resolver hub.apps.contracts.tests.test_ref_warming hub.apps.contracts.tests.test_odps_metrics hub.apps.contracts.tests.test_lineage_traversal hub.apps.contracts.tests.test_lineage_visualization hub.apps.contracts.tests.test_lineage_service hub.apps.contracts.tests.test_services hub.apps.contracts.tests.test_cli_client hub.apps.contracts.tests.test_odps_rate_limiting hub.apps.contracts.tests.test_odps_normalizer hub.apps.contracts.tests.security.test_ref_resolver_security hub.apps.contracts.tests.test_rollback_odps_migration"
    ["assets"]="hub.apps.assets.tests.test_asset_relationships"
    ["tenants"]="hub.apps.tenants.tests.test_tenant_config_file_upload_integration hub.apps.tenants.tests.test_tenant_config_compliance_integration hub.apps.tenants.tests.test_tenant_config_dq_integration hub.apps.tenants.tests.test_tenant_config_job_integration"
)

TOTAL_FAILURES=0
TOTAL_ERRORS=0
TOTAL_TESTS=0

for app in "${!TEST_BATCHES[@]}"; do
    echo ""
    echo "=========================================="
    echo "Testing: $app"
    echo "=========================================="

    TEST_PATH="${TEST_BATCHES[$app]}"

    # Run tests for this app
    OUTPUT=$(docker compose exec -T api-service python /app/hub/manage.py test \
        $TEST_PATH \
        --verbosity=1 \
        --keepdb \
        --no-input 2>&1) || true

    # Extract test results
    TESTS_RAN=$(echo "$OUTPUT" | grep -oP "Ran \d+ test" | grep -oP "\d+" || echo "0")
    FAILURES=$(echo "$OUTPUT" | grep -oP "FAILED \(failures=\d+" | grep -oP "\d+" || echo "0")
    ERRORS=$(echo "$OUTPUT" | grep -oP "ERROR.*errors=\d+" | grep -oP "\d+" || echo "0")

    if echo "$OUTPUT" | grep -q "OK"; then
        STATUS="✅ PASS"
    else
        STATUS="❌ FAIL"
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
        echo "$OUTPUT" | grep -A 10 -E "(FAILED|ERROR)" | head -30
    fi
done

echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="
echo "Total Tests: $TOTAL_TESTS"
echo "Total Failures: $TOTAL_FAILURES"
echo "Total Errors: $TOTAL_ERRORS"

if [ $((TOTAL_FAILURES + TOTAL_ERRORS)) -eq 0 ]; then
    echo ""
    echo "✅ All tests passed!"
    exit 0
else
    echo ""
    echo "❌ Some tests failed. See details above."
    exit 1
fi
