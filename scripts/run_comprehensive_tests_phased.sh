#!/bin/bash
# Comprehensive Test Execution - Phased Approach
# Runs tests in manageable phases with progress tracking

set +e  # Don't exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

REPORT_DIR="$PROJECT_DIR/test_reports_comprehensive"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "=========================================="
echo "Comprehensive Test Suite - Phased Execution"
echo "=========================================="
echo "Timestamp: $TIMESTAMP"
echo ""

mkdir -p "$REPORT_DIR"

# Get all apps
APPS=$(docker compose exec -T api-service bash -c "cd /app && find hub/apps -maxdepth 1 -type d -name '[a-z]*' | sort" | grep -v "^$")

if [ -z "$APPS" ]; then
    echo "❌ No apps found"
    exit 1
fi

TOTAL_APPS=$(echo "$APPS" | wc -l)
echo "Found $TOTAL_APPS apps to test"
echo ""

# Phase 1: Unit Tests (All Apps)
echo "=========================================="
echo "PHASE 1: Unit Tests (All Django Apps)"
echo "=========================================="
echo ""

PASSED_APPS=0
FAILED_APPS=0
APP_NUM=0

while IFS= read -r app_path; do
    if [ -z "$app_path" ]; then
        continue
    fi

    # Skip the parent "hub/apps" directory itself
    if [ "$app_path" = "hub/apps" ]; then
        continue
    fi

    ((APP_NUM++))
    app_name=$(echo "$app_path" | sed 's|hub/apps/||')
    app_dot=$(echo "$app_path" | tr '/' '.')

    echo "[$APP_NUM/$TOTAL_APPS] Testing: $app_name"

    LOG_FILE="/tmp/unit_${app_name}_${TIMESTAMP}.log"

    docker compose exec -T api-service bash -c "cd /app/hub && timeout 600 python manage.py test $app_dot --verbosity=1 --keepdb --no-input 2>&1" \
        2>&1 | tee "$LOG_FILE"

    EXIT_CODE=${PIPESTATUS[0]}

    # Extract summary
    if grep -q "OK" "$LOG_FILE" && [ $EXIT_CODE -eq 0 ]; then
        TOTAL=$(grep -oP "Ran \K\d+" "$LOG_FILE" | tail -1 || echo "0")
        echo "  ✅ $app_name: PASSED ($TOTAL tests)"
        ((PASSED_APPS++))
    else
        FAILED=$(grep -oP "\d+ failed" "$LOG_FILE" | grep -oP "\d+" | head -1 || echo "0")
        ERRORS=$(grep -oP "\d+ error" "$LOG_FILE" | grep -oP "\d+" | head -1 || echo "0")
        echo "  ❌ $app_name: FAILED ($FAILED failed, $ERRORS errors)"
        ((FAILED_APPS++))
    fi

    echo ""
    sleep 1  # Small delay between apps

done <<< "$APPS"

echo "=========================================="
echo "Phase 1 Summary: Unit Tests"
echo "=========================================="
echo "Total apps: $TOTAL_APPS"
echo "Passed: $PASSED_APPS"
echo "Failed: $FAILED_APPS"
echo ""

if [ $FAILED_APPS -gt 0 ]; then
    echo "⚠️  Some apps failed. Review logs in /tmp/unit_*_${TIMESTAMP}.log"
    echo ""
    echo "Continuing with other test types..."
    echo ""
fi

# Phase 2: Integration Tests
echo "=========================================="
echo "PHASE 2: Integration Tests"
echo "=========================================="
echo ""

LOG_FILE="/tmp/integration_tests_${TIMESTAMP}.log"

docker compose exec -T api-service bash -c "cd /app/hub && timeout 7200 python manage.py test tests.integration --verbosity=2 --keepdb --no-input 2>&1" \
    2>&1 | tee "$LOG_FILE"

INTEGRATION_EXIT=${PIPESTATUS[0]}

if [ $INTEGRATION_EXIT -eq 0 ]; then
    echo "✅ Integration Tests: PASSED"
