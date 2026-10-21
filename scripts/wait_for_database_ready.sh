#!/bin/bash
# Script to wait for database to become ready
# Usage: ./scripts/wait_for_database_ready.sh [container_name] [timeout_seconds]

set -e

CONTAINER_NAME="${1:-hub-postgres}"
TIMEOUT="${2:-3600}"  # Default 1 hour
INTERVAL=10

echo "Waiting for database '$CONTAINER_NAME' to become ready..."
echo "Timeout: ${TIMEOUT} seconds"
echo ""

START_TIME=$(date +%s)
ELAPSED=0

while [ $ELAPSED -lt $TIMEOUT ]; do
    # Check if container is running
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        echo "ERROR: Container '$CONTAINER_NAME' is not running"
        exit 1
    fi

    # Check if database accepts connections
    if docker exec "$CONTAINER_NAME" pg_isready -U hub >/dev/null 2>&1; then
        # Check if recovery is complete
        RECOVERY=$(docker exec "$CONTAINER_NAME" psql -U hub -d hub -t -c "SELECT pg_is_in_recovery();" 2>/dev/null | tr -d ' ' || echo "unknown")

        if [ "$RECOVERY" != "t" ] && [ "$RECOVERY" != "true" ]; then
            CURRENT_TIME=$(date +%s)
            ELAPSED=$((CURRENT_TIME - START_TIME))
            echo ""
            echo "✅ Database is ready!"
            echo "   Time elapsed: ${ELAPSED} seconds"
            echo "   Recovery complete: Yes"
            exit 0
        else
            echo -n "."
        fi
    else
        # Show progress
        CURRENT_TIME=$(date +%s)
        ELAPSED=$((CURRENT_TIME - START_TIME))
        if [ $((ELAPSED % 60)) -eq 0 ]; then
            echo ""
            echo "[${ELAPSED}s] Still recovering..."
        else
            echo -n "."
        fi
    fi

    sleep $INTERVAL
    CURRENT_TIME=$(date +%s)
    ELAPSED=$((CURRENT_TIME - START_TIME))
done

echo ""
echo "❌ Timeout: Database did not become ready within ${TIMEOUT} seconds"
exit 1
