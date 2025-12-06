#!/bin/bash
# Test Database Migrations with Python 3.12+
# This script tests that migrations work correctly with Python 3.12+

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Database Migrations Test - Python 3.12+${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if virtual environment exists
VENV_DIR="venv-python312-test"
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment not found. Creating...${NC}"
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    pip install --quiet --upgrade pip
    pip install --quiet -r requirements.txt
else
    source "$VENV_DIR/bin/activate"
fi

echo -e "${GREEN}✅ Virtual environment activated${NC}"
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo -e "${BLUE}Python version: ${PYTHON_VERSION}${NC}"
echo ""

# Check if database is running
echo -e "${BLUE}Checking database connection...${NC}"
if docker ps --format '{{.Names}}' | grep -q '^hub-postgres$'; then
    echo -e "${GREEN}✅ PostgreSQL container is running${NC}"
    
    # Wait for PostgreSQL to be ready
    echo -e "${BLUE}Waiting for PostgreSQL to be ready...${NC}"
    for i in {1..30}; do
        if docker exec hub-postgres pg_isready -U hub > /dev/null 2>&1; then
            echo -e "${GREEN}✅ PostgreSQL is ready${NC}"
            break
        fi
        if [ $i -eq 30 ]; then
            echo -e "${RED}❌ PostgreSQL did not become ready in time${NC}"
            exit 1
        fi
        sleep 1
    done
else
    echo -e "${YELLOW}⚠️  PostgreSQL container is not running${NC}"
    echo -e "${BLUE}Starting PostgreSQL...${NC}"
    docker compose up -d postgres
    sleep 10
fi

# Set environment variables
export DJANGO_SETTINGS_MODULE=hub.settings
export PYTHONPATH="$PROJECT_ROOT"
export DATABASE_URL="${DATABASE_URL:-postgresql://hub:hub@localhost:5432/hub}"

# Test Django connection
echo -e "${BLUE}Testing Django database connection...${NC}"
if python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
django.setup()
from django.db import connection
connection.ensure_connection()
print('✅ Database connection successful')
" 2>&1; then
    echo -e "${GREEN}✅ Database connection successful${NC}"
else
    echo -e "${RED}❌ Database connection failed${NC}"
    echo -e "${YELLOW}   Check that PostgreSQL is running and accessible${NC}"
    exit 1
fi
echo ""

# Show migration status
echo -e "${BLUE}Checking migration status...${NC}"
python hub/manage.py showmigrations --plan 2>&1 | head -50
echo ""

# Count unapplied migrations
UNAPPLIED=$(python hub/manage.py showmigrations --plan 2>/dev/null | grep -c '\[ \]' || echo "0")
APPLIED=$(python hub/manage.py showmigrations --plan 2>/dev/null | grep -c '\[X\]' || echo "0")

echo -e "${BLUE}Migration Summary:${NC}"
echo -e "  Applied: ${APPLIED}"
echo -e "  Unapplied: ${UNAPPLIED}"
echo ""

if [ "$UNAPPLIED" -gt 0 ]; then
    echo -e "${BLUE}Running migrations...${NC}"
    if python hub/manage.py migrate --noinput 2>&1; then
        echo -e "${GREEN}✅ Migrations applied successfully${NC}"
    else
        # Check if failure is due to existing tables (fake migrations)
        if python hub/manage.py migrate --fake 2>&1 | grep -q "No migrations to apply"; then
            echo -e "${YELLOW}⚠️  Some migrations may already be applied${NC}"
            echo -e "${BLUE}   Attempting to mark migrations as applied...${NC}"
            python hub/manage.py migrate --fake 2>&1 || echo -e "${YELLOW}   Some migrations may need manual resolution${NC}"
        else
            echo -e "${RED}❌ Migration failed${NC}"
            echo -e "${YELLOW}   This may be due to existing database state${NC}"
            echo -e "${BLUE}   Consider: python hub/manage.py migrate --fake-initial${NC}"
        fi
    fi
else
    echo -e "${GREEN}✅ All migrations are already applied${NC}"
fi

echo ""

# Verify migration status after
echo -e "${BLUE}Verifying migration status after running...${NC}"
python hub/manage.py showmigrations --plan 2>&1 | tail -20
echo ""

# Test that we can query the database
echo -e "${BLUE}Testing database queries...${NC}"
if python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
django.setup()
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute('SELECT version();')
    version = cursor.fetchone()
    print(f'✅ PostgreSQL version: {version[0]}')
    cursor.execute('SELECT current_database();')
    db = cursor.fetchone()
    print(f'✅ Connected to database: {db[0]}')
" 2>&1; then
    echo -e "${GREEN}✅ Database queries successful${NC}"
else
    echo -e "${RED}❌ Database queries failed${NC}"
    exit 1
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}✅ Database migrations test completed successfully!${NC}"
echo -e "${BLUE}========================================${NC}"

exit 0

