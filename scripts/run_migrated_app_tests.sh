#!/bin/bash
# Test execution script for all migrated app tests (mock/stub migration)
# Uses --keepdb for faster runs after initial database creation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "Running Migrated App Tests (Mock Migration)"
echo "=========================================="
echo ""

# Test files to run (all migrated apps from task 27.4.2)
TEST_FILES=(
    # scheduled_ingestion
    "hub.apps.scheduled_ingestion.tests.test_services"
    "hub.apps.scheduled_ingestion.tests.test_ingestion"
    "hub.apps.scheduled_ingestion.tests.test_views"

    # auth
    "hub.apps.auth.tests.test_authorization"
    "hub.apps.auth.tests.test_register_me"
    "hub.apps.auth.tests.test_middleware"

    # jobs
    "hub.apps.jobs.tests.test_job_processors"

    # contracts (key migrated files)
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

    # assets
    "hub.apps.assets.tests.test_asset_relationships"

    # tenants
    "hub.apps.tenants.tests.test_tenant_config_file_upload_integration"
    "hub.apps.tenants.tests.test_tenant_config_compliance_integration"
    "hub.apps.tenants.tests.test_tenant_config_dq_integration"
    "hub.apps.tenants.tests.test_tenant_config_job_integration"
)

# Build test path
TEST_PATH=$(IFS=' '; echo "${TEST_FILES[*]}")

echo "Test files (${#TEST_FILES[@]} total):"
for file in "${TEST_FILES[@]}"; do
    echo "  - $file"
done
echo ""

# Run tests with --keepdb for faster execution
echo "Running tests with --keepdb (faster after first run)..."
echo ""

docker compose exec -T api-service python /app/hub/manage.py test \
    $TEST_PATH \
    --verbosity=2 \
    --keepdb \
    --no-input

echo ""
echo "=========================================="
echo "Tests completed"
echo "=========================================="
