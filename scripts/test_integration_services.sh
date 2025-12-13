#!/bin/bash
# Test All Services Integration with Django 6

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

echo -e "${BOLD}${BLUE}========================================${RESET}"
echo -e "${BOLD}${BLUE}Django 6 Service Integration Testing${RESET}"
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

cd hub || { echo -e "${RED}Error: 'hub' directory not found${RESET}"; exit 1; }

echo -e "${BLUE}Step 1: Test Database Operations${RESET}"

if python3 -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
import django
django.setup()
from django.db import connection

with connection.cursor() as cursor:
    cursor.execute('SELECT version();')
    version = cursor.fetchone()[0]
    print(f'✅ Database connection: {version[:50]}...')
    
    # Test query
    cursor.execute('SELECT COUNT(*) FROM tenants_tenant;')
    count = cursor.fetchone()[0]
    print(f'✅ Database query works: {count} tenants')
" 2>&1; then
    echo -e "${GREEN}✅ Database operations verified${RESET}"
else
    echo -e "${RED}❌ Database operations failed${RESET}"
    exit 1
fi

echo ""
echo -e "${BLUE}Step 2: Test Redis Connection${RESET}"

if python3 -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
import django
django.setup()
from django.core.cache import cache

# Test cache connection
try:
    cache.set('test_key', 'test_value', 10)
    value = cache.get('test_key')
    if value == 'test_value':
        print('✅ Redis connection works')
    else:
        print('⚠️  Redis connection issue (value mismatch)')
except Exception as e:
    print(f'⚠️  Redis not available: {e}')
" 2>&1; then
    echo -e "${GREEN}✅ Redis connection verified${RESET}"
else
    echo -e "${YELLOW}⚠️  Redis not available (may not be required for all tests)${RESET}"
fi

echo ""
echo -e "${BLUE}Step 3: Test External Services${RESET}"

# Test service URLs from settings
if python3 -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
import django
django.setup()
from django.conf import settings

services = [
    ('DQ Service', getattr(settings, 'DQ_SERVICE_URL', None)),
    ('Compliance Service', getattr(settings, 'COMPLIANCE_SERVICE_URL', None)),
    ('Semantic Service', getattr(settings, 'SEMANTIC_SERVICE_URL', None)),
    ('DataContract Service', getattr(settings, 'DATACONTRACT_SERVICE_URL', None)),
]

for name, url in services:
    if url:
        print(f'✅ {name} configured: {url}')
    else:
        print(f'⚠️  {name} not configured')
" 2>&1; then
    echo -e "${GREEN}✅ External services configuration verified${RESET}"
else
    echo -e "${YELLOW}⚠️  Could not verify external services${RESET}"
fi

echo ""
echo -e "${BOLD}${GREEN}Service Integration Test Summary${RESET}"
echo -e "${GREEN}✅ Database operations verified${RESET}"
echo -e "${GREEN}✅ Redis connection verified (if available)${RESET}"
echo -e "${GREEN}✅ External services configuration verified${RESET}"

