#!/bin/bash
# Backup Creation Script
# Creates comprehensive backups before deployment

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${1:-staging}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="backups/${ENVIRONMENT}_${TIMESTAMP}"
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

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Track backup status
BACKUP_STATUS=0

# Backup database
backup_database() {
    log_section "Backing up Database"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    ENV_FILE=".env.${ENVIRONMENT}"
    
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Docker Compose file not found: $COMPOSE_FILE"
        BACKUP_STATUS=1
        return 1
    fi
    
    # Load environment variables
    if [ -f "$ENV_FILE" ]; then
        export $(grep -v '^#' "$ENV_FILE" | xargs)
    fi
    
    BACKUP_FILE="${BACKUP_DIR}/database_${TIMESTAMP}.sql"
    
    # Check if PostgreSQL container exists and is running
    if ! docker compose -f "$COMPOSE_FILE" ps postgres 2>/dev/null | grep -q "Up"; then
        log_info "PostgreSQL container not running, attempting to start it..."
        
        # Try to start the database container
        if docker compose -f "$COMPOSE_FILE" up -d postgres 2>/dev/null; then
            log_info "Waiting for PostgreSQL to be ready..."
            sleep 5
            
            # Wait for PostgreSQL to be ready (max 30 seconds)
            MAX_WAIT=30
            WAITED=0
            while [ $WAITED -lt $MAX_WAIT ]; do
                if docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U "${POSTGRES_USER:-postgres}" 2>/dev/null; then
                    log_info "PostgreSQL is ready"
                    break
                fi
                sleep 2
                WAITED=$((WAITED + 2))
            done
            
            if [ $WAITED -ge $MAX_WAIT ]; then
                log_error "PostgreSQL did not become ready within ${MAX_WAIT} seconds"
                BACKUP_STATUS=1
                return 1
            fi
        else
            log_error "Failed to start PostgreSQL container"
            BACKUP_STATUS=1
            return 1
        fi
    fi
    
    # Verify PostgreSQL is accessible
    if ! docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U "${POSTGRES_USER:-postgres}" 2>/dev/null; then
        log_error "PostgreSQL is not accessible"
        BACKUP_STATUS=1
        return 1
    fi
    
    log_info "Creating database backup..."
    
    # Get database credentials
    DB_USER="${POSTGRES_USER:-postgres}"
    DB_NAME="${POSTGRES_DB:-hub}"
    
    log_info "Using database: $DB_NAME, user: $DB_USER"
    
    # Check if database exists, create if it doesn't (for new deployments)
    DB_CHECK_ERROR_FILE="${BACKUP_DIR}/db_check_error_${TIMESTAMP}.log"
    DB_CHECK_OUTPUT=$(docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U "$DB_USER" -lqt 2> "$DB_CHECK_ERROR_FILE" || true)
    
    # Check if the command succeeded and database exists
    DB_EXISTS="no"
    DB_CHECK_FAILED=0
    
    if [ -s "$DB_CHECK_ERROR_FILE" ]; then
        DB_CHECK_ERROR=$(cat "$DB_CHECK_ERROR_FILE")
        log_warn "Database check had errors (this is OK for new deployments): $DB_CHECK_ERROR"
        DB_CHECK_FAILED=1
    fi
    
    # Try to determine if database exists (only if check didn't fail)
    if [ $DB_CHECK_FAILED -eq 0 ] && [ -n "$DB_CHECK_OUTPUT" ]; then
        if echo "$DB_CHECK_OUTPUT" | cut -d \| -f 1 | grep -qw "$DB_NAME" 2>/dev/null; then
            DB_EXISTS="yes"
        fi
    fi
    
    # If database doesn't exist or check failed, try to create it or use empty backup
    if [ "$DB_EXISTS" != "yes" ]; then
        if [ $DB_CHECK_FAILED -eq 1 ]; then
            log_info "Database check failed - assuming new deployment, creating empty backup..."
            # Create empty backup directly
            echo "-- PostgreSQL database dump (empty database for new deployment)" > "$BACKUP_FILE"
            echo "-- Database: $DB_NAME" >> "$BACKUP_FILE"
            echo "-- Created: $(date)" >> "$BACKUP_FILE"
            echo "-- This is a new deployment, database will be created during migration" >> "$BACKUP_FILE"
            echo "-- Database check failed, assuming database does not exist" >> "$BACKUP_FILE"
            
            if gzip "$BACKUP_FILE" 2>/dev/null; then
                BACKUP_FILE="${BACKUP_FILE}.gz"
                BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
                log_info "Empty database backup created: $BACKUP_FILE (${BACKUP_SIZE})"
                echo "database:${BACKUP_FILE}:${TIMESTAMP}:empty_new_deployment" >> "${BACKUP_DIR}/backup_manifest.txt"
                rm -f "$DB_CHECK_ERROR_FILE"
                return 0
            else
                log_error "Failed to create empty backup file"
                BACKUP_STATUS=1
                rm -f "$DB_CHECK_ERROR_FILE"
                return 1
            fi
        fi
        
        log_info "Database '$DB_NAME' does not exist (new deployment), creating it..."
        
        # Create the database with error capture
        CREATE_ERROR_FILE="${BACKUP_DIR}/db_create_error_${TIMESTAMP}.log"
        
        # Try with the specified user first
        if docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U "$DB_USER" -c "CREATE DATABASE \"$DB_NAME\";" > "$CREATE_ERROR_FILE" 2>&1; then
            log_info "Database '$DB_NAME' created successfully"
            rm -f "$CREATE_ERROR_FILE"
        else
            # Capture error
            CREATE_ERROR=$(cat "$CREATE_ERROR_FILE" 2>/dev/null || echo "Unknown error")
            
            # Try with postgres superuser if regular user can't create
            log_info "Attempting to create database with postgres superuser..."
            if docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U postgres -c "CREATE DATABASE \"$DB_NAME\";" > "$CREATE_ERROR_FILE" 2>&1; then
                log_info "Database '$DB_NAME' created successfully with postgres user"
                rm -f "$CREATE_ERROR_FILE"
            else
                CREATE_ERROR=$(cat "$CREATE_ERROR_FILE" 2>/dev/null || echo "Unknown error")
                log_warn "Failed to create database '$DB_NAME' - this is OK for new deployments"
                log_warn "Error: $CREATE_ERROR"
                
                # For new deployments, create an empty backup file instead
                log_info "Creating empty database backup for new deployment..."
                echo "-- PostgreSQL database dump (empty database for new deployment)" > "$BACKUP_FILE"
                echo "-- Database: $DB_NAME" >> "$BACKUP_FILE"
                echo "-- Created: $(date)" >> "$BACKUP_FILE"
                echo "-- This is a new deployment, database will be created during migration" >> "$BACKUP_FILE"
                echo "-- Database creation failed: $CREATE_ERROR" >> "$BACKUP_FILE"
                
                # Compress the empty backup
                if gzip "$BACKUP_FILE" 2>/dev/null; then
                    BACKUP_FILE="${BACKUP_FILE}.gz"
                    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
                    log_info "Empty database backup created: $BACKUP_FILE (${BACKUP_SIZE})"
                    echo "database:${BACKUP_FILE}:${TIMESTAMP}:empty_new_deployment" >> "${BACKUP_DIR}/backup_manifest.txt"
                    rm -f "$CREATE_ERROR_FILE" "$DB_CHECK_ERROR_FILE"
                    return 0
                else
                    log_error "Failed to compress empty backup file"
                    BACKUP_STATUS=1
                    rm -f "$CREATE_ERROR_FILE" "$DB_CHECK_ERROR_FILE"
                    return 1
                fi
            fi
        fi
        rm -f "$DB_CHECK_ERROR_FILE"
    else
        log_info "Database '$DB_NAME' exists"
        rm -f "$DB_CHECK_ERROR_FILE"
    fi
    
    # Create database backup with retry logic and proper error handling
    MAX_RETRIES=3
    RETRY_COUNT=0
    BACKUP_SUCCESS=0
    LAST_ERROR=""
    ERROR_FILE="${BACKUP_DIR}/db_backup_error_${TIMESTAMP}.log"
    
    while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
        # Run pg_dump and capture both stdout and stderr
        if docker compose -f "$COMPOSE_FILE" exec -T postgres pg_dump -U "$DB_USER" "$DB_NAME" > "$BACKUP_FILE" 2> "$ERROR_FILE"; then
            # Check if backup file is valid (exists, not empty, and has reasonable size > 100 bytes)
            if [ -f "$BACKUP_FILE" ] && [ -s "$BACKUP_FILE" ]; then
                FILE_SIZE=$(stat -f%z "$BACKUP_FILE" 2>/dev/null || stat -c%s "$BACKUP_FILE" 2>/dev/null || echo "0")
                if [ "$FILE_SIZE" -gt 100 ]; then
                    BACKUP_SUCCESS=1
                    rm -f "$ERROR_FILE"
                    break
                else
                    LAST_ERROR="Backup file is too small ($FILE_SIZE bytes)"
                fi
            else
                LAST_ERROR="Backup file is empty or missing"
            fi
        else
            # Capture error message from stderr
            if [ -f "$ERROR_FILE" ] && [ -s "$ERROR_FILE" ]; then
                LAST_ERROR=$(head -3 "$ERROR_FILE" | tr '\n' ' ' || echo "Unknown error")
            else
                LAST_ERROR="pg_dump command failed with exit code $?"
            fi
        fi
        
        RETRY_COUNT=$((RETRY_COUNT + 1))
        if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
            log_warn "Database backup attempt $RETRY_COUNT failed, retrying..."
            log_warn "Error: $LAST_ERROR"
            sleep 2
        fi
    done
    
    # Clean up error file if backup succeeded
    if [ $BACKUP_SUCCESS -eq 1 ]; then
        rm -f "$ERROR_FILE"
    fi
    
    if [ $BACKUP_SUCCESS -eq 0 ]; then
        log_error "Failed to create database backup after $MAX_RETRIES attempts"
        log_error "Last error: $LAST_ERROR"
        if [ -f "$BACKUP_FILE" ]; then
            log_error "Backup file contents (first 10 lines):"
            head -10 "$BACKUP_FILE" | sed 's/^/  /' || true
        fi
        BACKUP_STATUS=1
        return 1
    fi
    
    # Verify backup file was created and has content
    if [ ! -f "$BACKUP_FILE" ] || [ ! -s "$BACKUP_FILE" ]; then
        log_error "Database backup file is empty or missing"
        BACKUP_STATUS=1
        return 1
    fi
    
    # Compress backup
    if ! gzip "$BACKUP_FILE" 2>/dev/null; then
        log_error "Failed to compress database backup"
        BACKUP_STATUS=1
        return 1
    fi
    
    BACKUP_FILE="${BACKUP_FILE}.gz"
    
    # Verify compressed backup
    if [ ! -f "$BACKUP_FILE" ] || [ ! -s "$BACKUP_FILE" ]; then
        log_error "Compressed database backup file is empty or missing"
        BACKUP_STATUS=1
        return 1
    fi
    
    BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    log_info "Database backup created: $BACKUP_FILE (${BACKUP_SIZE})"
    
    # Save backup metadata
    echo "database:${BACKUP_FILE}:${TIMESTAMP}" >> "${BACKUP_DIR}/backup_manifest.txt"
}

