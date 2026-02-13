#!/bin/bash
# Run all unit tests for all Django apps
# Excludes integration and E2E tests by pattern

set +e  # Don't exit on error - we want to collect all results

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

REPORT_DIR="$PROJECT_DIR/test_reports_comprehensive"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
MAIN_LOG="/tmp/unit_tests_all_apps_${TIMESTAMP}.log"

echo "=========================================="
echo "Unit Tests - All Django Apps"
echo "=========================================="
echo "Log: $MAIN_LOG"
echo ""

# Create report directory
mkdir -p "$REPORT_DIR"

# Get all app directories
APPS=$(docker compose exec -T api-service bash -c "cd /app && find hub/apps -maxdepth 1 -type d -name '[a-z]*' | sort" | grep -v "^$")

if [ -z "$APPS" ]; then
    echo "❌ No apps found"
    exit 1
fi

echo "Found $(echo "$APPS" | wc -l) apps to test"
echo ""

# Track results
TOTAL_APPS=0
PASSED_APPS=0
FAILED_APPS=0
RESULTS=()

# Function to run tests for an app
run_app_tests() {
    local app_path=$1
    local app_name=$(echo "$app_path" | sed 's|hub/apps/||')

    echo "=========================================="
    echo "Testing: $app_name"
    echo "Path: $app_path"
    echo "=========================================="
    echo ""

    LOG_FILE="/tmp/unit_${app_name}_${TIMESTAMP}.log"
    START_TIME=$(date +%s)

    # Convert path to Django app notation (hub/apps/developer -> hub.apps.developer)
    app_dot=$(echo "$app_path" | tr '/' '.')

    # Run tests, excluding integration and e2e patterns
    docker compose exec -T api-service bash -c "cd /app/hub && python manage.py test $app_dot --verbosity=1 --keepdb --no-input 2>&1" \
        2>&1 | tee "$LOG_FILE"

    EXIT_CODE=${PIPESTATUS[0]}
    END_TIME=$(date +%s)
    DURATION=$((END_TIME - START_TIME))

    # Extract test summary from output
    TOTAL=$(grep -oP "Ran \K\d+" "$LOG_FILE" | tail -1 || echo "0")
    PASSED=$(grep -oP "\d+ passed" "$LOG_FILE" | grep -oP "\d+" | head -1 || echo "0")
    FAILED=$(grep -oP "\d+ failed" "$LOG_FILE" | grep -oP "\d+" | head -1 || echo "0")
    ERRORS=$(grep -oP "\d+ error" "$LOG_FILE" | grep -oP "\d+" | head -1 || echo "0")

    echo ""
    if [ $EXIT_CODE -eq 0 ]; then
        echo "✅ $app_name: PASSED ($TOTAL tests, ${DURATION}s)"
        ((PASSED_APPS++))
        RESULTS+=("$app_name:PASSED:$TOTAL:$DURATION")
    else
        echo "❌ $app_name: FAILED ($TOTAL tests, $FAILED failed, $ERRORS errors, ${DURATION}s)"
        ((FAILED_APPS++))
        RESULTS+=("$app_name:FAILED:$TOTAL:$FAILED:$ERRORS:$DURATION")
    fi
    echo ""

    return $EXIT_CODE
}

# Run tests for each app
while IFS= read -r app_path; do
    if [ -n "$app_path" ]; then
        ((TOTAL_APPS++))
        run_app_tests "$app_path"

        # Small delay between apps to avoid database contention
        sleep 2
    fi
done <<< "$APPS"

# Generate summary
echo ""
echo "=========================================="
echo "Unit Tests Summary"
echo "=========================================="
echo ""

for result in "${RESULTS[@]}"; do
    IFS=':' read -r app status rest <<< "$result"
    if [ "$status" = "PASSED" ]; then
        echo "✅ $app: PASSED"
    else
        echo "❌ $app: FAILED"
    fi
done

echo ""
echo "Total apps: $TOTAL_APPS"
echo "Passed: $PASSED_APPS"
echo "Failed: $FAILED_APPS"
echo ""

if [ $FAILED_APPS -eq 0 ]; then
    echo "✅ All unit tests passed!"
    exit 0
else
    echo "❌ Some apps failed"
    exit 1
fi
