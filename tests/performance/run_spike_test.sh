#!/bin/bash
# Spike Testing Script
#
# Spike testing suddenly increases load to extreme levels to test
# system's ability to handle sudden traffic spikes and recovery behavior.
#
# Usage:
#   ./run_spike_test.sh [OPTIONS]
#
# Options:
#   --host HOST          API host (default: http://localhost:8000)
#   --base-users USERS   Base number of users (default: 50)
#   --spike-users USERS  Spike number of users (default: 500)
#   --spawn-rate RATE    Users spawned per second (default: 100)
#   --duration TIME      Test duration (default: 5m)
#   --output-dir DIR     Output directory (default: tests/performance/results)
#
set -e

# Default configuration
API_HOST="${API_HOST:-http://localhost:8000}"
BASE_USERS="${BASE_USERS:-50}"
SPIKE_USERS="${SPIKE_USERS:-500}"
SPAWN_RATE="${SPAWN_RATE:-100}"
DURATION="${DURATION:-5m}"
OUTPUT_DIR="${OUTPUT_DIR:-tests/performance/results}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --host)
            API_HOST="$2"
            shift 2
            ;;
        --base-users)
            BASE_USERS="$2"
            shift 2
            ;;
        --spike-users)
            SPIKE_USERS="$2"
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
RESULTS_DIR="${OUTPUT_DIR}/spike_test_${TIMESTAMP}"
mkdir -p "$RESULTS_DIR"

echo "========================================="
echo "Spike Testing"
echo "========================================="
echo "API Host: $API_HOST"
echo "Base Users: $BASE_USERS"
echo "Spike Users: $SPIKE_USERS"
echo "Spawn Rate: $SPAWN_RATE users/second"
echo "Duration: $DURATION"
echo "Results: $RESULTS_DIR"
echo ""
echo "Test Pattern:"
echo "  1. Normal load ($BASE_USERS users)"
echo "  2. Sudden spike ($SPIKE_USERS users)"
echo "  3. Sustained spike"
echo "  4. Recovery to normal"
echo "========================================="
echo ""

# Phase 1: Normal load (1 minute)
echo "Phase 1: Normal load..."
locust \
    -f tests/performance/locustfile.py \
    SpikeTestUser \
    --host="$API_HOST" \
    -u "$BASE_USERS" \
    -r 10 \
    -t 1m \
    --headless \
    --csv "$RESULTS_DIR/spike_phase1_normal" \
    --loglevel INFO

# Phase 2: Sudden spike (2 minutes)
echo ""
echo "Phase 2: Sudden spike..."
locust \
    -f tests/performance/locustfile.py \
    SpikeTestUser \
    --host="$API_HOST" \
    -u "$SPIKE_USERS" \
    -r "$SPAWN_RATE" \
    -t 2m \
    --headless \
    --csv "$RESULTS_DIR/spike_phase2_spike" \
    --loglevel INFO

# Phase 3: Recovery (2 minutes)
echo ""
echo "Phase 3: Recovery..."
locust \
    -f tests/performance/locustfile.py \
    SpikeTestUser \
    --host="$API_HOST" \
    -u "$BASE_USERS" \
    -r 10 \
    -t 2m \
    --headless \
    --csv "$RESULTS_DIR/spike_phase3_recovery" \
    --loglevel INFO

echo ""
echo "========================================="
echo "Spike Test Completed"
echo "Results saved to: $RESULTS_DIR"
echo "========================================="
echo ""
echo "Check results for:"
echo "  - Response time during spike"
echo "  - Error rate during spike"
echo "  - Recovery time after spike"
echo "  - System stability during spike"
