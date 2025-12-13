#!/bin/bash
#
# Django 6 Upgrade Deployment Script for Staging
#
# This script executes the Django 6 upgrade in the staging environment
# following best practices and safety measures.
#
# Usage:
#   ./scripts/deploy_django6_staging.sh [--dry-run] [--skip-backup]
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DRY_RUN=false
SKIP_BACKUP=false
STAGING_ENV="${STAGING_ENV:-staging}"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --dry-run)
            DRY_RUN=true
            shift
            ;;
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

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

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if we're in the right directory
    if [ ! -f "manage.py" ]; then
        log_error "manage.py not found. Please run from project root."
        exit 1
    fi
    
    # Check if Docker Compose is available
    if ! command -v docker-compose &> /dev/null; then
        log_error "docker-compose not found. Please install Docker Compose."
        exit 1
    fi
    
    # Check if services are running
    if ! docker-compose ps | grep -q "Up"; then
        log_warn "Some Docker Compose services may not be running."
    fi
    
    log_info "Prerequisites check complete."
}

create_backup() {
    if [ "$SKIP_BACKUP" = true ]; then
        log_warn "Skipping backup (--skip-backup flag set)"
        return
    fi
    
    log_info "Creating database backup..."
    
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would create database backup"
        return
    fi
    
    BACKUP_DIR="backups/staging/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # Backup database
    docker-compose exec -T postgres pg_dump -U postgres hub_db > "$BACKUP_DIR/database.sql" || {
        log_error "Database backup failed"
        exit 1
    }
    
    # Backup media files (if applicable)
    if [ -d "media" ]; then
        tar -czf "$BACKUP_DIR/media.tar.gz" media/ || {
            log_warn "Media backup failed (non-critical)"
        }
    fi
    
    log_info "Backup created in $BACKUP_DIR"
}

run_migrations() {
    log_info "Running database migrations..."
    
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would run: python manage.py migrate"
        return
    fi
    
    # Run migrations
    python manage.py migrate --noinput || {
        log_error "Migrations failed"
        exit 1
    }
    
    log_info "Migrations completed successfully."
}

run_tests() {
    log_info "Running test suite..."
    
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would run: pytest tests/ -v"
        return
    fi
    
    # Run critical tests
    pytest tests/regression/ -v --tb=short || {
        log_error "Regression tests failed"
        exit 1
    }
    
    pytest tests/e2e/test_django6_upgrade_critical_workflows.py -v --tb=short || {
        log_error "Django 6 critical workflow tests failed"
        exit 1
    }
    
    log_info "Tests passed successfully."
}

validate_functionality() {
    log_info "Validating functionality..."
    
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would validate functionality"
        return
    fi
    
    # Check health endpoint
    HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health/ || echo "000")
    if [ "$HEALTH_RESPONSE" != "200" ]; then
        log_error "Health check failed (HTTP $HEALTH_RESPONSE)"
        exit 1
    fi
    
    # Check API endpoint
    API_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/contracts/ || echo "000")
    if [ "$API_RESPONSE" != "200" ] && [ "$API_RESPONSE" != "401" ]; then
        log_warn "API endpoint check returned HTTP $API_RESPONSE (may require authentication)"
    fi
    
    log_info "Functionality validation complete."
}

check_jsonfield_indexes() {
    log_info "Checking JSONField GIN indexes..."
    
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would check JSONField GIN indexes"
        return
    fi
    
    python scripts/optimize_jsonfield_queries.py --check || {
        log_warn "JSONField index check had warnings (non-critical)"
    }
}

main() {
    log_info "=========================================="
    log_info "Django 6 Upgrade Deployment - Staging"
    log_info "=========================================="
    log_info ""
    
    if [ "$DRY_RUN" = true ]; then
        log_warn "DRY RUN MODE - No changes will be made"
        log_info ""
    fi
    
    # Pre-deployment checks
    check_prerequisites
    
    # Create backup
    create_backup
    
    # Run migrations
    run_migrations
    
    # Check JSONField indexes
    check_jsonfield_indexes
    
    # Run tests
    run_tests
    
    # Validate functionality
    validate_functionality
    
    log_info ""
    log_info "=========================================="
    log_info "Django 6 Upgrade Deployment Complete"
    log_info "=========================================="
    log_info ""
    log_info "Next steps:"
    log_info "1. Monitor application logs for any errors"
    log_info "2. Run performance baseline tests"
    log_info "3. Validate all critical workflows"
    log_info "4. Proceed to production deployment after validation"
    log_info ""
}

# Run main function
main

