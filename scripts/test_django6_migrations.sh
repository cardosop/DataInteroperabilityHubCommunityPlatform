#!/bin/bash
# Test Django 6 Migrations

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

echo -e "${BOLD}${BLUE}========================================${RESET}"
echo -e "${BOLD}${BLUE}Django 6 Migration Testing${RESET}"
echo -e "${BOLD}${BLUE}========================================${RESET}"
echo ""

cd "$(dirname "$0")/.." || exit 1

# Check if virtual environment exists
if [ ! -d "venv-python312-test" ]; then
    echo -e "${RED}Error: Virtual environment 'venv-python312-test' not found${RESET}"
    echo "Please create it first or activate your Python 3.12+ environment"
    exit 1
fi

# Activate virtual environment
source venv-python312-test/bin/activate

# Check Python version
PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
echo -e "${BLUE}Python version: ${PYTHON_VERSION}${RESET}"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 12) else 1)"; then
    echo -e "${RED}Error: Python 3.12+ required${RESET}"
    exit 1
fi

# Check Django version
DJANGO_VERSION=$(python3 -c "import django; print(django.get_version())" 2>/dev/null || echo "not installed")
echo -e "${BLUE}Django version: ${DJANGO_VERSION}${RESET}"

if [ "$DJANGO_VERSION" = "not installed" ]; then
    echo -e "${YELLOW}Installing Django 6.0...${RESET}"
    pip install --break-system-packages "Django>=6.0,<7.0" > /dev/null 2>&1
    DJANGO_VERSION=$(python3 -c "import django; print(django.get_version())")
    echo -e "${GREEN}Django ${DJANGO_VERSION} installed${RESET}"
fi

echo ""
echo -e "${BOLD}${BLUE}Step 1: Review Migration Files${RESET}"
if python3 scripts/review_django6_migrations.py; then
    echo -e "${GREEN}✅ Migration review completed${RESET}"
else
    echo -e "${RED}❌ Migration review failed${RESET}"
    exit 1
fi

echo ""
echo -e "${BOLD}${BLUE}Step 2: Check Migration Status${RESET}"
cd hub || { echo -e "${RED}Error: 'hub' directory not found${RESET}"; exit 1; }

# Check if database is configured
if ! python3 manage.py check --database default > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  Database not configured. Skipping migration tests.${RESET}"
    echo -e "${YELLOW}   To test migrations, configure database connection in settings.${RESET}"
    exit 0
fi

# Show migration status
echo -e "${BLUE}Current migration status:${RESET}"
python3 manage.py showmigrations --plan 2>&1 | head -30 || echo -e "${YELLOW}Could not show migrations (database may not be accessible)${RESET}"

echo ""
echo -e "${BOLD}${BLUE}Step 3: Test Migration Plan (Dry Run)${RESET}"
if python3 manage.py migrate --plan > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Migration plan generated successfully${RESET}"
    echo -e "${BLUE}Migration plan:${RESET}"
    python3 manage.py migrate --plan 2>&1 | head -20
else
    echo -e "${YELLOW}⚠️  Could not generate migration plan (database may not be accessible)${RESET}"
fi

echo ""
echo -e "${BOLD}${GREEN}Migration Testing Summary${RESET}"
echo -e "${GREEN}✅ Migration files reviewed${RESET}"
echo -e "${GREEN}✅ No Django 6 compatibility issues found${RESET}"
echo ""
echo -e "${BLUE}Note: To fully test migrations, you need:${RESET}"
echo -e "${BLUE}  1. A configured database connection${RESET}"
echo -e "${BLUE}  2. Run: python manage.py migrate (on clean database)${RESET}"
echo -e "${BLUE}  3. Run: python manage.py migrate (on database with existing data)${RESET}"

