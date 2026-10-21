#!/bin/bash
# Deployment Execution Script
# Executes deployment following the deployment plan

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

# Track deployment progress
DEPLOYMENT_LOG="deployment_logs/deployment_$(date +%Y%m%d_%H%M%S).log"
mkdir -p deployment_logs

log_to_file() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> "$DEPLOYMENT_LOG"
}

# Execute deployment step
execute_step() {
    local step_name="$1"
    local step_command="$2"
    local step_description="${3:-$step_name}"
    
    log_section "$step_name"
    log_to_file "Starting: $step_description"
    
    if eval "$step_command" 2>&1 | tee -a "$DEPLOYMENT_LOG"; then
        log_info "✓ $step_description completed"
        log_to_file "Completed: $step_description"
        return 0
    else
        log_error "✗ $step_description failed"
        log_to_file "Failed: $step_description"
        return 1
    fi
}

# Execute staging deployment
execute_staging_deployment() {
    log_info "Starting Staging Deployment"
    log_to_file "=== STAGING DEPLOYMENT STARTED ==="
    
    local failed_steps=0
    
    # Step 1: Pre-deployment checks
    if ! execute_step "Pre-Deployment Checks" "./scripts/pre_deployment_checks.sh staging" "Pre-deployment verification"; then
        ((failed_steps++))
    fi
    
    # Step 2: Create backups
    if ! execute_step "Backup Creation" "./scripts/create_backup.sh staging" "Backup creation"; then
        ((failed_steps++))
    fi
    
    # Step 3: Deploy to staging
    if ! execute_step "Staging Deployment" "./scripts/deploy-staging.sh" "Staging deployment"; then
        ((failed_steps++))
    fi
    
    # Step 4: Run migrations
    if ! execute_step "Database Migrations" "./scripts/run_migrations.sh staging" "Database migrations"; then
        ((failed_steps++))
    fi
    
    # Step 5: Verify deployment
    if ! execute_step "Deployment Verification" "./scripts/verify_deployment.sh staging" "Deployment verification"; then
        ((failed_steps++))
    fi
    
    # Step 6: Run smoke tests
    if ! execute_step "Smoke Tests" "./scripts/smoke-tests.sh staging" "Smoke tests"; then
        ((failed_steps++))
    fi
    
    # Step 7: Run comprehensive tests
    if ! execute_step "Comprehensive Tests" "./scripts/run_comprehensive_tests.sh staging all" "Comprehensive tests"; then
        ((failed_steps++))
    fi
    
    log_to_file "=== STAGING DEPLOYMENT COMPLETED ==="
    
    if [ $failed_steps -eq 0 ]; then
        log_info "Staging deployment completed successfully ✓"
        log_to_file "RESULT: SUCCESS"
        return 0
    else
        log_error "Staging deployment completed with $failed_steps failed step(s)"
        log_to_file "RESULT: FAILED ($failed_steps steps failed)"
        return 1
    fi
}

# Execute production deployment
execute_production_deployment() {
    log_info "Starting Production Deployment"
    log_to_file "=== PRODUCTION DEPLOYMENT STARTED ==="
    
    # Confirm production deployment
    log_warn "WARNING: This will deploy to PRODUCTION"
    read -p "Are you sure you want to proceed? (yes/no): " CONFIRM
    
    if [ "$CONFIRM" != "yes" ]; then
        log_info "Production deployment cancelled"
        log_to_file "RESULT: CANCELLED"
        return 1
    fi
    
    local failed_steps=0
    
    # Step 1: Pre-deployment checks
    if ! execute_step "Pre-Deployment Checks" "./scripts/pre_deployment_checks.sh production" "Pre-deployment verification"; then
        ((failed_steps++))
    fi
    
    # Step 2: Create backups
    if ! execute_step "Backup Creation" "./scripts/create_backup.sh production" "Backup creation"; then
        ((failed_steps++))
    fi
    
    # Step 3: Deploy to production
    if ! execute_step "Production Deployment" "./scripts/deploy-production.sh blue-green green" "Production deployment"; then
        ((failed_steps++))
    fi
    
    log_to_file "=== PRODUCTION DEPLOYMENT COMPLETED ==="
    
    if [ $failed_steps -eq 0 ]; then
        log_info "Production deployment completed successfully ✓"
        log_to_file "RESULT: SUCCESS"
        return 0
    else
        log_error "Production deployment completed with $failed_steps failed step(s)"
        log_to_file "RESULT: FAILED ($failed_steps steps failed)"
        return 1
    fi
}

# Main execution
main() {
    local environment="${1:-staging}"
    
    log_info "Deployment Execution Script"
    log_info "Environment: $environment"
    log_info "Log file: $DEPLOYMENT_LOG"
    echo ""
    
    case "$environment" in
        staging)
            execute_staging_deployment
            ;;
        production)
            execute_production_deployment
            ;;
        *)
            log_error "Unknown environment: $environment"
            log_info "Usage: $0 [staging|production]"
            exit 1
            ;;
    esac
    
    log_info "Deployment log saved to: $DEPLOYMENT_LOG"
}

# Run main function
main "$@"

