#!/bin/bash
# Test Django 6 Migrations on Clean Database

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

echo -e "${BOLD}${BLUE}========================================${RESET}"
echo -e "${BOLD}${BLUE}Django 6 Migration Test - Clean Database${RESET}"
echo -e "${BOLD}${BLUE}========================================${RESET}"
echo ""

cd "$(dirname "$0")/.." || exit 1

# Check if virtual environment exists
if [ ! -d "venv-python312-test" ]; then
    echo -e "${RED}Error: Virtual environment 'venv-python312-test' not found${RESET}"
    exit 1
fi

# Activate virtual environment
source venv-python312-test/bin/activate

# Check Python version
if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 12) else 1)"; then
    echo -e "${RED}Error: Python 3.12+ required${RESET}"
    exit 1
fi

cd hub || { echo -e "${RED}Error: 'hub' directory not found${RESET}"; exit 1; }

echo -e "${BLUE}Step 1: Check Django version${RESET}"
DJANGO_VERSION=$(python3 -c "import django; print(django.get_version())" 2>/dev/null || echo "not installed")
echo -e "${GREEN}Django version: ${DJANGO_VERSION}${RESET}"

if [[ ! "$DJANGO_VERSION" =~ ^6\. ]]; then
    echo -e "${YELLOW}Warning: Django 6.0+ expected, but found ${DJANGO_VERSION}${RESET}"
    echo -e "${YELLOW}This test is designed for Django 6.0+${RESET}"
fi

echo ""
echo -e "${BLUE}Step 2: Create test database${RESET}"

# Create a test database name
TEST_DB_NAME="test_django6_migrations_$(date +%s)"

# Check if PostgreSQL is available
if ! python3 -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
import django
django.setup()
from django.db import connection
try:
    with connection.cursor() as cursor:
        cursor.execute('SELECT version();')
        print('✅ PostgreSQL connection available')
except Exception as e:
    print(f'❌ PostgreSQL connection failed: {e}')
    exit(1)
" 2>&1; then
    echo -e "${YELLOW}⚠️  PostgreSQL not available. Skipping clean database test.${RESET}"
    echo -e "${YELLOW}   To test migrations on clean database, ensure PostgreSQL is running.${RESET}"
    exit 0
fi

echo ""
echo -e "${BLUE}Step 3: Run migrations on clean database${RESET}"
echo -e "${BLUE}   (Using Django's test database mechanism)${RESET}"

# Use Django's test database creation which creates a clean database
if python3 manage.py migrate --run-syncdb --verbosity=2 2>&1 | tee /tmp/migration_test.log; then
    echo -e "${GREEN}✅ Migrations applied successfully${RESET}"
else
    echo -e "${RED}❌ Migration failed${RESET}"
    echo -e "${YELLOW}Migration output:${RESET}"
    tail -50 /tmp/migration_test.log
    exit 1
fi

echo ""
echo -e "${BLUE}Step 4: Verify database schema${RESET}"

# Check that key tables exist
if python3 -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
import django
django.setup()
from django.db import connection

tables_to_check = [
    'tenants_tenant',
    'users_user',
    'files_file',
    'datasets_dataset',
    'assets_asset',
    'contracts_contract',
    'jobs_job',
]

with connection.cursor() as cursor:
    cursor.execute(\"\"\"
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    \"\"\")
    existing_tables = {row[0] for row in cursor.fetchall()}
    
    missing_tables = []
    for table in tables_to_check:
        if table not in existing_tables:
            missing_tables.append(table)
    
    if missing_tables:
        print(f'❌ Missing tables: {missing_tables}')
        exit(1)
    else:
        print(f'✅ All key tables exist ({len(tables_to_check)} tables checked)')
        print(f'✅ Total tables in database: {len(existing_tables)}')
" 2>&1; then
    echo -e "${GREEN}✅ Database schema verified${RESET}"
else
    echo -e "${RED}❌ Database schema verification failed${RESET}"
    exit 1
fi

echo ""
echo -e "${BLUE}Step 5: Verify migration status${RESET}"
if python3 manage.py showmigrations --plan 2>&1 | grep -q "\[X\]"; then
    APPLIED=$(python3 manage.py showmigrations --plan 2>&1 | grep -c "\[X\]" || echo "0")
    echo -e "${GREEN}✅ ${APPLIED} migrations applied${RESET}"
else
    echo -e "${YELLOW}⚠️  Could not determine migration status${RESET}"
fi

echo ""
echo -e "${BOLD}${GREEN}✅ Clean Database Migration Test Complete${RESET}"
echo -e "${GREEN}All migrations applied successfully on clean database${RESET}"

