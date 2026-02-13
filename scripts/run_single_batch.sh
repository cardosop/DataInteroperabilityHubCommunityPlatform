#!/bin/bash
# Run a single test batch for easy iteration

set +e

if [ -z "$1" ]; then
    echo "Usage: $0 <app_path> [timeout]"
    echo ""
    echo "Examples:"
    echo "  $0 hub/apps/developer"
    echo "  $0 hub/apps/audit 1800"
    echo "  $0 hub/apps/graphql"
    echo ""
    echo "Available batches:"
    echo "  - hub/apps/developer (Developer App)"
    echo "  - hub/apps/audit (Audit App)"
    echo "  - hub/apps/graphql (GraphQL App)"
    echo "  - hub/apps/notifications (Notifications App)"
    echo "  - hub/apps/search (Search App)"
    exit 1
fi

APP_PATH="$1"
TIMEOUT="${2:-1800}"  # Default 30 minutes

# Extract app name for display
APP_NAME=$(echo "$APP_PATH" | sed 's|hub/apps/||' | sed 's|_| |g' | awk '{for(i=1;i<=NF;i++)sub(/./,toupper(substr($i,1,1)),$i)}1')

echo "=========================================="
echo "Running: $APP_NAME"
echo "App Path: $APP_PATH"
echo "Timeout: ${TIMEOUT}s"
echo "=========================================="
echo ""

# Clean up old test database connections
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
echo "Starting test execution..."
echo ""

docker compose exec -T api-service python3 -u /app/scripts/verify_batch_fixes.py \
    --batches "$APP_PATH" \
    --timeout "$TIMEOUT"

EXIT_CODE=$?

echo ""
echo "=========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ Batch completed successfully"
else
    echo "❌ Batch failed (exit code: $EXIT_CODE)"
fi
echo "=========================================="

exit $EXIT_CODE
