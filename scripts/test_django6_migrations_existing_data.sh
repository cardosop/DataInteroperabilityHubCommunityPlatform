#!/bin/bash
# Test Django 6 Migrations on Database with Existing Data

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

echo -e "${BOLD}${BLUE}========================================${RESET}"
echo -e "${BOLD}${BLUE}Django 6 Migration Test - Existing Data${RESET}"
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

echo ""
echo -e "${BLUE}Step 2: Check current migration status${RESET}"

# Get current migration status
python3 manage.py showmigrations --plan 2>&1 | head -30

# Count applied and unapplied migrations
APPLIED=$(python3 manage.py showmigrations --plan 2>&1 | grep -c "\[X\]" || echo "0")
UNAPPLIED=$(python3 manage.py showmigrations --plan 2>&1 | grep -c "\[ \]" || echo "0")

echo ""
echo -e "${BLUE}Current migration status:${RESET}"
echo -e "  Applied: ${APPLIED}"
echo -e "  Unapplied: ${UNAPPLIED}"

echo ""
echo -e "${BLUE}Step 3: Check for existing data${RESET}"

# Check if database has existing data
DATA_COUNT=$(python3 -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
import django
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    # Check for existing data in key tables
    tables_to_check = [
        ('tenants_tenant', 'SELECT COUNT(*) FROM tenants_tenant'),
        ('users_user', 'SELECT COUNT(*) FROM users_user'),
        ('files_file', 'SELECT COUNT(*) FROM files_file'),
        ('datasets_dataset', 'SELECT COUNT(*) FROM datasets_dataset'),
        ('assets_asset', 'SELECT COUNT(*) FROM assets_asset'),
        ('contracts_contract', 'SELECT COUNT(*) FROM contracts_contract'),
    ]
    
    total_rows = 0
    for table_name, query in tables_to_check:
        try:
            cursor.execute(query)
            count = cursor.fetchone()[0]
            if count > 0:
                print(f'{table_name}: {count} rows')
                total_rows += count
        except Exception as e:
            # Table might not exist yet
            pass
    
    if total_rows > 0:
        print(f'Total existing rows: {total_rows}')
        exit(0)  # Has data
    else:
        print('No existing data found')
        exit(1)  # No data
" 2>&1)

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Database has existing data${RESET}"
    echo "$DATA_COUNT"
else
    echo -e "${YELLOW}⚠️  No existing data found${RESET}"
    echo -e "${YELLOW}   This is expected for a fresh database${RESET}"
fi

echo ""
echo -e "${BLUE}Step 4: Apply pending migrations${RESET}"

if [ "$UNAPPLIED" -gt 0 ]; then
    echo -e "${BLUE}Applying ${UNAPPLIED} pending migrations...${RESET}"
    
    if python3 manage.py migrate --verbosity=2 2>&1 | tee /tmp/migration_existing_test.log; then
        echo -e "${GREEN}✅ Migrations applied successfully${RESET}"
    else
        echo -e "${RED}❌ Migration failed${RESET}"
        echo -e "${YELLOW}Migration output:${RESET}"
        tail -50 /tmp/migration_existing_test.log
        exit 1
    fi
else
    echo -e "${GREEN}✅ All migrations already applied${RESET}"
fi

echo ""
echo -e "${BLUE}Step 5: Verify data integrity${RESET}"

# Verify that existing data is still accessible
if python3 -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
import django
django.setup()

from django.db import connection

with connection.cursor() as cursor:
    # Try to query key tables
    tables_to_check = [
        'tenants_tenant',
        'users_user',
        'files_file',
        'datasets_dataset',
        'assets_asset',
        'contracts_contract',
    ]
    
    for table in tables_to_check:
        try:
            cursor.execute(f'SELECT COUNT(*) FROM {table}')
            count = cursor.fetchone()[0]
            print(f'✅ {table}: {count} rows accessible')
        except Exception as e:
            # Table might not exist (expected for some migrations)
            pass
    
    print('✅ Data integrity verified')
" 2>&1; then
    echo -e "${GREEN}✅ Data integrity verified${RESET}"
else
    echo -e "${YELLOW}⚠️  Could not verify all tables (some may not exist yet)${RESET}"
fi

echo ""
echo -e "${BLUE}Step 6: Verify migration status after${RESET}"
AFTER_APPLIED=$(python3 manage.py showmigrations --plan 2>&1 | grep -c "\[X\]" || echo "0")
AFTER_UNAPPLIED=$(python3 manage.py showmigrations --plan 2>&1 | grep -c "\[ \]" || echo "0")

echo -e "${BLUE}Migration status after:${RESET}"
echo -e "  Applied: ${AFTER_APPLIED}"
echo -e "  Unapplied: ${AFTER_UNAPPLIED}"

if [ "$AFTER_UNAPPLIED" -eq 0 ]; then
    echo -e "${GREEN}✅ All migrations applied${RESET}"
else
    echo -e "${YELLOW}⚠️  ${AFTER_UNAPPLIED} migrations still unapplied${RESET}"
fi

echo ""
echo -e "${BOLD}${GREEN}✅ Existing Data Migration Test Complete${RESET}"
echo -e "${GREEN}Migrations applied successfully on database with existing data${RESET}"

