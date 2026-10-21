#!/bin/bash
# Script to clean/reset the test database for pytest

set -e

echo "Resetting test database..."

# Get database name from settings
DB_NAME=$(python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings'); import django; django.setup(); from django.conf import settings; print(settings.DATABASES['default']['NAME'])")
TEST_DB_NAME="${DB_NAME}_test"

echo "Test database name: $TEST_DB_NAME"

# Get database connection info
DB_USER=$(python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings'); import django; django.setup(); from django.conf import settings; print(settings.DATABASES['default']['USER'])")
DB_HOST=$(python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings'); import django; django.setup(); from django.conf import settings; print(settings.DATABASES['default'].get('HOST', 'localhost'))")
DB_PORT=$(python -c "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hub.settings'); import django; django.setup(); from django.conf import settings; print(settings.DATABASES['default'].get('PORT', '5432'))")

echo "Connecting to PostgreSQL as $DB_USER@$DB_HOST:$DB_PORT"

# Drop test database if it exists
echo "Dropping test database if it exists..."
PGPASSWORD="${PGPASSWORD:-}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -c "DROP DATABASE IF EXISTS \"$TEST_DB_NAME\";" || true

# Also try with template1 as fallback
PGPASSWORD="${PGPASSWORD:-}" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d template1 -c "DROP DATABASE IF EXISTS \"$TEST_DB_NAME\";" || true

echo "Test database reset complete!"
echo "You can now run: pytest hub/apps/orchestration/workflows/tests/test_contract_creation.py -v"

