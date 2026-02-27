#!/bin/bash
# Script to run performance tests
# Runs Locust from host if installed, otherwise via Docker (api-service-test has locust).
# Run from repo root. Prerequisite: stack up (e.g. docker compose -f docker-compose.test.yml up -d).

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$PROJECT_ROOT"

# Configuration
API_HOST="${API_HOST:-http://localhost:8000}"
USERS="${USERS:-50}"
SPAWN_RATE="${SPAWN_RATE:-5}"
RUN_TIME="${RUN_TIME:-5m}"
TEST_TYPE="${TEST_TYPE:-all}"

# Detect Docker fallback: use when locust not on host
USE_DOCKER=false
if ! command -v locust &>/dev/null; then
    if [[ "$API_HOST" == *":8001"* ]]; then
        USE_DOCKER=true
        COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.test.yml}"
        API_SVC="api-service-test"
        INTERNAL_HOST="http://api-service-test:8000"
    elif [[ "$API_HOST" == *":8000"* ]]; then
        USE_DOCKER=true
        COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.dev.yml}"
        API_SVC="api-service"
        INTERNAL_HOST="http://api-service:8000"
    else
        echo "Error: locust not found. Install with: pip install locust"
        echo "  Or use API_HOST=http://localhost:8001 (test stack) / http://localhost:8000 (dev) to run via Docker."
        exit 1
    fi
    echo "locust not on host; running via Docker (${COMPOSE_FILE} ${API_SVC})"
fi

echo "Starting performance tests..."
echo "API Host: $API_HOST"
echo "Users: $USERS"
echo "Spawn Rate: $SPAWN_RATE"
echo "Run Time: $RUN_TIME"
echo "Test Type: $TEST_TYPE"

# Create results directory (host path; Docker will use /app/... which maps to repo)
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

    if [[ "$USE_DOCKER" == "true" ]]; then
        docker compose -f "${COMPOSE_FILE}" exec -T "${API_SVC}" bash -c \
            "cd /app && locust \
            -f tests/performance/locustfile.py \
            --host=${INTERNAL_HOST} \
            -u ${USERS} \
            -r ${SPAWN_RATE} \
            -t ${RUN_TIME} \
            --headless \
            --html /app/${RESULTS_DIR}/${test_name}.html \
            --csv /app/${RESULTS_DIR}/${test_name} \
            --loglevel INFO \
            ${user_class}"
    else
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
    fi
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

