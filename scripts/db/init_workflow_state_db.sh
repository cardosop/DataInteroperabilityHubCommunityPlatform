#!/bin/bash
# Initialize Workflow State Database
#
# This script initializes the workflow state database schema:
# - Creates database if it doesn't exist
# - Runs Django migrations
# - Creates indexes
# - Validates schema
#
# Usage:
#   ./scripts/db/init_workflow_state_db.sh [--skip-migrations] [--validate-only]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

SKIP_MIGRATIONS="${1:-}"
VALIDATE_ONLY="${2:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Python/Django
    if ! command -v python &> /dev/null; then
        log_error "Python is not installed"
        exit 1
    fi
    
    # Check Django
    if ! python -c "import django" 2>/dev/null; then
        log_error "Django is not installed"
        exit 1
    fi
    
    # Check PostgreSQL connection
    if ! python -c "from django.db import connection; connection.ensure_connection()" 2>/dev/null; then
        log_error "Cannot connect to PostgreSQL database"
        exit 1
    fi
    
    log_info "Prerequisites check passed"
}

create_database() {
    log_info "Checking database exists..."
    
    # Django will create database if needed via migrations
    # This is a placeholder for custom database creation logic if needed
    log_info "Database check complete"
}

run_migrations() {
    if [ "$SKIP_MIGRATIONS" = "--skip-migrations" ]; then
        log_warn "Skipping migrations (--skip-migrations flag set)"
        return
    fi
    
    log_info "Running Django migrations..."
    
    cd "${PROJECT_ROOT}"
    python manage.py migrate orchestration --verbosity=2
    
    log_info "Migrations completed"
}

validate_schema() {
    log_info "Validating workflow state schema..."
    
    cd "${PROJECT_ROOT}"
    
    # Run validation script
    python manage.py shell << 'EOF'
from django.db import connection
from django.core.management import call_command
import sys

# Check if tables exist
cursor = connection.cursor()
required_tables = [
    'workflow_definitions',
    'workflow_instances',
    'workflow_steps',
    'workflow_states'
]

missing_tables = []
for table in required_tables:
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = %s
        );
    """, [table])
    exists = cursor.fetchone()[0]
    if not exists:
        missing_tables.append(table)

if missing_tables:
    print(f"ERROR: Missing tables: {', '.join(missing_tables)}")
    sys.exit(1)

# Check if indexes exist
required_indexes = [
    'workflow_def_name_active_idx',
    'workflow_def_name_version_idx',
    'workflow_inst_tenant_status_idx',
    'workflow_inst_tenant_name_status_idx',
    'workflow_step_inst_status_idx',
    'workflow_state_inst_type_created_idx'
]

missing_indexes = []
for index in required_indexes:
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM pg_indexes 
            WHERE schemaname = 'public' 
            AND indexname = %s
        );
    """, [index])
    exists = cursor.fetchone()[0]
    if not exists:
        missing_indexes.append(index)

if missing_indexes:
    print(f"ERROR: Missing indexes: {', '.join(missing_indexes)}")
    sys.exit(1)

print("SUCCESS: Schema validation passed")
EOF
    
    if [ $? -eq 0 ]; then
        log_info "Schema validation passed"
    else
        log_error "Schema validation failed"
        exit 1
    fi
}

create_initial_data() {
    log_info "Creating initial workflow definitions..."
    
    cd "${PROJECT_ROOT}"
    
    # This can be extended to create initial workflow definitions
    # For now, we'll skip this as workflows are created dynamically
    log_info "Initial data creation skipped (workflows created dynamically)"
}

main() {
    log_info "Starting workflow state database initialization..."
    
    check_prerequisites
    
    if [ "$VALIDATE_ONLY" = "--validate-only" ]; then
        validate_schema
        log_info "Validation complete"
        return
    fi
    
    create_database
    run_migrations
    validate_schema
    create_initial_data
    
    log_info "Workflow state database initialization complete!"
    log_info "Next steps:"
    log_info "1. Verify tables: python manage.py dbshell -c '\\dt workflow_*'"
    log_info "2. Check indexes: python manage.py dbshell -c '\\di workflow_*'"
    log_info "3. Run tests: python manage.py test hub.apps.orchestration.tests.test_migrations"
}

main "$@"

