#!/bin/bash
# Quick database status check script
# Usage: ./scripts/check_database_status.sh

CONTAINER_NAME="${1:-hub-postgres}"

echo "=== Database Status Check ==="
echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "❌ Container '$CONTAINER_NAME' is not running"
    exit 1
fi

# Check health
HEALTH=$(docker inspect "$CONTAINER_NAME" --format='{{.State.Health.Status}}' 2>/dev/null || echo "no-healthcheck")
echo "Container Health: $HEALTH"

# Check if database accepts connections
if docker exec "$CONTAINER_NAME" pg_isready -U hub >/dev/null 2>&1; then
    echo "Database Status: ✅ Ready (accepting connections)"

    # Check if in recovery
    RECOVERY=$(docker exec "$CONTAINER_NAME" psql -U hub -d hub -t -c "SELECT pg_is_in_recovery();" 2>/dev/null | tr -d ' ')
    if [ "$RECOVERY" = "t" ] || [ "$RECOVERY" = "true" ]; then
        echo "Recovery Status: ⏳ Still in recovery"
    else
        echo "Recovery Status: ✅ Complete"
    fi
else
    echo "Database Status: ⏳ Starting up (not accepting connections)"

    # Check recovery progress from logs
    LAST_SYNC=$(docker logs "$CONTAINER_NAME" 2>&1 | grep "syncing data directory" | tail -1 | grep -oP "elapsed time: \K[0-9.]+" || echo "unknown")
    if [ "$LAST_SYNC" != "unknown" ]; then
        MINUTES=$(echo "$LAST_SYNC / 60" | bc -l 2>/dev/null | cut -d. -f1)
        echo "Recovery Time: ~${MINUTES} minutes elapsed"
    fi
fi

echo ""
echo "For detailed monitoring: ./scripts/monitor_database_recovery.sh $CONTAINER_NAME"
echo "For continuous watch: ./scripts/monitor_database_recovery.sh $CONTAINER_NAME --watch"
