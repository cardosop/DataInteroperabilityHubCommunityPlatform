#!/bin/bash
# Script to run monitoring observability tests and capture results

set -e

cd /home/ph/Desktop/DataInteroperabilityHub

echo "Running Monitoring & Observability Comprehensive Validation Tests..."
echo "================================================================"

# Run tests with timeout and capture output
docker compose exec -T api-service python manage.py test \
    tests.integration.test_monitoring_observability_comprehensive_validation \
    --verbosity=2 \
    --keepdb \
    2>&1 | tee /tmp/test_output.log

# Extract summary
echo ""
echo "================================================================"
echo "Test Summary:"
echo "================================================================"
grep -E "(FAILED|ERROR|OK|skipped|passed|failed)" /tmp/test_output.log | tail -20

# Count failures
FAILURES=$(grep -c "FAILED\|ERROR" /tmp/test_output.log || echo "0")
echo ""
echo "Total failures/errors: $FAILURES"

if [ "$FAILURES" -gt 0 ]; then
    echo ""
    echo "Detailed failures:"
    grep -A 10 "FAILED\|ERROR" /tmp/test_output.log
    exit 1
fi

exit 0
