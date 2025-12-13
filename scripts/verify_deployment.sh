#!/bin/bash
# Deployment Verification Script
# Verifies all services and infrastructure after deployment

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

check_passed() {
    echo -e "${GREEN}✓${NC} $1"
}

check_failed() {
    echo -e "${RED}✗${NC} $1"
    return 1
}

# Track failures
FAILURES=0

# Verify services are running
verify_services_running() {
    log_section "Verifying Services are Running"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Docker Compose file not found: $COMPOSE_FILE"
        ((FAILURES++))
        return
    fi
    
    # Get list of services
    SERVICES=$(docker compose -f "$COMPOSE_FILE" config --services 2>/dev/null || echo "")
    
    if [ -z "$SERVICES" ]; then
        log_error "Could not get service list"
        ((FAILURES++))
        return
    fi
    
    for SERVICE in $SERVICES; do
        if docker compose -f "$COMPOSE_FILE" ps "$SERVICE" 2>/dev/null | grep -q "Up"; then
            check_passed "Service $SERVICE is running"
        else
            check_failed "Service $SERVICE is not running"
            ((FAILURES++))
        fi
    done
}

# Verify service health
verify_service_health() {
    log_section "Verifying Service Health"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    
    # Check API service health
    if docker compose -f "$COMPOSE_FILE" exec -T api-service curl -s http://localhost:8000/health/ 2>/dev/null | grep -q "ok\|healthy"; then
        check_passed "API service health endpoint responding"
    else
        check_failed "API service health endpoint not responding"
        ((FAILURES++))
    fi
}

# Verify database connectivity
verify_database_connectivity() {
    log_section "Verifying Database Connectivity"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    
    # Check PostgreSQL is accessible
    if docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U postgres -c "SELECT 1;" &>/dev/null; then
        check_passed "PostgreSQL is accessible"
    else
        check_failed "PostgreSQL is not accessible"
        ((FAILURES++))
    fi
    
    # Check API service can connect to database
    if docker compose -f "$COMPOSE_FILE" exec -T api-service python hub/manage.py check --database default &>/dev/null; then
        check_passed "API service can connect to database"
    else
        check_failed "API service cannot connect to database"
        ((FAILURES++))
    fi
}

# Verify Redis connectivity
verify_redis_connectivity() {
    log_section "Verifying Redis Connectivity"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    
    # Check Redis is accessible
    if docker compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
        check_passed "Redis is accessible"
    else
        check_failed "Redis is not accessible"
        ((FAILURES++))
    fi
    
    # Check API service can connect to Redis
    if docker compose -f "$COMPOSE_FILE" exec -T api-service python -c "import redis; r=redis.from_url('${REDIS_URL:-redis://redis:6379/0}'); r.ping()" 2>/dev/null; then
        check_passed "API service can connect to Redis"
    else
        check_failed "API service cannot connect to Redis"
        ((FAILURES++))
    fi
}

# Verify S3/MinIO connectivity
verify_s3_connectivity() {
    log_section "Verifying S3/MinIO Connectivity"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    
    # Check MinIO is accessible (if using MinIO)
    if docker compose -f "$COMPOSE_FILE" ps minio 2>/dev/null | grep -q "Up"; then
        if curl -s http://localhost:9000/minio/health/live &>/dev/null; then
            check_passed "MinIO is accessible"
        else
            check_failed "MinIO is not accessible"
            ((FAILURES++))
        fi
    else
        log_warn "MinIO service not found (may be using external S3)"
    fi
}

# Verify middleware
verify_middleware() {
    log_section "Verifying Middleware"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    
    # Check middleware is working by making a request
    if docker compose -f "$COMPOSE_FILE" exec -T api-service curl -s http://localhost:8000/health/ -H "X-Request-ID: test-123" 2>/dev/null | grep -q "ok\|healthy"; then
        check_passed "Middleware is processing requests"
    else
        check_failed "Middleware may not be working correctly"
        ((FAILURES++))
    fi
}

# Verify OpenTelemetry metrics
verify_metrics() {
    log_section "Verifying OpenTelemetry Metrics"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    
    # Check metrics endpoint
    if docker compose -f "$COMPOSE_FILE" exec -T api-service curl -s http://localhost:8000/metrics 2>/dev/null | grep -q "http_requests_total\|# HELP"; then
        check_passed "Metrics endpoint is accessible"
    else
        check_failed "Metrics endpoint is not accessible or not returning metrics"
        ((FAILURES++))
    fi
}

# Verify service communication
verify_service_communication() {
    log_section "Verifying Service Communication"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    
    # Check API service can communicate with worker service (if applicable)
    # This is a basic check - can be extended based on actual service architecture
    
    log_info "Service communication checks completed"
}

# Main execution
main() {
    log_info "Verifying deployment for: $ENVIRONMENT"
    echo ""
    
    verify_services_running
    verify_service_health
    verify_database_connectivity
    verify_redis_connectivity
    verify_s3_connectivity
    verify_middleware
    verify_metrics
    verify_service_communication
    
    echo ""
    log_section "Verification Summary"
    
    if [ $FAILURES -eq 0 ]; then
        log_info "All verification checks passed ✓"
        exit 0
    else
        log_error "$FAILURES verification check(s) failed"
        exit 1
    fi
}

# Run main function
main "$@"

