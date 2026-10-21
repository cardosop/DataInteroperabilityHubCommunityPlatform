#!/bin/bash
# Quick script to fix test database lock issues
# Uses Docker exec to terminate connections and drop test database

set -e

CONTAINER_NAME="${POSTGRES_CONTAINER:-hub-postgres-staging}"
DB_USER="${POSTGRES_USER:-hub_staging}"
TEST_DB_NAME="${TEST_DB_NAME:-hub_staging_test}"

echo "Fixing test database lock..."
echo "Container: $CONTAINER_NAME"
echo "Database: $TEST_DB_NAME"

# Terminate connections
echo "Terminating connections to $TEST_DB_NAME..."
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d postgres -c \
  "SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity WHERE pg_stat_activity.datname = '$TEST_DB_NAME' AND pid <> pg_backend_pid();" || true

# Wait a moment
sleep 0.5

# Drop database
echo "Dropping test database $TEST_DB_NAME..."
docker exec "$CONTAINER_NAME" psql -U "$DB_USER" -d postgres -c \
  "DROP DATABASE IF EXISTS $TEST_DB_NAME;" || true

echo "✓ Test database lock fixed!"
echo "You can now run tests without database lock errors."

