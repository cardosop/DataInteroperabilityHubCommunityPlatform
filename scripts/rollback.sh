#!/bin/bash
# Rollback Script
# Rolls back deployment to previous version

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${1:-staging}"
ROLLBACK_REASON="${2:-Manual rollback}"
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

confirm_rollback() {
    log_warn "WARNING: This will rollback the deployment to the previous version"
    log_warn "Reason: $ROLLBACK_REASON"
    echo ""
    read -p "Are you sure you want to proceed? (yes/no): " CONFIRM
    
    if [ "$CONFIRM" != "yes" ]; then
        log_info "Rollback cancelled"
        exit 0
    fi
}

# Find latest backup
find_latest_backup() {
    log_section "Finding Latest Backup"
    
    BACKUP_PATTERN="backups/${ENVIRONMENT}_*"
    LATEST_BACKUP=$(ls -td $BACKUP_PATTERN 2>/dev/null | head -1)
    
    if [ -z "$LATEST_BACKUP" ]; then
        log_error "No backup found for environment: $ENVIRONMENT"
        exit 1
    fi
    
    log_info "Latest backup found: $LATEST_BACKUP"
    echo "$LATEST_BACKUP"
}

# Rollback code
rollback_code() {
    log_section "Rolling back Application Code"
    
    BACKUP_DIR="$1"
    MANIFEST_FILE="${BACKUP_DIR}/backup_manifest.txt"
    
    # Find code backup tag
    CODE_TAG=$(grep "^code:" "$MANIFEST_FILE" | cut -d: -f4 | head -1)
    
    if [ -n "$CODE_TAG" ]; then
        log_info "Rolling back to commit: $CODE_TAG"
        
        # Checkout the backup commit
        if git checkout "$CODE_TAG" 2>/dev/null; then
            log_info "Code rolled back to: $CODE_TAG"
        else
            log_error "Failed to rollback code"
            return 1
        fi
    else
        log_warn "No code backup tag found, attempting to checkout previous commit"
        PREVIOUS_COMMIT=$(git rev-parse HEAD~1)
        if git checkout "$PREVIOUS_COMMIT" 2>/dev/null; then
            log_info "Code rolled back to previous commit: $PREVIOUS_COMMIT"
        else
            log_error "Failed to rollback code"
            return 1
        fi
    fi
}

# Rollback database
rollback_database() {
    log_section "Rolling back Database"
    
    BACKUP_DIR="$1"
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    ENV_FILE=".env.${ENVIRONMENT}"
    
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Docker Compose file not found: $COMPOSE_FILE"
        return 1
    fi
    
    # Load environment variables
    if [ -f "$ENV_FILE" ]; then
        export $(grep -v '^#' "$ENV_FILE" | xargs)
    fi
    
    # Find database backup
    DB_BACKUP=$(find "$BACKUP_DIR" -name "database_*.sql.gz" | head -1)
    
    if [ -z "$DB_BACKUP" ]; then
        log_warn "No database backup found, skipping database rollback"
        return 0
    fi
    
    log_warn "WARNING: Database rollback will restore from backup"
    log_warn "This will overwrite current database data"
    read -p "Continue with database rollback? (yes/no): " CONFIRM
    
    if [ "$CONFIRM" != "yes" ]; then
        log_info "Database rollback skipped"
        return 0
    fi
    
    # Check if PostgreSQL container is running
    if ! docker compose -f "$COMPOSE_FILE" ps postgres 2>/dev/null | grep -q "Up"; then
        log_error "PostgreSQL container is not running"
        return 1
    fi
    
    log_info "Restoring database from backup: $DB_BACKUP"
    
    # Decompress and restore
    if gunzip -c "$DB_BACKUP" | docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U "${POSTGRES_USER:-postgres}" "${POSTGRES_DB:-hub}" > /dev/null 2>&1; then
        log_info "Database restored successfully"
    else
        log_error "Failed to restore database"
        return 1
    fi
}

