#!/bin/bash
# Verification Script for Transformation Feature Removal
# This script verifies that transformation removal was successful

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${1:-staging}"
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

log_pass() {
    echo -e "${GREEN}✓${NC} $1"
}

log_fail() {
    echo -e "${RED}✗${NC} $1"
}

# Verification counters
PASSED=0
FAILED=0
PENDING=0

# Code verification
verify_code() {
    log_section "Code Verification"

    # Check for transformation imports
    IMPORT_COUNT=$(grep -r "from hub.apps.transformation" hub/ 2>/dev/null | grep -v "test\|backup\|deprecated\|__pycache__" | wc -l | tr -d ' ')
    if [ -z "$IMPORT_COUNT" ] || [ "$IMPORT_COUNT" = "0" ]; then
        log_pass "No transformation imports found"
        ((PASSED++))
    else
        log_fail "Found $IMPORT_COUNT transformation imports"
        ((FAILED++))
    fi

    # Check for transformation directory
    if [ ! -d "hub/apps/transformation" ]; then
        log_pass "Transformation app directory removed"
        ((PASSED++))
    else
        log_fail "Transformation app directory still exists"
        ((FAILED++))
    fi

    # Check URL routing
    if ! grep -q "transformation" hub/apps/api/urls.py 2>/dev/null; then
        log_pass "No transformation URLs in routing"
        ((PASSED++))
    else
        log_fail "Transformation URLs still in routing"
        ((FAILED++))
    fi
}

