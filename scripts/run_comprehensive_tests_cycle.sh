#!/bin/bash
# Comprehensive Test Execution with Fix Cycle
# Runs tests, evaluates results, fixes issues, repeats until all pass

set +e  # Don't exit on error - we want to collect all results

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

REPORT_DIR="$PROJECT_DIR/test_reports_comprehensive"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
CYCLE_LOG="$REPORT_DIR/COMPREHENSIVE_TEST_CYCLE_${TIMESTAMP}.log"

echo "=========================================="
echo "Comprehensive Test Execution Cycle"
echo "=========================================="
echo "Log: $CYCLE_LOG"
echo ""

# Create report directory
mkdir -p "$REPORT_DIR"

# Function to run test type and capture results
run_test_type() {
    local test_type=$1
    local description=$2
    local cycle_num=$3

    echo "=========================================="
    echo "[Cycle $cycle_num] Running: $description"
    echo "=========================================="
    echo ""

    LOG_FILE="/tmp/comprehensive_${test_type}_cycle${cycle_num}_${TIMESTAMP}.log"

    docker compose exec -T api-service python3 -u /app/scripts/run_comprehensive_test_execution_docker.py \
        --test-type "$test_type" \
        --report-dir /app/test_reports_comprehensive \
        2>&1 | tee "$LOG_FILE"

    EXIT_CODE=${PIPESTATUS[0]}

    echo ""
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ $description: PASSED"
        return 0
    else
        echo "❌ $description: FAILED (exit code: $EXIT_CODE)"
        return 1
    fi
}

# Track overall status
MAX_CYCLES=5
CYCLE=1
ALL_PASSED=false

# Test types to run
TEST_TYPES=("unit" "integration" "e2e" "performance" "security")

while [ $CYCLE -le $MAX_CYCLES ] && [ "$ALL_PASSED" = false ]; do
    echo ""
    echo "=========================================="
    echo "CYCLE $CYCLE of $MAX_CYCLES"
    echo "=========================================="
    echo ""

    CYCLE_PASSED=true
    RESULTS=()

    # Run all test types
    for test_type in "${TEST_TYPES[@]}"; do
        case $test_type in
            "unit")
                desc="Unit Tests"
                ;;
            "integration")
                desc="Integration Tests"
                ;;
            "e2e")
                desc="E2E Tests"
                ;;
            "performance")
                desc="Performance Tests"
                ;;
            "security")
                desc="Security Tests"
                ;;
            *)
                desc="$test_type Tests"
                ;;
        esac

        run_test_type "$test_type" "$desc" "$CYCLE"
        if [ $? -ne 0 ]; then
            CYCLE_PASSED=false
            RESULTS+=("$test_type:FAILED")
        else
            RESULTS+=("$test_type:PASSED")
        fi

        echo ""
        echo "Waiting 10 seconds before next test type..."
        sleep 10
        echo ""
    done

    # Check if all passed
    if [ "$CYCLE_PASSED" = true ]; then
        ALL_PASSED=true
        echo "=========================================="
        echo "✅ ALL TESTS PASSED in Cycle $CYCLE!"
        echo "=========================================="
        break
    else
        echo "=========================================="
        echo "❌ Some tests failed in Cycle $CYCLE"
        echo "=========================================="
        echo ""
        echo "Results:"
        for result in "${RESULTS[@]}"; do
            echo "  $result"
        done
        echo ""
        echo "Please fix issues and re-run, or wait for automatic fix cycle..."
        echo ""

        # Increment cycle
        ((CYCLE++))

        if [ $CYCLE -le $MAX_CYCLES ]; then
            echo "Waiting 30 seconds before next cycle..."
            sleep 30
        fi
    fi
done

# Final summary
echo ""
echo "=========================================="
echo "FINAL SUMMARY"
echo "=========================================="
echo ""

if [ "$ALL_PASSED" = true ]; then
    echo "✅ All test types passed!"
    echo "Total cycles: $CYCLE"
    exit 0
else
    echo "❌ Some test types failed after $MAX_CYCLES cycles"
    echo ""
    echo "Final results:"
    for result in "${RESULTS[@]}"; do
        echo "  $result"
    done
    exit 1
fi