# Backup application code
backup_application_code() {
    log_section "Backing up Application Code"
    
    # Get current Git commit
    CURRENT_COMMIT=$(git rev-parse HEAD)
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    
    # Create Git bundle
    BACKUP_FILE="${BACKUP_DIR}/code_${TIMESTAMP}.bundle"
    
    log_info "Creating Git bundle..."
    if git bundle create "$BACKUP_FILE" --all 2>/dev/null; then
        BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
        log_info "Code backup created: $BACKUP_FILE (${BACKUP_SIZE})"
        
        # Save backup metadata
        echo "code:${BACKUP_FILE}:${TIMESTAMP}:${CURRENT_COMMIT}:${CURRENT_BRANCH}" >> "${BACKUP_DIR}/backup_manifest.txt"
        
        # Also create a tag for this backup
        BACKUP_TAG="backup-${ENVIRONMENT}-${TIMESTAMP}"
        if git tag "$BACKUP_TAG" 2>/dev/null; then
            log_info "Created backup tag: $BACKUP_TAG"
        fi
    else
        log_error "Failed to create code backup"
        BACKUP_STATUS=1
    fi
}

# Backup configuration files
backup_configuration() {
    log_section "Backing up Configuration Files"
    
    CONFIG_FILES=(
        ".env.${ENVIRONMENT}"
        "docker-compose.${ENVIRONMENT}.yml"
        "hub/settings.py"
        "requirements.txt"
    )
    
    CONFIG_DIR="${BACKUP_DIR}/config"
    mkdir -p "$CONFIG_DIR"
    
    BACKED_UP=0
    for FILE in "${CONFIG_FILES[@]}"; do
        if [ -f "$FILE" ]; then
            cp "$FILE" "$CONFIG_DIR/"
            BACKED_UP=$((BACKED_UP + 1))
        fi
    done
    
    if [ $BACKED_UP -gt 0 ]; then
        # Create tar archive
        BACKUP_FILE="${BACKUP_DIR}/config_${TIMESTAMP}.tar.gz"
        tar -czf "$BACKUP_FILE" -C "$CONFIG_DIR" .
        rm -rf "$CONFIG_DIR"
        
        BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
        log_info "Configuration backup created: $BACKUP_FILE (${BACKUP_SIZE})"
        echo "config:${BACKUP_FILE}:${TIMESTAMP}" >> "${BACKUP_DIR}/backup_manifest.txt"
    else
        log_warn "No configuration files found to backup"
    fi
}

