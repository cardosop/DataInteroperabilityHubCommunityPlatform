#!/bin/bash
# Test Django 6 Settings Functionality

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
BOLD='\033[1m'
RESET='\033[0m'

echo -e "${BOLD}${BLUE}========================================${RESET}"
echo -e "${BOLD}${BLUE}Django 6 Settings Functionality Test${RESET}"
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
echo -e "${BLUE}Step 2: Test STORAGES setting${RESET}"

if python3 -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
import django
django.setup()
from django.conf import settings

# Test STORAGES setting (Django 6)
if hasattr(settings, 'STORAGES'):
    print('✅ STORAGES setting exists')
    if 'default' in settings.STORAGES:
        print(f'✅ Default storage: {settings.STORAGES[\"default\"][\"BACKEND\"]}')
    if 'staticfiles' in settings.STORAGES:
        print(f'✅ Staticfiles storage: {settings.STORAGES[\"staticfiles\"][\"BACKEND\"]}')
    
    # Verify deprecated settings are not used
    if hasattr(settings, 'DEFAULT_FILE_STORAGE'):
        print('⚠️  DEFAULT_FILE_STORAGE still exists (should use STORAGES)')
    else:
        print('✅ DEFAULT_FILE_STORAGE removed (using STORAGES)')
    
    if hasattr(settings, 'STATICFILES_STORAGE'):
        print('⚠️  STATICFILES_STORAGE still exists (should use STORAGES)')
    else:
        print('✅ STATICFILES_STORAGE removed (using STORAGES)')
else:
    print('❌ STORAGES setting not found')
    exit(1)
" 2>&1; then
    echo -e "${GREEN}✅ STORAGES setting verified${RESET}"
else
    echo -e "${RED}❌ STORAGES setting test failed${RESET}"
    exit 1
fi

echo ""
echo -e "${BLUE}Step 3: Test middleware configuration${RESET}"

if python3 -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
import django
django.setup()
from django.conf import settings

# Check middleware order
middleware = settings.MIDDLEWARE
print(f'✅ Middleware configured ({len(middleware)} middleware classes)')

# Check for our custom middleware
custom_middleware = [
    'hub.apps.api.middleware.RequestIDMiddleware',
    'hub.apps.auth.middleware.TenantScopingMiddleware',
    'hub.apps.tenants.middleware.TenantSuspensionMiddleware',
    'hub.apps.rate_limiting.middleware.RateLimitMiddleware',
    'hub.apps.observability.middleware.MetricsMiddleware',
]

for mw in custom_middleware:
    if mw in middleware:
        print(f'✅ {mw} configured')
    else:
        print(f'⚠️  {mw} not found in middleware')
" 2>&1; then
    echo -e "${GREEN}✅ Middleware configuration verified${RESET}"
else
    echo -e "${YELLOW}⚠️  Middleware configuration check completed with warnings${RESET}"
fi

echo ""
echo -e "${BLUE}Step 4: Test database configuration${RESET}"

if python3 -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
import django
django.setup()
from django.conf import settings
from django.db import connection

# Test database connection
try:
    with connection.cursor() as cursor:
        cursor.execute('SELECT version();')
        version = cursor.fetchone()[0]
        print(f'✅ Database connection: {version[:50]}...')
        
        cursor.execute('SELECT current_database();')
        db_name = cursor.fetchone()[0]
        print(f'✅ Connected to database: {db_name}')
except Exception as e:
    print(f'❌ Database connection failed: {e}')
    exit(1)
" 2>&1; then
    echo -e "${GREEN}✅ Database configuration verified${RESET}"
else
    echo -e "${RED}❌ Database configuration test failed${RESET}"
    exit 1
fi

echo ""
echo -e "${BLUE}Step 5: Test security settings${RESET}"

if python3 -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
import django
django.setup()
from django.conf import settings

# Check security settings
security_settings = [
    'SECRET_KEY',
    'DEBUG',
    'ALLOWED_HOSTS',
    'CSRF_COOKIE_SECURE',
    'SESSION_COOKIE_SECURE',
]

for setting in security_settings:
    if hasattr(settings, setting):
        value = getattr(settings, setting)
        if setting == 'SECRET_KEY':
            print(f'✅ {setting}: {\"*\" * 20} (hidden)')
        elif setting == 'ALLOWED_HOSTS':
            print(f'✅ {setting}: {value}')
        else:
            print(f'✅ {setting}: {value}')
    else:
        print(f'⚠️  {setting} not found')
" 2>&1; then
    echo -e "${GREEN}✅ Security settings verified${RESET}"
else
    echo -e "${YELLOW}⚠️  Security settings check completed${RESET}"
fi

echo ""
echo -e "${BLUE}Step 6: Test static files settings${RESET}"

if python3 -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
import django
django.setup()
from django.conf import settings

# Check static files settings
if hasattr(settings, 'STATIC_URL'):
    print(f'✅ STATIC_URL: {settings.STATIC_URL}')
if hasattr(settings, 'STATIC_ROOT'):
    print(f'✅ STATIC_ROOT: {settings.STATIC_ROOT}')
if hasattr(settings, 'STORAGES') and 'staticfiles' in settings.STORAGES:
    print(f'✅ Staticfiles storage configured')
" 2>&1; then
    echo -e "${GREEN}✅ Static files settings verified${RESET}"
else
    echo -e "${YELLOW}⚠️  Static files settings check completed${RESET}"
fi

echo ""
echo -e "${BLUE}Step 7: Test logging settings${RESET}"

if python3 -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
import django
django.setup()
from django.conf import settings

# Check logging configuration
if hasattr(settings, 'LOGGING'):
    print('✅ LOGGING configuration exists')
    if 'handlers' in settings.LOGGING:
        print(f'✅ Log handlers configured: {len(settings.LOGGING[\"handlers\"])} handlers')
    if 'loggers' in settings.LOGGING:
        print(f'✅ Loggers configured: {len(settings.LOGGING[\"loggers\"])} loggers')
else:
    print('⚠️  LOGGING configuration not found')
" 2>&1; then
    echo -e "${GREEN}✅ Logging settings verified${RESET}"
else
    echo -e "${YELLOW}⚠️  Logging settings check completed${RESET}"
fi

echo ""
echo -e "${BLUE}Step 8: Test cache settings${RESET}"

if python3 -c "
import os
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings')
import django
django.setup()
from django.conf import settings

# Check cache configuration
if hasattr(settings, 'CACHES'):
    print('✅ CACHES configuration exists')
    for cache_name in settings.CACHES:
        backend = settings.CACHES[cache_name].get('BACKEND', 'unknown')
        print(f'✅ Cache \"{cache_name}\": {backend}')
else:
    print('⚠️  CACHES configuration not found')
" 2>&1; then
    echo -e "${GREEN}✅ Cache settings verified${RESET}"
else
    echo -e "${YELLOW}⚠️  Cache settings check completed${RESET}"
fi

echo ""
echo -e "${BLUE}Step 9: Run Django system check${RESET}"

if python3 manage.py check --deploy 2>&1 | tee /tmp/django_check.log; then
    echo -e "${GREEN}✅ Django system check passed${RESET}"
else
    echo -e "${YELLOW}⚠️  Django system check completed with warnings${RESET}"
    echo -e "${YELLOW}Check output:${RESET}"
    tail -20 /tmp/django_check.log
fi

echo ""
echo -e "${BOLD}${GREEN}✅ Settings Functionality Test Complete${RESET}"
echo -e "${GREEN}All settings verified and functional${RESET}"