# Rollback configuration
rollback_configuration() {
    log_section "Rolling back Configuration"
    
    BACKUP_DIR="$1"
    CONFIG_BACKUP=$(find "$BACKUP_DIR" -name "config_*.tar.gz" | head -1)
    
    if [ -z "$CONFIG_BACKUP" ]; then
        log_warn "No configuration backup found, skipping configuration rollback"
        return 0
    fi
    
    log_info "Restoring configuration from backup: $CONFIG_BACKUP"
    
    # Extract configuration files
    TEMP_DIR=$(mktemp -d)
    tar -xzf "$CONFIG_BACKUP" -C "$TEMP_DIR"
    
    # Restore files
    for FILE in "$TEMP_DIR"/*; do
        FILENAME=$(basename "$FILE")
        if [ -f "$FILE" ]; then
            cp "$FILE" "./$FILENAME"
            log_info "Restored: $FILENAME"
        fi
    done
    
    rm -rf "$TEMP_DIR"
    log_info "Configuration restored successfully"
}

# Rollback infrastructure (Docker Compose)
rollback_infrastructure() {
    log_section "Rolling back Infrastructure"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Docker Compose file not found: $COMPOSE_FILE"
        return 1
    fi
    
    log_info "Stopping current services..."
    docker compose -f "$COMPOSE_FILE" down
    
    log_info "Starting services with rolled back code..."
    docker compose -f "$COMPOSE_FILE" up -d
    
    # Wait for services to be healthy
    log_info "Waiting for services to be healthy..."
    sleep 10
    
    # Check service health
    if docker compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        log_info "Services started successfully"
    else
        log_error "Some services failed to start"
        return 1
    fi
}

# Verify rollback
verify_rollback() {
    log_section "Verifying Rollback"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    
    # Check service health
    if docker compose -f "$COMPOSE_FILE" ps | grep -q "Up"; then
        log_info "✓ Services are running"
    else
        log_error "✗ Some services are not running"
        return 1
    fi
    
    # Check health endpoint (if available)
    if command -v curl &> /dev/null; then
        API_URL="http://localhost:8000"
        if [ "$ENVIRONMENT" = "production" ]; then
            API_URL="${PRODUCTION_API_URL:-https://api.example.com}"
        fi
        
        if curl -s "${API_URL}/health/" | grep -q "ok\|healthy" 2>/dev/null; then
            log_info "✓ Health endpoint responding"
        else
            log_warn "⚠ Health endpoint not responding (may be normal)"
        fi
    fi
    
    log_info "Rollback verification completed"
}

# Document rollback
document_rollback() {
    log_section "Documenting Rollback"
    
    ROLLBACK_LOG="rollbacks/rollback_${ENVIRONMENT}_$(date +%Y%m%d_%H%M%S).txt"
    mkdir -p rollbacks
    
    {
        echo "Rollback Report"
        echo "=============="
        echo "Environment: $ENVIRONMENT"
        echo "Timestamp: $(date)"
        echo "Reason: $ROLLBACK_REASON"
        echo "Rolled back by: $(whoami)"
        echo ""
        echo "Rollback Details:"
        echo "  - Code: $(git rev-parse HEAD)"
        echo "  - Branch: $(git rev-parse --abbrev-ref HEAD)"
        echo ""
    } > "$ROLLBACK_LOG"
    
    log_info "Rollback documented in: $ROLLBACK_LOG"
}

# Main execution
main() {
    log_info "Starting rollback for: $ENVIRONMENT"
    log_info "Reason: $ROLLBACK_REASON"
    echo ""
    
    confirm_rollback
    
    LATEST_BACKUP=$(find_latest_backup)
    
    rollback_code "$LATEST_BACKUP"
    rollback_configuration "$LATEST_BACKUP"
    rollback_infrastructure
    rollback_database "$LATEST_BACKUP"
    verify_rollback
    document_rollback
    
    echo ""
    log_info "Rollback completed successfully ✓"
    log_warn "Please verify the system is working correctly"
}

# Run main function
main "$@"

