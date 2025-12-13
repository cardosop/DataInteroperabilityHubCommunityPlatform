#!/bin/bash
# Test Deployment Scripts
# Validates all deployment scripts for syntax and basic functionality

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_section() {
    echo -e "\n${BLUE}=== $1 ===${NC}\n"
}

# Track results
PASSED=0
FAILED=0
WARNINGS=0

test_script_syntax() {
    local script="$1"
    local name="$2"
    
    if [ ! -f "$script" ]; then
        log_error "Script not found: $script"
        ((FAILED++))
        return 1
    fi
    
    if bash -n "$script" 2>&1; then
        log_info "✓ $name: Syntax check passed"
        ((PASSED++))
        return 0
    else
        log_error "✗ $name: Syntax check failed"
        ((FAILED++))
        return 1
    fi
}

test_script_executable() {
    local script="$1"
    local name="$2"
    
    if [ -x "$script" ]; then
        log_info "✓ $name: Is executable"
        ((PASSED++))
        return 0
    else
        log_warn "⚠ $name: Not executable (will fix)"
        chmod +x "$script"
        log_info "✓ $name: Made executable"
        ((WARNINGS++))
        return 0
    fi
}

# Test all deployment scripts
log_section "Testing Deployment Scripts"

SCRIPTS=(
    "scripts/pre_deployment_checks.sh:Pre-Deployment Checks"
    "scripts/create_backup.sh:Backup Creation"
    "scripts/rollback.sh:Rollback"
    "scripts/run_migrations.sh:Database Migrations"
    "scripts/verify_deployment.sh:Deployment Verification"
    "scripts/run_comprehensive_tests.sh:Comprehensive Tests"
    "scripts/monitor_deployment.sh:Deployment Monitoring"
    "scripts/deploy-production.sh:Production Deployment"
)

for script_info in "${SCRIPTS[@]}"; do
    IFS=':' read -r script name <<< "$script_info"
    test_script_syntax "$script" "$name"
    test_script_executable "$script" "$name"
done

# Test existing scripts
log_section "Testing Existing Scripts"

EXISTING_SCRIPTS=(
    "scripts/deploy-staging.sh:Staging Deployment"
    "scripts/smoke-tests.sh:Smoke Tests"
)

for script_info in "${EXISTING_SCRIPTS[@]}"; do
    IFS=':' read -r script name <<< "$script_info"
    if [ -f "$script" ]; then
        test_script_syntax "$script" "$name"
        test_script_executable "$script" "$name"
    else
        log_warn "⚠ $name: Script not found (may be created later)"
        ((WARNINGS++))
    fi
done

# Summary
log_section "Test Summary"

echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo "Warnings: $WARNINGS"

if [ $FAILED -eq 0 ]; then
    log_info "All script syntax checks passed ✓"
    exit 0
else
    log_error "$FAILED script(s) failed syntax check"
    exit 1
fi

