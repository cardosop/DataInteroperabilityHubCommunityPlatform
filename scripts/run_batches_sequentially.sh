#!/bin/bash
# Run test batches sequentially to avoid I/O contention

# Don't use set -e globally - we want to continue even if one batch fails
set +e

TIMEOUT=1800  # 30 minutes per batch
REPORT_DIR="test_reports_comprehensive"

echo "=========================================="
echo "Running Test Batches Sequentially"
echo "=========================================="
echo ""
echo "This approach runs one batch at a time to avoid"
echo "database I/O contention issues."
echo ""

BATCHES=(
    "hub/apps/developer:Developer App"
    "hub/apps/audit:Audit App"
    "hub/apps/graphql:GraphQL App"
    "hub/apps/notifications:Notifications App"
    "hub/apps/search:Search App"
)

RESULTS=()
PASSED=0
FAILED=0

for batch in "${BATCHES[@]}"; do
    IFS=':' read -r app_path batch_name <<< "$batch"

    echo "=========================================="
    echo "Running: $batch_name ($app_path)"
    echo "=========================================="
    echo ""

    # Clean up old test databases before each batch (keep last 3)
    # Use simpler approach: just terminate connections, don't drop databases
    # (Dropping causes I/O contention - let them be cleaned up later)
    echo "Cleaning up old test database connections..."
    timeout 10 docker compose exec -T postgres psql -U hub -d postgres -c "
        SELECT pg_terminate_backend(pid)
        FROM pg_stat_activity
        WHERE datname LIKE 'hub_test%'
          AND state != 'idle'
          AND pid != pg_backend_pid();
    " > /dev/null 2>&1 || true
    echo "Cleanup complete."
    echo ""

    # Run the batch
    LOG_FILE="/tmp/batch_$(echo $app_path | tr '/' '_')_$(date +%Y%m%d_%H%M%S).log"

    echo "Starting batch execution (timeout: ${TIMEOUT}s)..."
    echo "Log file: $LOG_FILE"
    echo ""

    # Run the batch and capture exit code properly
    # Use unbuffered Python output and tee to both file and stdout
    docker compose exec -T api-service python3 -u /app/scripts/verify_batch_fixes.py \
        --batches "$app_path" \
        --timeout "$TIMEOUT" \
        2>&1 | tee "$LOG_FILE"

    EXIT_CODE=${PIPESTATUS[0]}

    echo ""

    # Check results
    if [ $EXIT_CODE -eq 0 ]; then
        if grep -q "✅.*PASSED\|All batches passed" "$LOG_FILE"; then
            echo "✅ $batch_name: PASSED"
            RESULTS+=("✅ $batch_name: PASSED")
            ((PASSED++))
        else
            echo "❌ $batch_name: FAILED (exit code: $EXIT_CODE)"
            RESULTS+=("❌ $batch_name: FAILED")
            ((FAILED++))
        fi
    else
        echo "❌ $batch_name: ERROR (exit code: $EXIT_CODE)"
        RESULTS+=("❌ $batch_name: ERROR")
        ((FAILED++))
    fi

    echo ""
    echo "Waiting 5 seconds before next batch..."
    sleep 5
    echo ""
done

# Summary
echo "=========================================="
echo "SUMMARY"
echo "=========================================="
echo ""
for result in "${RESULTS[@]}"; do
    echo "$result"
done
echo ""
echo "Total: ${#BATCHES[@]} batches"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "✅ All batches passed!"
    exit 0
else
    echo "❌ Some batches failed"
    exit 1
fi
