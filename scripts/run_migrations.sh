#!/bin/bash
# Database Migration Script
# Runs Django migrations with verification

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${1:-staging}"
MONITOR="${2:-false}"
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

# Check prerequisites
check_prerequisites() {
    log_section "Checking Prerequisites"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Docker Compose file not found: $COMPOSE_FILE"
        exit 1
    fi
    
    # Check if PostgreSQL container is running
    if ! docker compose -f "$COMPOSE_FILE" ps postgres 2>/dev/null | grep -q "Up"; then
        log_error "PostgreSQL container is not running"
        exit 1
    fi
    
    log_info "Prerequisites check passed"
}

# Get current migration state
get_migration_state() {
    log_section "Checking Current Migration State"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    
    log_info "Getting current migration state..."
    docker compose -f "$COMPOSE_FILE" exec -T api-service python hub/manage.py showmigrations --plan 2>/dev/null || {
        log_warn "Could not get migration state (this is OK if migrations haven't been run)"
    }
}

# Check for pending migrations
check_pending_migrations() {
    log_section "Checking for Pending Migrations"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    
    log_info "Checking for model changes that need migrations..."
    PENDING_APPS=$(docker compose -f "$COMPOSE_FILE" exec -T api-service python hub/manage.py makemigrations --dry-run 2>&1 | grep -E "Migrations for|No changes detected" || echo "")
    
    if echo "$PENDING_APPS" | grep -q "Migrations for"; then
        log_warn "Pending migrations detected. Creating migrations..."
        if docker compose -f "$COMPOSE_FILE" exec -T api-service python hub/manage.py makemigrations --noinput 2>&1; then
            log_info "Migrations created successfully"
        else
            log_error "Failed to create migrations"
            return 1
        fi
    else
        log_info "No pending migrations detected"
    fi
}

# Run migrations
run_migrations() {
    log_section "Running Database Migrations"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    START_TIME=$(date +%s)
    
    # Check and create pending migrations first
    check_pending_migrations
    
    log_info "Running migrations..."
    
    if [ "$MONITOR" = "true" ] || [ "$MONITOR" = "--monitor" ]; then
        # Run migrations with monitoring
        log_info "Running migrations with monitoring..."
        
        # Start monitoring in background
        (
            while true; do
                docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U postgres -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';" 2>/dev/null || true
                sleep 2
            done
        ) &
        MONITOR_PID=$!
        
        # Run migrations
        if docker compose -f "$COMPOSE_FILE" exec -T api-service python hub/manage.py migrate --noinput 2>&1; then
            kill $MONITOR_PID 2>/dev/null || true
            END_TIME=$(date +%s)
            DURATION=$((END_TIME - START_TIME))
            log_info "Migrations completed successfully in ${DURATION} seconds"
        else
            kill $MONITOR_PID 2>/dev/null || true
            log_error "Migrations failed"
            return 1
        fi
    else
        # Run migrations normally
        if docker compose -f "$COMPOSE_FILE" exec -T api-service python hub/manage.py migrate --noinput 2>&1; then
            END_TIME=$(date +%s)
            DURATION=$((END_TIME - START_TIME))
            log_info "Migrations completed successfully in ${DURATION} seconds"
        else
            log_error "Migrations failed"
            return 1
        fi
    fi
}

# Verify migrations
verify_migrations() {
    log_section "Verifying Migrations"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    
    # Check for unapplied migrations
    log_info "Checking for unapplied migrations..."
    UNAPPLIED=$(docker compose -f "$COMPOSE_FILE" exec -T api-service python hub/manage.py showmigrations --plan 2>/dev/null | grep "\[ \]" | wc -l || echo "0")
    
    if [ "$UNAPPLIED" -eq 0 ]; then
        log_info "✓ All migrations applied"
    else
        log_warn "⚠ $UNAPPLIED unapplied migrations detected"
    fi
    
    # Verify database schema
    log_info "Verifying database schema..."
    if docker compose -f "$COMPOSE_FILE" exec -T api-service python hub/manage.py check --database default 2>/dev/null; then
        log_info "✓ Database schema is valid"
    else
        log_warn "⚠ Database schema check returned warnings"
    fi
}

# Verify data integrity
verify_data_integrity() {
    log_section "Verifying Data Integrity"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    
    log_info "Checking data integrity..."
    
    # Check for common data integrity issues
    # This is a basic check - can be extended
    
    # Check if critical tables exist
    CRITICAL_TABLES=("tenants" "users" "assets" "contracts")
    
    for TABLE in "${CRITICAL_TABLES[@]}"; do
        if docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U postgres -d "${POSTGRES_DB:-hub}" -c "SELECT 1 FROM ${TABLE} LIMIT 1;" &>/dev/null; then
            log_info "✓ Table $TABLE exists and is accessible"
        else
            log_warn "⚠ Table $TABLE may not exist or is not accessible"
        fi
    done
}

# Test migration rollback (if needed)
test_migration_rollback() {
    log_section "Testing Migration Rollback"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    
    log_warn "Migration rollback testing is not automated"
    log_info "To test rollback manually:"
    log_info "  1. Identify migrations to rollback"
    log_info "  2. Run: python hub/manage.py migrate <app> <previous_migration>"
    log_info "  3. Verify database state"
    log_info "  4. Re-run migrations"
}

# Main execution
main() {
    log_info "Running database migrations for: $ENVIRONMENT"
    if [ "$MONITOR" = "true" ] || [ "$MONITOR" = "--monitor" ]; then
        log_info "Monitoring enabled"
    fi
    echo ""
    
    check_prerequisites
    get_migration_state
    run_migrations
    verify_migrations
    verify_data_integrity
    
    if [ "$ENVIRONMENT" = "staging" ]; then
        test_migration_rollback
    fi
    
    echo ""
    log_info "Migration process completed successfully ✓"
}

# Run main function
main "$@"

