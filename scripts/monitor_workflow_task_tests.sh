#!/bin/bash
# Script to monitor workflow task business rules integration tests

LOG_FILE="/tmp/workflow_tests_background.log"

echo "=========================================="
echo "Monitoring Workflow Task Tests"
echo "=========================================="
echo ""
echo "Log file: $LOG_FILE"
echo ""

if [ ! -f "$LOG_FILE" ]; then
    echo "⚠️  Log file not found. Test may not be running."
    echo ""
    echo "To start the test:"
    echo "  docker compose exec -d api-service bash -c \"cd /app && python hub/manage.py test hub.apps.orchestration.tests.test_workflow_task_business_rules_integration --verbosity=2 --keepdb --no-input > $LOG_FILE 2>&1\""
    exit 1
fi

echo "Current status:"
echo "----------------------------------------"

# Check if test is still running
if docker compose exec -T api-service bash -c "pgrep -f 'test.*workflow_task_business_rules' > /dev/null 2>&1" 2>/dev/null; then
    echo "✅ Test is running"
else
    echo "⏸️  Test process not found (may have completed or not started)"
fi

echo ""
echo "Last 20 lines of log:"
echo "----------------------------------------"
docker compose exec -T api-service bash -c "tail -20 $LOG_FILE 2>/dev/null" 2>/dev/null || tail -20 "$LOG_FILE" 2>/dev/null

echo ""
echo "Test execution summary:"
echo "----------------------------------------"
docker compose exec -T api-service bash -c "grep -E '(test_|OK|FAILED|ERROR|Ran|passed|failed|skipped)' $LOG_FILE 2>/dev/null | tail -20" 2>/dev/null || grep -E "(test_|OK|FAILED|ERROR|Ran|passed|failed|skipped)" "$LOG_FILE" 2>/dev/null | tail -20

echo ""
echo "Migration progress:"
echo "----------------------------------------"
docker compose exec -T api-service bash -c "grep -E 'Applying|OK|Creating' $LOG_FILE 2>/dev/null | tail -10" 2>/dev/null || grep -E "Applying|OK|Creating" "$LOG_FILE" 2>/dev/null | tail -10

echo ""
echo "To monitor in real-time:"
echo "  docker compose exec -T api-service bash -c 'tail -f $LOG_FILE'"
echo ""
echo "To view full log:"
echo "  docker compose exec -T api-service bash -c 'cat $LOG_FILE'"
