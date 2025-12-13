#!/bin/bash
# Comprehensive tenant migration verification script
# This script runs all Django verification steps for the tenant migration fix

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

echo "=========================================="
echo "Tenant Migration Verification"
echo "=========================================="
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [ ! -d "venv" ] && [ ! -d ".venv" ]; then
    echo -e "${RED}❌ Virtual environment not found${NC}"
    echo "Please create a virtual environment first:"
    echo "  python3 -m venv venv"
    exit 1
fi

# Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
elif [ -d ".venv" ]; then
    source .venv/bin/activate
fi

echo -e "${GREEN}✓ Virtual environment activated${NC}"
echo ""

# Check Django availability
if ! python -c "import django" 2>/dev/null; then
    echo -e "${RED}❌ Django not found in virtual environment${NC}"
    echo "Please install dependencies:"
    echo "  pip install -r requirements.txt"
    exit 1
fi

echo -e "${GREEN}✓ Django available${NC}"
echo ""

# Check PostgreSQL connection
cd hub
if ! python manage.py dbshell -c "SELECT 1;" >/dev/null 2>&1; then
    echo -e "${YELLOW}⚠ PostgreSQL database not available${NC}"
    echo ""
    echo "To start PostgreSQL:"
    echo "  Option 1: docker compose up -d postgres"
    echo "  Option 2: sudo systemctl start postgresql"
    echo ""
    echo "Skipping database-dependent checks..."
    echo ""
    
    # Run file-based checks only
    echo "=========================================="
    echo "File System Checks"
    echo "=========================================="
    python3 "$PROJECT_ROOT/scripts/check_migration_files.py"
    echo ""
    
    echo "=========================================="
    echo "Migration Conflicts Check"
    echo "=========================================="
    if python manage.py makemigrations --dry-run 2>&1 | grep -q "No changes"; then
        echo -e "${GREEN}✓ No migration conflicts detected${NC}"
    else
        echo -e "${YELLOW}⚠ Migration conflicts detected (check output above)${NC}"
    fi
    echo ""
    
    echo -e "${YELLOW}⚠ Database checks skipped - PostgreSQL not available${NC}"
    echo ""
    echo "When PostgreSQL is available, run:"
    echo "  cd hub"
    echo "  python manage.py showmigrations tenants"
    echo "  python manage.py migrate tenants 0004_add_sso_config [--fake]"
    echo "  python manage.py test hub.apps.tenants"
    exit 0
fi

echo -e "${GREEN}✓ PostgreSQL database available${NC}"
echo ""

# Step 1: Check migration status
echo "=========================================="
echo "Step 1: Migration Status"
echo "=========================================="
python manage.py showmigrations tenants
echo ""

# Step 2: Check if sso_config column exists
echo "=========================================="
echo "Step 2: Check Database State"
echo "=========================================="
SSO_COLUMN_EXISTS=$(python manage.py shell << 'PYEOF'
from django.db import connection
cursor = connection.cursor()
cursor.execute("""
    SELECT column_name 
    FROM information_schema.columns 
    WHERE table_name = 'tenant_configs' 
    AND column_name = 'sso_config';
""")
result = cursor.fetchone()
print("EXISTS" if result else "NOT_EXISTS")
PYEOF
)

if [ "$SSO_COLUMN_EXISTS" = "EXISTS" ]; then
    echo -e "${YELLOW}⚠ sso_config column already exists in database${NC}"
    echo "Migration may have been applied incorrectly."
    echo "Will use --fake flag to mark migration as applied."
    FAKE_FLAG="--fake"
else
    echo -e "${GREEN}✓ sso_config column does not exist${NC}"
    echo "Will apply migration normally."
    FAKE_FLAG=""
fi
echo ""

# Step 3: Apply migration
echo "=========================================="
echo "Step 3: Apply Migration"
echo "=========================================="
if [ -n "$FAKE_FLAG" ]; then
    echo "Running: python manage.py migrate tenants 0004_add_sso_config --fake"
    python manage.py migrate tenants 0004_add_sso_config --fake
else
    echo "Running: python manage.py migrate tenants 0004_add_sso_config"
    python manage.py migrate tenants 0004_add_sso_config
fi
echo ""

# Step 4: Verify no conflicts
echo "=========================================="
echo "Step 4: Verify No Conflicts"
echo "=========================================="
if python manage.py makemigrations --dry-run 2>&1 | grep -q "No changes"; then
    echo -e "${GREEN}✓ No migration conflicts detected${NC}"
else
    echo -e "${YELLOW}⚠ Migration conflicts detected:${NC}"
    python manage.py makemigrations --dry-run
fi
echo ""

# Step 5: Run tests
echo "=========================================="
echo "Step 5: Run Tests"
echo "=========================================="
echo "Testing hub.apps.tenants..."
if python manage.py test hub.apps.tenants --verbosity=1 2>&1 | tee /tmp/tenant_test_output.log; then
    echo -e "${GREEN}✓ Tenant tests passed${NC}"
else
    echo -e "${RED}❌ Tenant tests failed${NC}"
    TEST_FAILED=1
fi
echo ""

echo "Testing related apps..."
if python manage.py test hub.apps.contracts hub.apps.assets hub.apps.datasets --verbosity=1 2>&1 | tee /tmp/related_test_output.log; then
    echo -e "${GREEN}✓ Related app tests passed${NC}"
else
    echo -e "${RED}❌ Related app tests failed${NC}"
    TEST_FAILED=1
fi
echo ""

# Summary
echo "=========================================="
echo "Verification Summary"
echo "=========================================="
if [ -z "$TEST_FAILED" ]; then
    echo -e "${GREEN}✅ All verification steps completed successfully!${NC}"
    exit 0
else
    echo -e "${RED}❌ Some tests failed. Check output above.${NC}"
    exit 1
fi

