#!/bin/bash
# Run Files Service Comprehensive Validation Tests
# Runs tests in batches to avoid timeouts

set -e

echo "=========================================="
echo "Files Service Comprehensive Validation Tests"
echo "=========================================="
echo ""

cd /home/ph/Desktop/DataInteroperabilityHub

# Test classes to run
TEST_CLASSES=(
    "tests.integration.test_files_service_comprehensive_validation.FileUploadTest"
    "tests.integration.test_files_service_comprehensive_validation.FileDownloadTest"
    "tests.integration.test_files_service_comprehensive_validation.FileStorageTest"
    "tests.integration.test_files_service_comprehensive_validation.FileValidationTest"
    "tests.integration.test_files_service_comprehensive_validation.FilesODPSIntegrationTest"
)

TOTAL_PASSED=0
TOTAL_FAILED=0
TOTAL_ERRORED=0
TOTAL_SKIPPED=0

for test_class in "${TEST_CLASSES[@]}"; do
    echo "----------------------------------------"
    echo "Running: $test_class"
    echo "----------------------------------------"
    
    # Run test class with timeout
    if timeout 600 docker compose exec -T api-service python manage.py test \
        "$test_class" \
        --verbosity=2 \
        --keepdb \
        --failfast 2>&1 | tee /tmp/test_output.log; then
        
        # Parse results
        PASSED=$(grep -oP '(\d+) passed' /tmp/test_output.log | grep -oP '\d+' | head -1 || echo "0")
        FAILED=$(grep -oP '(\d+) failed' /tmp/test_output.log | grep -oP '\d+' | head -1 || echo "0")
        ERRORED=$(grep -oP '(\d+) error' /tmp/test_output.log | grep -oP '\d+' | head -1 || echo "0")
        SKIPPED=$(grep -oP '(\d+) skipped' /tmp/test_output.log | grep -oP '\d+' | head -1 || echo "0")
        
        TOTAL_PASSED=$((TOTAL_PASSED + PASSED))
        TOTAL_FAILED=$((TOTAL_FAILED + FAILED))
        TOTAL_ERRORED=$((TOTAL_ERRORED + ERRORED))
        TOTAL_SKIPPED=$((TOTAL_SKIPPED + SKIPPED))
        
        echo "Results: $PASSED passed, $FAILED failed, $ERRORED errored, $SKIPPED skipped"
    else
        echo "Test class failed or timed out"
        TOTAL_FAILED=$((TOTAL_FAILED + 1))
    fi
    
    echo ""
done

echo "=========================================="
echo "Summary"
echo "=========================================="
echo "Total Passed: $TOTAL_PASSED"
echo "Total Failed: $TOTAL_FAILED"
echo "Total Errored: $TOTAL_ERRORED"
echo "Total Skipped: $TOTAL_SKIPPED"
echo "=========================================="

if [ $TOTAL_FAILED -gt 0 ] || [ $TOTAL_ERRORED -gt 0 ]; then
    exit 1
else
    exit 0
fi
