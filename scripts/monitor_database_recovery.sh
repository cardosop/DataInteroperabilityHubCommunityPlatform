#!/bin/bash
# Script to monitor PostgreSQL database recovery progress
# Usage: ./scripts/monitor_database_recovery.sh [container_name]

set -e

CONTAINER_NAME="${1:-hub-postgres}"

echo "=========================================="
echo "PostgreSQL Recovery Progress Monitor"
echo "=========================================="
echo "Container: $CONTAINER_NAME"
echo ""

# Check if container exists
if ! docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "ERROR: Container '$CONTAINER_NAME' not found"
    exit 1
fi

# Check if container is running
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "WARNING: Container '$CONTAINER_NAME' is not running"
    echo "Starting container..."
    docker start "$CONTAINER_NAME" || {
        echo "ERROR: Failed to start container"
        exit 1
    }
    sleep 2
fi

# Function to check recovery status
check_recovery_status() {
    echo "=== Container Status ==="
    docker ps --filter "name=${CONTAINER_NAME}" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    echo ""

    # Check health status
    HEALTH=$(docker inspect "$CONTAINER_NAME" --format='{{.State.Health.Status}}' 2>/dev/null || echo "no-healthcheck")
    echo "Health Status: $HEALTH"
    echo ""

    # Check if we can connect to check recovery
    if docker exec "$CONTAINER_NAME" pg_isready -U hub >/dev/null 2>&1; then
        echo "✅ Database is accepting connections"
        echo ""

        # Try to check recovery status via SQL
        RECOVERY_STATUS=$(docker exec "$CONTAINER_NAME" psql -U hub -d hub -t -c "SELECT pg_is_in_recovery();" 2>/dev/null || echo "unknown")
        if [ "$RECOVERY_STATUS" = "t" ] || [ "$RECOVERY_STATUS" = "true" ]; then
            echo "⚠️  Database is still in recovery mode"
            echo ""

            # Get recovery progress if available
            RECOVERY_PROGRESS=$(docker exec "$CONTAINER_NAME" psql -U hub -d hub -t -c "SELECT pg_wal_lsn_diff(pg_last_wal_replay_lsn(), pg_current_wal_lsn()) AS bytes_remaining;" 2>/dev/null || echo "unknown")
            if [ "$RECOVERY_PROGRESS" != "unknown" ] && [ -n "$RECOVERY_PROGRESS" ]; then
                echo "Recovery Progress: $RECOVERY_PROGRESS bytes remaining"
            fi
        else
            echo "✅ Database recovery complete - database is ready"
        fi
    else
        echo "⏳ Database is still starting up (not accepting connections yet)"
        echo ""

        # Check logs for recovery progress
        echo "=== Recent Recovery Activity ==="
        docker logs "$CONTAINER_NAME" --tail 20 2>&1 | grep -E "(syncing|recovery|startup|database system)" | tail -5 || echo "No recovery activity found in recent logs"
    fi
    echo ""
}

# Function to show detailed recovery information
show_detailed_info() {
    echo "=== Detailed Recovery Information ==="

    # Check WAL directory size
    WAL_SIZE=$(docker exec "$CONTAINER_NAME" sh -c "du -sh /var/lib/postgresql/data/pg_wal 2>/dev/null | cut -f1" || echo "unknown")
    echo "WAL Directory Size: $WAL_SIZE"

    # Count WAL files (PostgreSQL WAL files don't have .wal extension)
    WAL_COUNT=$(docker exec "$CONTAINER_NAME" sh -c "find /var/lib/postgresql/data/pg_wal -type f -name '000000*' 2>/dev/null | wc -l" || echo "0")
    echo "WAL Files: $WAL_COUNT"

    # Check for recovery signal file
    RECOVERY_SIGNAL=$(docker exec "$CONTAINER_NAME" sh -c "test -f /var/lib/postgresql/data/recovery.signal && echo 'yes' || echo 'no'" 2>/dev/null || echo "unknown")
    echo "Recovery Signal File: $RECOVERY_SIGNAL"

    # Check startup process
    STARTUP_PROC=$(docker exec "$CONTAINER_NAME" ps aux 2>/dev/null | grep -c "postgres: startup" || echo "0")
    if [ "$STARTUP_PROC" -gt 0 ]; then
        echo "Startup Process: Running (recovery in progress)"
    else
        echo "Startup Process: Not running (recovery may be complete)"
    fi

    echo ""
}

# Function to show recent logs
show_recent_logs() {
    echo "=== Recent Database Logs ==="
    docker logs "$CONTAINER_NAME" --tail 30 2>&1 | grep -E "(LOG|ERROR|FATAL|WARNING|syncing|recovery|startup)" | tail -10 || echo "No relevant log entries"
    echo ""
}

# Main monitoring loop
if [ "${2:-}" = "--watch" ] || [ "${2:-}" = "-w" ]; then
    echo "Watching recovery progress (press Ctrl+C to stop)..."
    echo ""

    while true; do
        clear
        echo "=========================================="
        echo "PostgreSQL Recovery Progress Monitor"
        echo "=========================================="
        echo "Container: $CONTAINER_NAME"
        echo "Time: $(date '+%Y-%m-%d %H:%M:%S')"
        echo ""

        check_recovery_status
        show_detailed_info

        # Check if recovery is complete
        if docker exec "$CONTAINER_NAME" pg_isready -U hub >/dev/null 2>&1; then
            RECOVERY_STATUS=$(docker exec "$CONTAINER_NAME" psql -U hub -d hub -t -c "SELECT pg_is_in_recovery();" 2>/dev/null || echo "unknown")
            if [ "$RECOVERY_STATUS" != "t" ] && [ "$RECOVERY_STATUS" != "true" ]; then
                echo "✅ RECOVERY COMPLETE - Database is ready!"
                break
            fi
        fi

        sleep 10
    done
else
    # Single check
    check_recovery_status
    show_detailed_info
    show_recent_logs

    echo "=== Usage ==="
    echo "For continuous monitoring: $0 $CONTAINER_NAME --watch"
    echo ""

    # Provide recommendations
    if ! docker exec "$CONTAINER_NAME" pg_isready -U hub >/dev/null 2>&1; then
        echo "=== Recommendations ==="
        echo "1. Database is still recovering - this can take time with large WAL files"
        echo "2. Monitor progress with: $0 $CONTAINER_NAME --watch"
        echo "3. Check logs with: docker logs -f $CONTAINER_NAME"
        echo "4. If recovery takes too long, consider:"
        echo "   - Checking disk I/O performance"
        echo "   - Reviewing PostgreSQL configuration"
        echo "   - Ensuring proper shutdown procedures are followed"
    fi
fi
