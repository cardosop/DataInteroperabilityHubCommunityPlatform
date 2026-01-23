#!/bin/bash
# Run Files Service tests in background and capture results

cd /home/ph/Desktop/DataInteroperabilityHub

echo "Starting Files Service Comprehensive Validation Tests..."
echo "This will take 15-20 minutes due to TransactionTestCase database setup"
echo ""

# Run tests in background and capture output
nohup docker compose exec -T api-service python manage.py test \
    tests.integration.test_files_service_comprehensive_validation \
    --verbosity=2 \
    --keepdb \
    > /tmp/files_service_tests_complete.log 2>&1 &

TEST_PID=$!
echo "Test process started with PID: $TEST_PID"
echo "Log file: /tmp/files_service_tests_complete.log"
echo ""
echo "To check progress: tail -f /tmp/files_service_tests_complete.log"
echo "To check results: grep -E '(OK|FAIL|ERROR|Ran|passed|failed|skipped)' /tmp/files_service_tests_complete.log | tail -20"
