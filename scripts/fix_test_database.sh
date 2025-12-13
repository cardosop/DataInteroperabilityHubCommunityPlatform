#!/bin/bash
# Script to fix test database infrastructure issues

set -e

echo "=== Fixing Test Database Infrastructure ==="

# Check if Docker PostgreSQL container is running
if ! docker ps | grep -q hub-postgres-staging; then
    echo "ERROR: PostgreSQL container 'hub-postgres-staging' is not running"
    echo "Please start it with: docker start hub-postgres-staging"
    exit 1
fi

echo "✓ PostgreSQL container is running"

# Kill any existing connections to test database (multiple attempts)
echo "Killing existing connections to test database..."
for i in {1..3}; do
    docker exec hub-postgres-staging psql -U hub_staging -d postgres -c "
    SELECT pg_terminate_backend(pid) 
    FROM pg_stat_activity 
    WHERE datname = 'hub_staging_test';
    " 2>&1 | grep -v "terminate_backend" || true
    sleep 1
done

# Drop test database if it exists
echo "Dropping existing test database..."
docker exec hub-postgres-staging psql -U hub_staging -d postgres -c "
DROP DATABASE IF EXISTS hub_staging_test;
" 2>&1 | grep -v "DROP DATABASE" || true

# Create fresh test database
echo "Creating fresh test database..."
docker exec hub-postgres-staging psql -U hub_staging -d postgres -c "
CREATE DATABASE hub_staging_test
WITH OWNER = hub_staging
ENCODING = 'UTF8'
LC_COLLATE = 'en_US.utf8'
LC_CTYPE = 'en_US.utf8'
TEMPLATE = template0;
" 2>&1 | grep -v "CREATE DATABASE" || true

echo "✓ Test database created successfully"

# Verify connection
echo "Verifying database connection..."
docker exec hub-postgres-staging psql -U hub_staging -d hub_staging_test -c "SELECT version();" > /dev/null 2>&1

if [ $? -eq 0 ]; then
    echo "✓ Database connection verified"
else
    echo "ERROR: Failed to connect to test database"
    exit 1
fi

echo ""
echo "=== Test Database Infrastructure Fixed ==="
echo "You can now run tests with:"
echo "  pytest hub/apps/core/events/tests/ -v"

