#!/bin/bash
# Deployment Script for Transformation Feature Removal
# This script handles the deployment of transformation removal to test/staging/production

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${1:-staging}"
SKIP_BACKUP="${2:-false}"
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

# Pre-deployment checks
pre_deployment_checks() {
    log_section "Pre-Deployment Checks"

    # Check if transformation app still exists
    if [ -d "hub/apps/transformation" ]; then
        log_error "Transformation app directory still exists!"
        exit 1
    fi

    # Check if migrations exist
    if [ ! -f "hub/apps/core/migrations/0004_remove_transformation_feature.py" ]; then
        log_error "Transformation removal migration not found!"
        exit 1
    fi

    # Check if monitoring is configured
    if [ ! -f "monitoring/prometheus/alerts/removal-monitoring.yml" ]; then
        log_error "Removal monitoring alerts not configured!"
        exit 1
    fi

    log_info "Pre-deployment checks passed"
}

# Create backup
create_backup() {
    if [ "$SKIP_BACKUP" = "true" ]; then
        log_warn "Skipping backup (SKIP_BACKUP=true)"
        return 0
    fi

    log_section "Creating Backup"

    if [ -f "scripts/create_backup.sh" ]; then
        log_info "Running backup script..."
        bash scripts/create_backup.sh "$ENVIRONMENT"
        log_info "Backup created successfully"
    else
        log_warn "Backup script not found, skipping backup"
    fi
}

# Run migrations
run_migrations() {
    log_section "Running Migrations"

    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    ENV_FILE=".env.${ENVIRONMENT}"

    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Docker Compose file not found: $COMPOSE_FILE"
        exit 1
    fi

    # Load environment variables
    if [ -f "$ENV_FILE" ]; then
        export $(grep -v '^#' "$ENV_FILE" | xargs)
    fi

    # Check if PostgreSQL container is running
    if ! docker compose -f "$COMPOSE_FILE" ps postgres 2>/dev/null | grep -q "Up"; then
        log_error "PostgreSQL container is not running"
        exit 1
    fi

    log_info "Running migrations..."

    # Show migration status
    docker compose -f "$COMPOSE_FILE" exec -T api python3 hub/manage.py showmigrations | grep -E "\[ \]|\[X\]" || true

    # Run migrations
    if docker compose -f "$COMPOSE_FILE" exec -T api python3 hub/manage.py migrate --noinput; then
        log_info "Migrations completed successfully"
    else
        log_error "Migration failed!"
        exit 1
    fi

    # Verify transformation tables are gone
    log_info "Verifying transformation tables are removed..."
    TABLE_COUNT=$(docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U "${POSTGRES_USER:-postgres}" "${POSTGRES_DB:-hub}" -t -c "
        SELECT COUNT(*)
        FROM pg_tables
        WHERE tablename LIKE '%transformation%'
           OR tablename LIKE '%preview%'
           OR tablename LIKE '%wrangling%';
    " | tr -d ' ')

    if [ "$TABLE_COUNT" != "0" ]; then
        log_error "Transformation tables still exist! Count: $TABLE_COUNT"
        exit 1
    fi

    log_info "Transformation tables verified as removed"
}

# Restart services
restart_services() {
    log_section "Restarting Services"

    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"

    log_info "Restarting services..."
    docker compose -f "$COMPOSE_FILE" restart api worker

    log_info "Waiting for services to be healthy..."
    sleep 10

    # Check service health
    if docker compose -f "$COMPOSE_FILE" ps api | grep -q "Up"; then
        log_info "Services restarted successfully"
    else
        log_error "Some services failed to start"
        exit 1
    fi
}

# Verify deployment
verify_deployment() {
    log_section "Verifying Deployment"

    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    API_URL="http://localhost:8000"

    if [ "$ENVIRONMENT" = "production" ]; then
        API_URL="${PRODUCTION_API_URL:-https://api.example.com}"
    fi

    # Test transformation endpoints return 404
    log_info "Testing transformation endpoints..."

    ENDPOINTS=(
        "/api/v1/transformation/pipelines/"
        "/api/v1/transformation/executions/"
        "/api/v1/transformation/previews/"
        "/api/v1/transformation/wrangling/"
    )

    for endpoint in "${ENDPOINTS[@]}"; do
        if command -v curl &> /dev/null; then
            STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${API_URL}${endpoint}" || echo "000")
            if [ "$STATUS" = "404" ]; then
                log_info "✓ ${endpoint} returns 404 (expected)"
            else
                log_error "✗ ${endpoint} returned ${STATUS} (expected 404)"
            fi
        fi
    done

    # Check for import errors in logs
    log_info "Checking for import errors..."
    if docker compose -f "$COMPOSE_FILE" logs api | grep -i "ModuleNotFoundError.*transformation" | head -5; then
        log_error "Import errors detected in logs!"
        exit 1
    else
        log_info "✓ No import errors detected"
    fi

    log_info "Deployment verification completed"
}

# Setup monitoring
setup_monitoring() {
    log_section "Setting Up Monitoring"

    log_info "Monitoring alerts configured in: monitoring/prometheus/alerts/removal-monitoring.yml"
    log_info "Grafana dashboard available at: monitoring/grafana/dashboards/transformation-removal-monitoring.json"
    log_info "See docs/TRANSFORMATION_REMOVAL_MONITORING.md for monitoring procedures"

    # Reload Prometheus if running
    if docker compose ps prometheus 2>/dev/null | grep -q "Up"; then
        log_info "Reloading Prometheus configuration..."
        docker compose exec prometheus kill -HUP 1 || true
    fi
}

# Main execution
main() {
    log_info "Deploying Transformation Removal to: $ENVIRONMENT"
    log_info "Project directory: $PROJECT_DIR"
    echo ""

    pre_deployment_checks
    create_backup
    run_migrations
    restart_services
    verify_deployment
    setup_monitoring

    echo ""
    log_info "Deployment completed successfully ✓"
    log_warn "Please monitor the system for 48 hours using the configured alerts and dashboard"
    log_info "Monitoring guide: docs/TRANSFORMATION_REMOVAL_MONITORING.md"
}

# Run main function
main "$@"
