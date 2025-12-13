#!/bin/bash
# Stress Testing Script
#
# Stress testing pushes the system beyond normal operational capacity
# to identify breaking points, resource limits, and failure modes.
#
# Usage:
#   ./run_stress_test.sh [OPTIONS]
#
# Options:
#   --host HOST          API host (default: http://localhost:8000)
#   --users USERS        Number of concurrent users (default: 200)
#   --spawn-rate RATE    Users spawned per second (default: 20)
#   --duration TIME      Test duration (default: 10m)
#   --output-dir DIR     Output directory (default: tests/performance/results)
#
set -e

# Default configuration
API_HOST="${API_HOST:-http://localhost:8000}"
USERS="${USERS:-200}"
SPAWN_RATE="${SPAWN_RATE:-20}"
DURATION="${DURATION:-10m}"
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
RESULTS_DIR="${OUTPUT_DIR}/stress_test_${TIMESTAMP}"
mkdir -p "$RESULTS_DIR"

echo "========================================="
echo "Stress Testing"
echo "========================================="
echo "API Host: $API_HOST"
echo "Users: $USERS"
echo "Spawn Rate: $SPAWN_RATE users/second"
echo "Duration: $DURATION"
echo "Results: $RESULTS_DIR"
echo "========================================="
echo ""

# Run stress test
locust \
    -f tests/performance/locustfile.py \
    StressTestUser \
    --host="$API_HOST" \
    -u "$USERS" \
    -r "$SPAWN_RATE" \
    -t "$DURATION" \
    --headless \
    --html "$RESULTS_DIR/stress_test.html" \
    --csv "$RESULTS_DIR/stress_test" \
    --loglevel INFO

echo ""
echo "========================================="
echo "Stress Test Completed"
echo "Results saved to: $RESULTS_DIR"
echo "========================================="