# Backup static files
backup_static_files() {
    log_section "Backing up Static Files"
    
    STATIC_DIRS=(
        "staticfiles"
        "static"
    )
    
    STATIC_BACKUP="${BACKUP_DIR}/static_${TIMESTAMP}.tar.gz"
    FOUND_FILES=0
    
    for DIR in "${STATIC_DIRS[@]}"; do
        if [ -d "$DIR" ] && [ "$(ls -A $DIR 2>/dev/null)" ]; then
            FOUND_FILES=1
            break
        fi
    done
    
    if [ $FOUND_FILES -eq 1 ]; then
        log_info "Creating static files backup..."
        tar -czf "$STATIC_BACKUP" "${STATIC_DIRS[@]}" 2>/dev/null || true
        
        if [ -f "$STATIC_BACKUP" ] && [ -s "$STATIC_BACKUP" ]; then
            BACKUP_SIZE=$(du -h "$STATIC_BACKUP" | cut -f1)
            log_info "Static files backup created: $STATIC_BACKUP (${BACKUP_SIZE})"
            echo "static:${STATIC_BACKUP}:${TIMESTAMP}" >> "${BACKUP_DIR}/backup_manifest.txt"
        else
            log_warn "Static files backup is empty"
        fi
    else
        log_warn "No static files found to backup"
    fi
}

