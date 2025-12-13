#!/bin/bash
# Verify Tenant Migrations Fix
#
# This script verifies that the tenant migration issue has been fixed.
# Run this after fixing the duplicate migration number issue.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

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

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

check_migration_files() {
    log_info "Checking migration files..."
    
    cd "${PROJECT_ROOT}/hub/apps/tenants/migrations"
    
    # Check for duplicate 0002
    if [ -f "0002_add_sso_config.py" ]; then
        log_error "Found duplicate migration: 0002_add_sso_config.py (should be 0004)"
        return 1
    fi
    
    # Check for correct 0004
    if [ ! -f "0004_add_sso_config.py" ]; then
        log_error "Missing migration: 0004_add_sso_config.py"
        return 1
    fi
    
    # Check migration chain
    local files=(
        "0001_initial.py"
        "0002_add_tenant_config.py"
        "0003_rename_tenant_configs_tenant_idx_tenant_conf_tenant__37e737_idx_and_more.py"
        "0004_add_sso_config.py"
    )
    
    for file in "${files[@]}"; do
        if [ ! -f "$file" ]; then
            log_error "Missing migration file: $file"
            return 1
        fi
    done
    
    log_success "Migration files are correct"
    return 0
}

check_migration_dependencies() {
    log_info "Checking migration dependencies..."
    
    cd "${PROJECT_ROOT}/hub/apps/tenants/migrations"
    
    # Check 0002 depends on 0001
    if ! grep -q "('tenants', '0001_initial')" "0002_add_tenant_config.py"; then
        log_error "0002_add_tenant_config.py should depend on 0001_initial"
        return 1
    fi
    
    # Check 0003 depends on 0002
    if ! grep -q "('tenants', '0002_add_tenant_config')" "0003_rename_tenant_configs_tenant_idx_tenant_conf_tenant__37e737_idx_and_more.py"; then
        log_error "0003 migration should depend on 0002_add_tenant_config"
        return 1
    fi
    
    # Check 0004 depends on 0003
    if ! grep -q "('tenants', '0003_rename_tenant_configs" "0004_add_sso_config.py"; then
        log_error "0004_add_sso_config.py should depend on 0003"
        return 1
    fi
    
    log_success "Migration dependencies are correct"
    return 0
}

check_django_available() {
    log_info "Checking if Django is available..."
    
    cd "${PROJECT_ROOT}/hub"
    
    if command -v python3 &> /dev/null; then
        if python3 -c "import django" 2>/dev/null; then
            log_success "Django is available"
            return 0
        fi
    fi
    
    log_warn "Django is not available (virtual environment may not be activated)"
    log_warn "Skipping Django-specific checks"
    return 2
}

check_migration_status() {
    log_info "Checking migration status..."
    
    cd "${PROJECT_ROOT}/hub"
    
    if python3 manage.py showmigrations tenants 2>&1 | grep -q "0002_add_sso_config"; then
        log_error "Migration system still sees 0002_add_sso_config (may need to clear cache)"
        return 1
    fi
    
    if python3 manage.py showmigrations tenants 2>&1 | grep -q "0004_add_sso_config"; then
        log_success "Migration 0004_add_sso_config is recognized"
    else
        log_warn "Migration 0004_add_sso_config not found in migration status"
    fi
    
    return 0
}

check_database_state() {
    log_info "Checking database state..."
    
    cd "${PROJECT_ROOT}/hub"
    
    # Check if sso_config column exists
    local result=$(python3 manage.py dbshell -c "SELECT column_name FROM information_schema.columns WHERE table_name = 'tenant_configs' AND column_name = 'sso_config';" 2>&1 | grep -c "sso_config" || echo "0")
    
    if [ "$result" -gt 0 ]; then
        log_info "sso_config column exists in database"
        log_info "You may need to run: python manage.py migrate tenants 0004_add_sso_config --fake"
        return 0
    else
        log_info "sso_config column does NOT exist in database"
        log_info "You should run: python manage.py migrate tenants 0004_add_sso_config"
        return 0
    fi
}

check_makemigrations() {
    log_info "Checking for migration conflicts..."
    
    cd "${PROJECT_ROOT}/hub"
    
    local output=$(python3 manage.py makemigrations --dry-run 2>&1)
    
    if echo "$output" | grep -qi "conflict\|error\|duplicate"; then
        log_error "Found migration conflicts:"
        echo "$output" | grep -i "conflict\|error\|duplicate"
        return 1
    fi
    
    log_success "No migration conflicts detected"
    return 0
}

main() {
    log_info "Verifying tenant migration fix..."
    echo ""
    
    local errors=0
    
    # Check migration files
    if ! check_migration_files; then
        ((errors++))
    fi
    
    # Check dependencies
    if ! check_migration_dependencies; then
        ((errors++))
    fi
    
    # Check Django availability
    local django_status=0
    check_django_available || django_status=$?
    
    if [ $django_status -eq 0 ]; then
        # Django is available, run Django-specific checks
        if ! check_migration_status; then
            ((errors++))
        fi
        
        if ! check_database_state; then
            ((errors++))
        fi
        
        if ! check_makemigrations; then
            ((errors++))
        fi
    else
        log_warn "Skipping Django-specific checks (Django not available)"
    fi
    
    echo ""
    if [ $errors -eq 0 ]; then
        log_success "All checks passed! Migration fix is correct."
        echo ""
        log_info "Next steps:"
        echo "  1. Activate your virtual environment"
        echo "  2. Run: python manage.py showmigrations tenants"
        echo "  3. Run: python manage.py migrate tenants 0004_add_sso_config [--fake]"
        echo "  4. Run: python manage.py makemigrations --dry-run"
        echo "  5. Run: python manage.py test hub.apps.tenants"
        return 0
    else
        log_error "Found $errors issue(s). Please review above."
        return 1
    fi
}

main "$@"

