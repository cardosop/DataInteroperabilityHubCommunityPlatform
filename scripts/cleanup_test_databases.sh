#!/bin/bash
# Cleanup old test databases
# This script drops old test databases to free up space and reduce lock contention

set -e

echo "Cleaning up old test databases..."

# Get list of test databases (excluding hub_test_migrated_tests)
TEST_DBS=$(docker compose exec -T postgres psql -U hub -d postgres -t -c "SELECT datname FROM pg_database WHERE datname LIKE 'hub_test%' AND datname != 'hub_test_migrated_tests' ORDER BY datname;" | tr -d ' ' | grep -v '^$')

if [ -z "$TEST_DBS" ]; then
    echo "No test databases to clean up."
    exit 0
fi

DB_COUNT=$(echo "$TEST_DBS" | wc -l)
echo "Found $DB_COUNT test databases to drop."

# Drop databases one by one
DROPPED=0
FAILED=0

for db in $TEST_DBS; do
    echo -n "Dropping $db... "
    if docker compose exec -T postgres psql -U hub -d postgres -c "DROP DATABASE IF EXISTS $db;" > /dev/null 2>&1; then
        echo "OK"
        ((DROPPED++))
    else
        echo "FAILED"
        ((FAILED++))
    fi
done

echo ""
echo "Summary:"
echo "  Dropped: $DROPPED"
echo "  Failed: $FAILED"
echo "  Remaining: $((DB_COUNT - DROPPED))"