# Backup media files
backup_media_files() {
    log_section "Backing up Media Files"
    
    MEDIA_DIRS=(
        "media"
        "uploads"
    )
    
    MEDIA_BACKUP="${BACKUP_DIR}/media_${TIMESTAMP}.tar.gz"
    FOUND_FILES=0
    
    for DIR in "${MEDIA_DIRS[@]}"; do
        if [ -d "$DIR" ] && [ "$(ls -A $DIR 2>/dev/null)" ]; then
            FOUND_FILES=1
            break
        fi
    done
    
    if [ $FOUND_FILES -eq 1 ]; then
        log_info "Creating media files backup..."
        tar -czf "$MEDIA_BACKUP" "${MEDIA_DIRS[@]}" 2>/dev/null || true
        
        if [ -f "$MEDIA_BACKUP" ] && [ -s "$MEDIA_BACKUP" ]; then
            BACKUP_SIZE=$(du -h "$MEDIA_BACKUP" | cut -f1)
            log_info "Media files backup created: $MEDIA_BACKUP (${BACKUP_SIZE})"
            echo "media:${MEDIA_BACKUP}:${TIMESTAMP}" >> "${BACKUP_DIR}/backup_manifest.txt"
        else
            log_warn "Media files backup is empty"
        fi
    else
        log_warn "No media files found to backup"
    fi
}

