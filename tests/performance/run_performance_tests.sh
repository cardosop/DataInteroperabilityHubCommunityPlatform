#!/bin/bash
# Script to run performance tests

set -e

# Configuration
API_HOST="${API_HOST:-http://localhost:8000}"
USERS="${USERS:-50}"
SPAWN_RATE="${SPAWN_RATE:-5}"
RUN_TIME="${RUN_TIME:-5m}"
TEST_TYPE="${TEST_TYPE:-all}"

echo "Starting performance tests..."
echo "API Host: $API_HOST"
echo "Users: $USERS"
echo "Spawn Rate: $SPAWN_RATE"
echo "Run Time: $RUN_TIME"
echo "Test Type: $TEST_TYPE"

# Create results directory
RESULTS_DIR="tests/performance/results/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$RESULTS_DIR"

# Function to run a specific test
run_test() {
    local test_name=$1
    local user_class=$2
    
    echo ""
    echo "========================================="
    echo "Running: $test_name"
    echo "========================================="
    
    locust \
        -f tests/performance/locustfile.py \
        --host="$API_HOST" \
        -u "$USERS" \
        -r "$SPAWN_RATE" \
        -t "$RUN_TIME" \
        --headless \
        --html "$RESULTS_DIR/${test_name}.html" \
        --csv "$RESULTS_DIR/${test_name}" \
        --loglevel INFO \
        $user_class
}

# Run tests based on type
case "$TEST_TYPE" in
    file)
        run_test "T15_file_upload_download" "FileUploadDownloadUser"
        ;;
    job)
        run_test "T16_job_queue_throughput" "JobQueueThroughputUser"
        ;;
    db)
        run_test "T17_database_query_performance" "DatabaseQueryPerformanceUser"
        ;;
    api)
        run_test "T18_api_endpoints_availability" "APIEndpointsAvailabilityUser"
        ;;
    all)
        run_test "T15_file_upload_download" "FileUploadDownloadUser"
        run_test "T16_job_queue_throughput" "JobQueueThroughputUser"
        run_test "T17_database_query_performance" "DatabaseQueryPerformanceUser"
        run_test "T18_api_endpoints_availability" "APIEndpointsAvailabilityUser"
        ;;
    *)
        echo "Unknown test type: $TEST_TYPE"
        echo "Valid types: file, job, db, api, all"
        exit 1
        ;;
esac

echo ""
echo "========================================="
echo "Performance tests completed!"
echo "Results saved to: $RESULTS_DIR"
echo "========================================="

