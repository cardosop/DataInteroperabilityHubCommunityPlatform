#!/bin/bash
# Endurance Testing Script
#
# Endurance testing (soak testing) runs the system under normal load
# for extended periods to identify memory leaks, resource exhaustion,
# and performance degradation over time.
#
# Usage:
#   ./run_endurance_test.sh [OPTIONS]
#
# Options:
#   --host HOST          API host (default: http://localhost:8000)
#   --users USERS        Number of concurrent users (default: 50)
#   --spawn-rate RATE    Users spawned per second (default: 5)
#   --duration TIME      Test duration (default: 2h, recommended: 4-24h)
#   --output-dir DIR     Output directory (default: tests/performance/results)
#
set -e

# Default configuration
API_HOST="${API_HOST:-http://localhost:8000}"
USERS="${USERS:-50}"
SPAWN_RATE="${SPAWN_RATE:-5}"
DURATION="${DURATION:-2h}"
OUTPUT_DIR="${OUTPUT_DIR:-tests/performance/results}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            API_HOST="$2"
            shift 2
            ;;
        --users)
            USERS="$2"
            shift 2
            ;;
        --spawn-rate)
            SPAWN_RATE="$2"
            shift 2
            ;;
        --duration)
            DURATION="$2"
            shift 2
            ;;
        --output-dir)
            OUTPUT_DIR="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Create results directory
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_DIR="${OUTPUT_DIR}/endurance_test_${TIMESTAMP}"
mkdir -p "$RESULTS_DIR"

echo "========================================="
echo "Endurance Testing (Soak Testing)"
echo "========================================="
echo "API Host: $API_HOST"
echo "Users: $USERS"
echo "Spawn Rate: $SPAWN_RATE users/second"
echo "Duration: $DURATION"
echo "Results: $RESULTS_DIR"
echo ""
echo "WARNING: This test will run for $DURATION"
echo "Monitor system resources during execution"
echo "========================================="
echo ""

# Run endurance test
locust \
    -f tests/performance/locustfile.py \
    EnduranceTestUser \
    --host="$API_HOST" \
    -u "$USERS" \
    -r "$SPAWN_RATE" \
    -t "$DURATION" \
    --headless \
    --html "$RESULTS_DIR/endurance_test.html" \
    --csv "$RESULTS_DIR/endurance_test" \
    --loglevel INFO

echo ""
echo "========================================="
echo "Endurance Test Completed"
echo "Results saved to: $RESULTS_DIR"
echo "========================================="
echo ""
echo "Check results for:"
echo "  - Memory usage trends (should be stable)"
echo "  - Response time trends (should not degrade)"
echo "  - Error rate trends (should remain low)"
echo "  - Resource exhaustion indicators"