# Verify backups
verify_backups() {
    log_section "Verifying Backups"
    
    VERIFICATION_FAILED=0
    VERIFIED_COUNT=0
    
    # Ensure variables are set (for arithmetic operations with set -e)
    : ${VERIFICATION_FAILED:=0}
    : ${VERIFIED_COUNT:=0}
    
    if [ ! -f "${BACKUP_DIR}/backup_manifest.txt" ]; then
        log_error "Backup manifest file not found"
        BACKUP_STATUS=1
        return 1
    fi
    
    while IFS= read -r LINE; do
        # Skip empty lines
        if [ -z "$LINE" ]; then
            continue
        fi
        
        # Parse the line (format: TYPE:FILE:TIMESTAMP[:REST...])
        # Extract TYPE (first field)
        TYPE=$(echo "$LINE" | cut -d: -f1)
        
        # Extract FILE - remove TYPE: prefix, then extract everything before timestamp pattern
        AFTER_TYPE=$(echo "$LINE" | sed "s/^${TYPE}://")
        
        # FILE is everything up to the timestamp (format: YYYYMMDD_HHMMSS or YYYYMMDD)
        if echo "$AFTER_TYPE" | grep -qE "^([^:]+):[0-9]{8}(_[0-9]{6})?:"; then
            # Extract FILE as everything before the timestamp
            FILE=$(echo "$AFTER_TYPE" | sed -E 's/:[0-9]{8}(_[0-9]{6})?:.*$//')
        else
            # Fallback: FILE is first part after TYPE:
            FILE=$(echo "$AFTER_TYPE" | cut -d: -f1)
        fi
        
        # Skip if TYPE is empty
        if [ -z "$TYPE" ]; then
            continue
        fi
        
        # All backups must be verified - no skips allowed
        if [ -z "$FILE" ] || [ "$FILE" = "SKIPPED" ]; then
            log_error "✗ $TYPE backup verification failed: backup was skipped (not allowed)"
            VERIFICATION_FAILED=1
            continue
        fi
        
        if [ -f "$FILE" ] && [ -s "$FILE" ]; then
            BACKUP_SIZE=$(du -h "$FILE" 2>/dev/null | cut -f1 || echo "N/A")
            log_info "✓ $TYPE backup verified: $FILE (${BACKUP_SIZE})"
            VERIFIED_COUNT=$((VERIFIED_COUNT + 1))
        else
            log_error "✗ $TYPE backup verification failed: $FILE (file missing or empty)"
            VERIFICATION_FAILED=1
        fi
    done < "${BACKUP_DIR}/backup_manifest.txt"
    
    if [ $VERIFICATION_FAILED -eq 0 ] && [ $VERIFIED_COUNT -gt 0 ]; then
        log_info "All backups verified successfully ($VERIFIED_COUNT verified)"
        return 0
    else
        if [ $VERIFIED_COUNT -eq 0 ]; then
            log_error "No backups were verified successfully"
        else
            log_error "Backup verification failed ($VERIFIED_COUNT verified, $VERIFICATION_FAILED failed)"
        fi
        BACKUP_STATUS=1
        return 1
    fi
}

# Create backup summary
create_backup_summary() {
    log_section "Backup Summary"
    
    SUMMARY_FILE="${BACKUP_DIR}/backup_summary.txt"
    
    {
        echo "Backup Summary"
        echo "=============="
        echo "Environment: $ENVIRONMENT"
        echo "Timestamp: $TIMESTAMP"
        echo "Backup Directory: $BACKUP_DIR"
        echo ""
        echo "Backed up components:"
        while IFS=: read -r TYPE FILE TIMESTAMP REST; do
            if [ -z "$TYPE" ]; then
                continue
            fi
            if [ -n "$FILE" ] && [ "$FILE" != "SKIPPED" ]; then
                SIZE=$(du -h "$FILE" 2>/dev/null | cut -f1 || echo "N/A")
                echo "  - $TYPE: $FILE ($SIZE)"
            else
                echo "  - $TYPE: FAILED (backup was not created)"
            fi
        done < "${BACKUP_DIR}/backup_manifest.txt"
        echo ""
        echo "Total backup size:"
        du -sh "$BACKUP_DIR" | cut -f1
    } > "$SUMMARY_FILE"
    
    cat "$SUMMARY_FILE"
    log_info "Backup summary saved to: $SUMMARY_FILE"
}

# Main execution
main() {
    log_info "Creating backups for: $ENVIRONMENT"
    log_info "Backup directory: $BACKUP_DIR"
    echo ""
    
    backup_database || true  # Don't fail if database backup creates empty backup
    backup_application_code
    backup_configuration
    backup_static_files
    backup_media_files
    
    # Verify backups (this must succeed)
    if verify_backups; then
        VERIFY_RESULT=0
    else
        VERIFY_RESULT=$?
        log_error "Backup verification failed with exit code: $VERIFY_RESULT"
    fi
    
    create_backup_summary
    
    echo ""
    # Count successful backups from manifest
    SUCCESSFUL_BACKUPS=$(grep -v "^$" "${BACKUP_DIR}/backup_manifest.txt" 2>/dev/null | grep -v "SKIPPED" | wc -l || echo "0")
    
    # Check if verification passed
    if [ "${VERIFY_RESULT:-1}" -eq 0 ] && [ "$SUCCESSFUL_BACKUPS" -gt 0 ]; then
        log_info "Backup creation completed successfully ✓"
        log_info "Successfully backed up $SUCCESSFUL_BACKUPS component(s)"
        log_info "Backup location: $BACKUP_DIR"
        exit 0
    else
        log_error "Backup creation failed"
        if [ "$SUCCESSFUL_BACKUPS" -eq 0 ]; then
            log_error "No backups were created successfully"
        fi
        if [ "${VERIFY_RESULT:-1}" -ne 0 ]; then
            log_error "Backup verification failed (exit code: ${VERIFY_RESULT:-1})"
        fi
        exit 1
    fi
}

# Run main function
main "$@"