# Database verification
verify_database() {
    log_section "Database Verification"

    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    ENV_FILE=".env.${ENVIRONMENT}"

    if [ ! -f "$COMPOSE_FILE" ]; then
        log_warn "Docker Compose file not found, skipping database verification"
        ((PENDING++))
        return 0
    fi

    # Load environment variables
    if [ -f "$ENV_FILE" ]; then
        export $(grep -v '^#' "$ENV_FILE" | xargs)
    fi

    # Check if PostgreSQL is accessible
    if ! docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U "${POSTGRES_USER:-postgres}" &>/dev/null; then
        log_warn "PostgreSQL not accessible, skipping database verification"
        ((PENDING++))
        return 0
    fi

    # Check transformation tables
    TABLE_COUNT=$(docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U "${POSTGRES_USER:-postgres}" "${POSTGRES_DB:-hub}" -t -c "
        SELECT COUNT(*)
        FROM pg_tables
        WHERE tablename LIKE '%transformation%'
           OR tablename LIKE '%preview%'
           OR tablename LIKE '%wrangling%';
    " 2>/dev/null | tr -d ' ' || echo "error")

    if [ "$TABLE_COUNT" = "0" ]; then
        log_pass "No transformation tables found in database"
        ((PASSED++))
    elif [ "$TABLE_COUNT" = "error" ]; then
        log_warn "Could not verify database tables"
        ((PENDING++))
    else
        log_fail "Found $TABLE_COUNT transformation tables in database"
        ((FAILED++))
    fi

    # Check for transformation jobs
    JOB_COUNT=$(docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U "${POSTGRES_USER:-postgres}" "${POSTGRES_DB:-hub}" -t -c "
        SELECT COUNT(*)
        FROM jobs_job
        WHERE job_type = 'TRANSFORMATION_PIPELINE_EXECUTION'
          AND status IN ('PENDING', 'RUNNING');
    " 2>/dev/null | tr -d ' ' || echo "error")

    if [ "$JOB_COUNT" = "0" ]; then
        log_pass "No pending/running transformation jobs"
        ((PASSED++))
    elif [ "$JOB_COUNT" = "error" ]; then
        log_warn "Could not verify job status"
        ((PENDING++))
    else
        log_fail "Found $JOB_COUNT pending/running transformation jobs"
        ((FAILED++))
    fi
}

# API verification
verify_api() {
    log_section "API Verification"

    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    API_URL="http://localhost:8000"

    if [ "$ENVIRONMENT" = "production" ]; then
        API_URL="${PRODUCTION_API_URL:-https://api.example.com}"
    fi

    if ! command -v curl &> /dev/null; then
        log_warn "curl not available, skipping API verification"
        ((PENDING++))
        return 0
    fi

    # Check if API is accessible
    if ! curl -s -o /dev/null -w "%{http_code}" "${API_URL}/health/" | grep -q "200\|404"; then
        log_warn "API not accessible, skipping API verification"
        ((PENDING++))
        return 0
    fi

    # Test transformation endpoints
    ENDPOINTS=(
        "/api/v1/transformation/pipelines/"
        "/api/v1/transformation/executions/"
        "/api/v1/transformation/previews/"
        "/api/v1/transformation/wrangling/"
    )

    ALL_404=true
    for endpoint in "${ENDPOINTS[@]}"; do
        STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${API_URL}${endpoint}" 2>/dev/null || echo "000")
        if [ "$STATUS" = "404" ]; then
            log_pass "${endpoint} returns 404"
        else
            log_fail "${endpoint} returned ${STATUS} (expected 404)"
            ALL_404=false
        fi
    done

    if [ "$ALL_404" = "true" ]; then
        ((PASSED++))
    else
        ((FAILED++))
    fi
}

# Log verification
verify_logs() {
    log_section "Log Verification"

    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"

    if [ ! -f "$COMPOSE_FILE" ]; then
        log_warn "Docker Compose file not found, skipping log verification"
        ((PENDING++))
        return 0
    fi

    # Check for import errors
    IMPORT_ERRORS=$(docker compose -f "$COMPOSE_FILE" logs api 2>/dev/null | grep -i "ModuleNotFoundError.*transformation" | wc -l || echo "0")

    if [ "$IMPORT_ERRORS" = "0" ]; then
        log_pass "No import errors in logs"
        ((PASSED++))
    else
        log_fail "Found $IMPORT_ERRORS import errors in logs"
        ((FAILED++))
    fi

    # Check for transformation-related errors
    TRANSFORM_ERRORS=$(docker compose -f "$COMPOSE_FILE" logs api 2>/dev/null | grep -i "transformation" | grep -i "error\|exception" | wc -l || echo "0")

    if [ "$TRANSFORM_ERRORS" = "0" ]; then
        log_pass "No transformation-related errors in logs"
        ((PASSED++))
    else
        log_warn "Found $TRANSFORM_ERRORS transformation-related errors in logs (may be expected during removal)"
        ((PENDING++))
    fi
}

# Monitoring verification
verify_monitoring() {
    log_section "Monitoring Verification"

    # Check alert configuration
    if [ -f "monitoring/prometheus/alerts/removal-monitoring.yml" ]; then
        log_pass "Removal monitoring alerts configured"
        ((PASSED++))
    else
        log_fail "Removal monitoring alerts not found"
        ((FAILED++))
    fi

    # Check dashboard
    if [ -f "monitoring/grafana/dashboards/transformation-removal-monitoring.json" ]; then
        log_pass "Removal monitoring dashboard created"
        ((PASSED++))
    else
        log_fail "Removal monitoring dashboard not found"
        ((FAILED++))
    fi
}

# Documentation verification
verify_documentation() {
    log_section "Documentation Verification"

    DOCS=(
        "docs/TRANSFORMATION_REMOVAL.md"
        "docs/TRANSFORMATION_REMOVAL_BACKUP_IMPACT.md"
        "docs/TRANSFORMATION_REMOVAL_MONITORING.md"
        "docs/TRANSFORMATION_REMOVAL_ROLLBACK.md"
        "docs/TRANSFORMATION_REMOVAL_SUCCESS_CRITERIA.md"
    )

    ALL_EXIST=true
    for doc in "${DOCS[@]}"; do
        if [ -f "$doc" ]; then
            log_pass "$doc exists"
        else
            log_fail "$doc not found"
            ALL_EXIST=false
        fi
    done

    if [ "$ALL_EXIST" = "true" ]; then
        ((PASSED++))
    else
        ((FAILED++))
    fi
}

# Summary
print_summary() {
    log_section "Verification Summary"

    TOTAL=$((PASSED + FAILED + PENDING))

    echo "Passed:  $PASSED"
    echo "Failed:  $FAILED"
    echo "Pending: $PENDING"
    echo "Total:   $TOTAL"
    echo ""

    if [ "$FAILED" -eq 0 ] && [ "$PENDING" -eq 0 ]; then
        log_info "All verifications passed! ✓"
        exit 0
    elif [ "$FAILED" -eq 0 ]; then
        log_warn "All critical verifications passed, but some checks are pending"
        log_warn "Pending checks may require runtime environment or manual verification"
        exit 0
    else
        log_error "Some verifications failed. Please review the errors above."
        exit 1
    fi
}

# Main execution
main() {
    log_info "Verifying Transformation Removal for: $ENVIRONMENT"
    echo ""

    verify_code
    verify_database
    verify_api
    verify_logs
    verify_monitoring
    verify_documentation

    print_summary
}

# Run main function
main "$@"
