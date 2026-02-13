#!/bin/bash
# Restart verification with clean state

set -e

echo "=========================================="
echo "Restarting Test Verification (Clean State)"
echo "=========================================="
echo ""

# Kill any remaining processes
echo "1. Cleaning up processes..."
pkill -f "verify_batch_fixes.py" 2>/dev/null || true
pkill -f "manage.py test" 2>/dev/null || true
sleep 2

# Terminate stuck database connections
echo "2. Terminating stuck database connections..."
docker compose exec -T postgres psql -U hub -d postgres -c "
SELECT pg_terminate_backend(pid)
FROM pg_stat_activity
WHERE datname LIKE 'hub_test%'
  AND state != 'idle'
  AND pid != pg_backend_pid();
" > /dev/null 2>&1 || true

# Clean up old test databases (keep last 10)
echo "3. Cleaning up old test databases..."
docker compose exec -T postgres psql -U hub -d postgres <<'SQL' > /dev/null 2>&1 || true
DO \$\$
DECLARE
    dbname TEXT;
    db_count INT;
BEGIN
    -- Get count of test databases
    SELECT COUNT(*) INTO db_count
    FROM pg_database
    WHERE datname LIKE 'hub_test%';

    -- If more than 10, drop oldest ones
    IF db_count > 10 THEN
        FOR dbname IN
            SELECT datname
            FROM pg_database
            WHERE datname LIKE 'hub_test%'
            ORDER BY datname
            LIMIT (db_count - 10)
        LOOP
            -- Terminate connections first
            PERFORM pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = dbname AND pid != pg_backend_pid();

            -- Drop database
            EXECUTE 'DROP DATABASE IF EXISTS ' || quote_ident(dbname);
        END LOOP;
    END IF;
END \$\$;
SQL

echo "4. Starting verification with increased timeout..."
echo ""

# Restart verification with increased timeout
docker compose exec -T api-service python3 /app/scripts/verify_batch_fixes.py \
    --signal-fixes \
    --timeout 3600 \
    2>&1 | tee /tmp/verification_restart_$(date +%Y%m%d_%H%M%S).log

echo ""
echo "=========================================="
echo "Verification restarted"
echo "=========================================="
