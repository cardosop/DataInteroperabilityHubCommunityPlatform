#!/bin/bash
# Run lineage service comprehensive validation tests

set -e

echo "Running Lineage Service Comprehensive Validation Tests..."
echo "========================================================="

cd /home/ph/Desktop/DataInteroperabilityHub

# Run tests and capture output
docker compose exec -T api-service python manage.py test \
    tests.integration.test_lineage_service_comprehensive_validation \
    --verbosity=2 \
    --keepdb \
    2>&1 | tee /tmp/lineage_tests_output.log

# Extract summary
echo ""
echo "========================================================="
echo "Test Summary:"
echo "========================================================="
grep -E "(Ran|FAILED|ERROR|OK|skipped)" /tmp/lineage_tests_output.log | tail -5

# Show failures if any
if grep -q "FAILED\|ERROR" /tmp/lineage_tests_output.log; then
    echo ""
    echo "========================================================="
    echo "Failures/Errors:"
    echo "========================================================="
    grep -A 20 "FAILED\|ERROR" /tmp/lineage_tests_output.log | head -100
fi
