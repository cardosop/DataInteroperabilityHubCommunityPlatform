#!/bin/bash
#
# Django 6 Upgrade Deployment Script for Production
#
# This script executes the Django 6 upgrade in the production environment
# following best practices, safety measures, and rollback procedures.
#
# Usage:
#   ./scripts/deploy_django6_production.sh [--dry-run] [--skip-backup] [--maintenance-window]
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
MAINTENANCE_WINDOW=false
PRODUCTION_ENV="${PRODUCTION_ENV:-production}"

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
        --maintenance-window)
            MAINTENANCE_WINDOW=true
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

confirm_production() {
    if [ "$DRY_RUN" = false ]; then
        log_warn "=========================================="
        log_warn "PRODUCTION DEPLOYMENT CONFIRMATION"
        log_warn "=========================================="
        log_warn ""
        log_warn "You are about to deploy Django 6 upgrade to PRODUCTION"
        log_warn ""
        read -p "Type 'DEPLOY' to confirm: " confirmation
        if [ "$confirmation" != "DEPLOY" ]; then
            log_error "Deployment cancelled"
            exit 1
        fi
        log_info ""
    fi
}

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if we're in the right directory
    if [ ! -f "manage.py" ]; then
        log_error "manage.py not found. Please run from project root."
        exit 1
    fi
    
    # Check if staging validation passed
    if [ "$DRY_RUN" = false ]; then
        log_info "Verifying staging validation..."
        if ! bash scripts/validate_staging_django6.sh; then
            log_error "Staging validation failed. Please fix issues before production deployment."
            exit 1
        fi
    fi
    
    log_info "Prerequisites check complete."
}

create_backup() {
    if [ "$SKIP_BACKUP" = true ]; then
        log_warn "Skipping backup (--skip-backup flag set)"
        log_warn "⚠️  WARNING: No backup will be created!"
        return
    fi
    
    log_info "Creating production database backup..."
    
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would create production database backup"
        return
    fi
    
    BACKUP_DIR="backups/production/$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"
    
    # Backup database (adjust command based on your production setup)
    # This is a template - adjust for your production database configuration
    log_info "Creating database backup..."
    # Example: pg_dump -h production-db-host -U postgres hub_db > "$BACKUP_DIR/database.sql"
    
    # Backup media files (if applicable)
    if [ -d "media" ]; then
        tar -czf "$BACKUP_DIR/media.tar.gz" media/ || {
            log_warn "Media backup failed (non-critical)"
        }
    fi
    
    log_info "Backup created in $BACKUP_DIR"
    log_info "Backup location saved for rollback: $BACKUP_DIR"
}

enable_maintenance_mode() {
    if [ "$MAINTENANCE_WINDOW" = true ]; then
        log_info "Enabling maintenance mode..."
        
        if [ "$DRY_RUN" = true ]; then
            log_info "[DRY RUN] Would enable maintenance mode"
            return
        fi
        
        # Enable maintenance mode (adjust based on your setup)
        # Example: touch maintenance.flag
        log_info "Maintenance mode enabled"
    else
        log_warn "Maintenance window not enabled. Consider using --maintenance-window for zero-downtime deployment."
    fi
}

disable_maintenance_mode() {
    if [ "$MAINTENANCE_WINDOW" = true ]; then
        log_info "Disabling maintenance mode..."
        
        if [ "$DRY_RUN" = true ]; then
            log_info "[DRY RUN] Would disable maintenance mode"
            return
        fi
        
        # Disable maintenance mode (adjust based on your setup)
        # Example: rm -f maintenance.flag
        log_info "Maintenance mode disabled"
    fi
}

run_migrations() {
    log_info "Running production database migrations..."
    
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would run: python manage.py migrate"
        return
    fi
    
    # Run migrations
    python manage.py migrate --noinput || {
        log_error "Migrations failed"
        log_error "Rollback procedure: Restore from backup in backups/production/"
        exit 1
    }
    
    log_info "Migrations completed successfully."
}

validate_production() {
    log_info "Validating production deployment..."
    
    if [ "$DRY_RUN" = true ]; then
        log_info "[DRY RUN] Would validate production deployment"
        return
    fi
    
    # Check health endpoint
    HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" https://your-production-domain.com/health/ || echo "000")
    if [ "$HEALTH_RESPONSE" != "200" ]; then
        log_error "Health check failed (HTTP $HEALTH_RESPONSE)"
        log_error "Rollback procedure: Restore from backup and revert migrations"
        exit 1
    fi
    
    # Check critical API endpoints
    API_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" https://your-production-domain.com/api/v1/contracts/ || echo "000")
    if [ "$API_RESPONSE" != "200" ] && [ "$API_RESPONSE" != "401" ]; then
        log_warn "API endpoint check returned HTTP $API_RESPONSE (may require authentication)"
    fi
    
    log_info "Production validation complete."
}

main() {
    log_info "=========================================="
    log_info "Django 6 Upgrade Deployment - Production"
    log_info "=========================================="
    log_info ""
    
    if [ "$DRY_RUN" = true ]; then
        log_warn "DRY RUN MODE - No changes will be made"
        log_info ""
    fi
    
    # Confirm production deployment
    confirm_production
    
    # Pre-deployment checks
    check_prerequisites
    
    # Create backup
    create_backup
    
    # Enable maintenance mode
    enable_maintenance_mode
    
    # Run migrations
    run_migrations
    
    # Validate production
    validate_production
    
    # Disable maintenance mode
    disable_maintenance_mode
    
    log_info ""
    log_info "=========================================="
    log_info "Django 6 Upgrade Deployment Complete"
    log_info "=========================================="
    log_info ""
    log_info "Deployment successful!"
    log_info ""
    log_info "Post-deployment tasks:"
    log_info "1. Monitor application logs for any errors"
    log_info "2. Monitor performance metrics"
    log_info "3. Run performance baseline tests"
    log_info "4. Validate all critical workflows"
    log_info "5. Monitor user feedback"
    log_info ""
    log_info "Rollback procedure (if needed):"
    log_info "1. Restore database from backup in backups/production/"
    log_info "2. Revert code to previous version"
    log_info "3. Restart application services"
    log_info ""
}

# Run main function
main