else
    echo "❌ Integration Tests: FAILED"
fi
echo ""

# Phase 3: E2E Tests
echo "=========================================="
echo "PHASE 3: E2E Tests"
echo "=========================================="
echo ""

LOG_FILE="/tmp/e2e_tests_${TIMESTAMP}.log"

docker compose exec -T api-service bash -c "cd /app/hub && timeout 10800 python manage.py test tests.e2e --verbosity=2 --keepdb --no-input 2>&1" \
    2>&1 | tee "$LOG_FILE"

E2E_EXIT=${PIPESTATUS[0]}

if [ $E2E_EXIT -eq 0 ]; then
    echo "✅ E2E Tests: PASSED"
else
    echo "❌ E2E Tests: FAILED"
fi
echo ""

# Phase 4: Performance Tests
echo "=========================================="
echo "PHASE 4: Performance Tests"
echo "=========================================="
echo ""

LOG_FILE="/tmp/performance_tests_${TIMESTAMP}.log"

docker compose exec -T api-service bash -c "cd /app/hub && timeout 3600 python manage.py test tests.performance --verbosity=2 --keepdb --no-input 2>&1" \
    2>&1 | tee "$LOG_FILE"

PERF_EXIT=${PIPESTATUS[0]}

if [ $PERF_EXIT -eq 0 ]; then
    echo "✅ Performance Tests: PASSED"
else
    echo "❌ Performance Tests: FAILED"
fi
echo ""

# Phase 5: Security Tests
echo "=========================================="
echo "PHASE 5: Security Tests"
echo "=========================================="
echo ""

LOG_FILE="/tmp/security_tests_${TIMESTAMP}.log"

docker compose exec -T api-service bash -c "cd /app/hub && timeout 1800 python manage.py test tests.security --verbosity=2 --keepdb --no-input 2>&1" \
    2>&1 | tee "$LOG_FILE"

SECURITY_EXIT=${PIPESTATUS[0]}

if [ $SECURITY_EXIT -eq 0 ]; then
    echo "✅ Security Tests: PASSED"
else
    echo "❌ Security Tests: FAILED"
fi
echo ""

# Final Summary
echo "=========================================="
echo "FINAL SUMMARY"
echo "=========================================="
echo ""

OVERALL_STATUS=0

echo "Unit Tests:"
echo "  Apps tested: $TOTAL_APPS"
echo "  Passed: $PASSED_APPS"
echo "  Failed: $FAILED_APPS"
if [ $FAILED_APPS -gt 0 ]; then
    OVERALL_STATUS=1
fi

echo ""
if [ -n "$INTEGRATION_EXIT" ] && [ "$INTEGRATION_EXIT" -eq 0 ]; then
    echo "Integration Tests: ✅ PASSED"
else
    echo "Integration Tests: ❌ FAILED"
    OVERALL_STATUS=1
fi

if [ -n "$E2E_EXIT" ] && [ "$E2E_EXIT" -eq 0 ]; then
    echo "E2E Tests: ✅ PASSED"
else
    echo "E2E Tests: ❌ FAILED"
    OVERALL_STATUS=1
fi

if [ -n "$PERF_EXIT" ] && [ "$PERF_EXIT" -eq 0 ]; then
    echo "Performance Tests: ✅ PASSED"
else
    echo "Performance Tests: ❌ FAILED"
    OVERALL_STATUS=1
fi

if [ -n "$SECURITY_EXIT" ] && [ "$SECURITY_EXIT" -eq 0 ]; then
    echo "Security Tests: ✅ PASSED"
else
    echo "Security Tests: ❌ FAILED"
    OVERALL_STATUS=1
fi

echo ""

if [ $OVERALL_STATUS -eq 0 ]; then
    echo "✅ All test types passed!"
else
    echo "❌ Some test types failed"
    echo ""
    echo "Review logs in: /tmp/*_tests_${TIMESTAMP}.log"
    echo "Fix issues and re-run."
fi

exit $OVERALL_STATUS
