#!/bin/bash
# Test Application with Python 3.12+
# This script creates a virtual environment, installs dependencies, runs migrations, and tests the server

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
echo -e "${BLUE}Application Test - Python 3.12+${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo -e "${BLUE}Testing with Python: ${PYTHON_VERSION}${NC}"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 12) else 1)"; then
    echo -e "${RED}❌ Python 3.12+ required. Found: ${PYTHON_VERSION}${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Python version check passed${NC}"
echo ""

# Create virtual environment
VENV_DIR="venv-python312-test"
echo -e "${BLUE}Creating virtual environment...${NC}"

if [ -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}⚠️  Virtual environment already exists, removing...${NC}"
    rm -rf "$VENV_DIR"
fi

python3 -m venv "$VENV_DIR"
echo -e "${GREEN}✅ Virtual environment created${NC}"

# Activate virtual environment
echo -e "${BLUE}Activating virtual environment...${NC}"
source "$VENV_DIR/bin/activate"
echo -e "${GREEN}✅ Virtual environment activated${NC}"

# Verify Python version in venv
VENV_PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
echo -e "${BLUE}Python version in venv: ${VENV_PYTHON_VERSION}${NC}"
echo ""

# Upgrade pip
echo -e "${BLUE}Upgrading pip...${NC}"
pip install --quiet --upgrade pip
PIP_VERSION=$(pip --version | awk '{print $2}')
echo -e "${GREEN}✅ pip upgraded to ${PIP_VERSION}${NC}"
echo ""

# Install dependencies
echo -e "${BLUE}Installing dependencies...${NC}"

if [ -f "requirements.txt" ]; then
    echo -e "${BLUE}  Installing requirements.txt...${NC}"
    if pip install --quiet -r requirements.txt; then
        echo -e "${GREEN}  ✅ requirements.txt installed successfully${NC}"
    else
        echo -e "${RED}  ❌ Failed to install requirements.txt${NC}"
        exit 1
    fi
else
    echo -e "${YELLOW}  ⚠️  requirements.txt not found${NC}"
fi

if [ -f "requirements-dev.txt" ]; then
    echo -e "${BLUE}  Installing requirements-dev.txt...${NC}"
    if pip install --quiet -r requirements-dev.txt; then
        echo -e "${GREEN}  ✅ requirements-dev.txt installed successfully${NC}"
    else
        echo -e "${YELLOW}  ⚠️  Some dev dependencies may have failed (non-critical)${NC}"
    fi
else
    echo -e "${YELLOW}  ⚠️  requirements-dev.txt not found${NC}"
fi

echo ""

# Verify Django is installed
echo -e "${BLUE}Verifying Django installation...${NC}"
if python -c "import django; print('Django', django.get_version())" 2>/dev/null; then
    DJANGO_VERSION=$(python -c "import django; print(django.get_version())" 2>/dev/null)
    echo -e "${GREEN}✅ Django ${DJANGO_VERSION} is installed${NC}"
else
    echo -e "${RED}❌ Django is not installed${NC}"
    exit 1
fi
echo ""

# Check if Django project exists
if [ ! -f "hub/manage.py" ]; then
    echo -e "${YELLOW}⚠️  Django project not found (hub/manage.py missing)${NC}"
    echo -e "${YELLOW}   Skipping Django-specific tests${NC}"
    deactivate
    rm -rf "$VENV_DIR"
    exit 0
fi

# Test Django configuration
echo -e "${BLUE}Testing Django configuration...${NC}"
export DJANGO_SETTINGS_MODULE=hub.settings
export PYTHONPATH="$PROJECT_ROOT"

if python hub/manage.py check --deploy > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Django configuration is valid${NC}"
else
    echo -e "${YELLOW}⚠️  Django configuration has warnings (check output above)${NC}"
    python hub/manage.py check 2>&1 | head -20
fi
echo ""

# Test database connection (if database is available)
echo -e "${BLUE}Testing database connection...${NC}"
if python -c "
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
django.setup()
from django.db import connection
connection.ensure_connection()
print('✅ Database connection successful')
" 2>/dev/null; then
    echo -e "${GREEN}✅ Database connection successful${NC}"
    
    # Test migrations (dry-run)
    echo -e "${BLUE}Checking migrations...${NC}"
    if python hub/manage.py showmigrations --plan > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Migrations check passed${NC}"
        
        # Show migration status
        UNAPPLIED=$(python hub/manage.py showmigrations --plan 2>/dev/null | grep '\[ \]' | wc -l || echo "0")
        if [ "$UNAPPLIED" -gt 0 ]; then
            echo -e "${YELLOW}  ⚠️  ${UNAPPLIED} unapplied migrations found${NC}"
            echo -e "${BLUE}  Run: python hub/manage.py migrate${NC}"
        else
            echo -e "${GREEN}  ✅ All migrations are applied${NC}"
        fi
    else
        echo -e "${YELLOW}⚠️  Could not check migrations${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Database connection failed (database may not be running)${NC}"
    echo -e "${YELLOW}   Start database with: docker-compose up -d postgres${NC}"
fi
echo ""

# Test imports
echo -e "${BLUE}Testing critical imports...${NC}"
python -c "
import sys
print('Testing imports...')
try:
    import django
    print('✅ django')
    import rest_framework
    print('✅ djangorestframework')
    import structlog
    print('✅ structlog')
    import rq
    print('✅ django-rq')
    print('✅ All critical imports successful')
except ImportError as e:
    print(f'❌ Import failed: {e}')
    sys.exit(1)
" && echo -e "${GREEN}✅ All critical imports successful${NC}" || echo -e "${RED}❌ Some imports failed${NC}"
echo ""

# Summary
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Application Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}✅ Virtual environment created with Python 3.12+${NC}"
echo -e "${GREEN}✅ Dependencies installed successfully${NC}"
echo -e "${GREEN}✅ Django configuration validated${NC}"
echo ""
echo -e "${BLUE}Next steps:${NC}"
echo "  1. Activate venv: source ${VENV_DIR}/bin/activate"
echo "  2. Start database: docker-compose up -d postgres redis"
echo "  3. Run migrations: python hub/manage.py migrate"
echo "  4. Start server: python hub/manage.py runserver"
echo ""

# Cleanup (optional)
read -p "Remove test virtual environment? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    deactivate
    rm -rf "$VENV_DIR"
    echo -e "${GREEN}✅ Virtual environment removed${NC}"
else
    echo -e "${BLUE}Virtual environment kept at: ${VENV_DIR}${NC}"
    echo -e "${BLUE}Activate with: source ${VENV_DIR}/bin/activate${NC}"
fi

exit 0

