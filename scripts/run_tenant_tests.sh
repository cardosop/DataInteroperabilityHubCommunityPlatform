#!/bin/bash
# Test execution script for tenant integration tests
# Uses --keepdb for faster runs after initial database creation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "=========================================="
echo "Running Tenant Integration Tests"
echo "=========================================="
echo ""

# Test files to run
TEST_FILES=(
    "hub.apps.tenants.tests.test_tenant_config_file_upload_integration"
    "hub.apps.tenants.tests.test_tenant_config_compliance_integration"
    "hub.apps.tenants.tests.test_tenant_config_dq_integration"
    "hub.apps.tenants.tests.test_tenant_config_job_integration"
)

# Build test path
TEST_PATH=$(IFS=' '; echo "${TEST_FILES[*]}")

echo "Test files:"
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
