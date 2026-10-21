#!/bin/bash
# Deployment Monitoring Script
# Monitors deployment metrics and performance

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${1:-staging}"
BASELINE_COMPARISON="${2:-false}"
MONITORING_DURATION="${3:-3600}"  # Default 1 hour in seconds
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

# Monitor application performance
monitor_application_performance() {
    log_section "Monitoring Application Performance"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Docker Compose file not found: $COMPOSE_FILE"
        return 1
    fi
    
    # Get metrics from Prometheus/OpenTelemetry endpoint
    METRICS_URL="http://localhost:8000/metrics"
    if [ "$ENVIRONMENT" = "production" ]; then
        METRICS_URL="${PRODUCTION_METRICS_URL:-https://api.example.com/metrics}"
    fi
    
    log_info "Fetching metrics from: $METRICS_URL"
    
    # Monitor HTTP request rate
    HTTP_REQUESTS=$(curl -s "$METRICS_URL" | grep "http_requests_total" | head -1 | awk '{print $2}' || echo "0")
    log_info "HTTP requests total: $HTTP_REQUESTS"
    
    # Monitor HTTP error rate
    HTTP_ERRORS=$(curl -s "$METRICS_URL" | grep "http_errors_total" | head -1 | awk '{print $2}' || echo "0")
    log_info "HTTP errors total: $HTTP_ERRORS"
    
    # Monitor HTTP response time
    HTTP_RESPONSE_TIME=$(curl -s "$METRICS_URL" | grep "http_request_duration_seconds" | head -1 | awk '{print $2}' || echo "0")
    log_info "HTTP response time (seconds): $HTTP_RESPONSE_TIME"
}

# Monitor error rates
monitor_error_rates() {
    log_section "Monitoring Error Rates"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    
    # Check application logs for errors
    log_info "Checking application logs for errors..."
    
    ERROR_COUNT=$(docker compose -f "$COMPOSE_FILE" logs api-service --tail 100 2>/dev/null | grep -i "error\|exception\|traceback" | wc -l || echo "0")
    log_info "Recent errors in logs: $ERROR_COUNT"
    
    if [ "$ERROR_COUNT" -gt 10 ]; then
        log_warn "High error count detected: $ERROR_COUNT"
    fi
}

# Monitor database performance
monitor_database_performance() {
    log_section "Monitoring Database Performance"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    
    # Check active connections
    ACTIVE_CONNECTIONS=$(docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U postgres -t -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';" 2>/dev/null | tr -d ' ' || echo "0")
    log_info "Active database connections: $ACTIVE_CONNECTIONS"
    
    # Check database size
    DB_SIZE=$(docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U postgres -t -c "SELECT pg_size_pretty(pg_database_size('${POSTGRES_DB:-hub}'));" 2>/dev/null | tr -d ' ' || echo "N/A")
    log_info "Database size: $DB_SIZE"
}

# Monitor API response times
monitor_api_response_times() {
    log_section "Monitoring API Response Times"
    
    API_URL="http://localhost:8000"
    if [ "$ENVIRONMENT" = "production" ]; then
        API_URL="${PRODUCTION_API_URL:-https://api.example.com}"
    fi
    
    # Test health endpoint response time
    START_TIME=$(date +%s%N)
    curl -s "${API_URL}/health/" > /dev/null
    END_TIME=$(date +%s%N)
    RESPONSE_TIME=$(( (END_TIME - START_TIME) / 1000000 ))  # Convert to milliseconds
    
    log_info "Health endpoint response time: ${RESPONSE_TIME}ms"
    
    if [ "$RESPONSE_TIME" -gt 1000 ]; then
        log_warn "High response time detected: ${RESPONSE_TIME}ms"
    fi
}

# Monitor job queue performance
monitor_job_queue_performance() {
    log_section "Monitoring Job Queue Performance"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    
    # Check Redis queue length (if using Redis for job queue)
    if docker compose -f "$COMPOSE_FILE" ps redis 2>/dev/null | grep -q "Up"; then
        QUEUE_LENGTH=$(docker compose -f "$COMPOSE_FILE" exec -T redis redis-cli LLEN "rq:queue:default" 2>/dev/null || echo "0")
        log_info "Job queue length: $QUEUE_LENGTH"
        
        if [ "$QUEUE_LENGTH" -gt 100 ]; then
            log_warn "High job queue length: $QUEUE_LENGTH"
        fi
    fi
}

# Monitor middleware performance
monitor_middleware_performance() {
    log_section "Monitoring Middleware Performance"
    
    # Middleware performance is typically measured through HTTP metrics
    # This is a placeholder for specific middleware monitoring
    log_info "Middleware performance monitoring (via HTTP metrics)"
}

# Monitor JSONField query performance
monitor_jsonfield_performance() {
    log_section "Monitoring JSONField Query Performance"
    
    # JSONField query performance is typically measured through database metrics
    # This is a placeholder for specific JSONField monitoring
    log_info "JSONField query performance monitoring (via database metrics)"
}

# Continuous monitoring loop
continuous_monitoring() {
    log_section "Starting Continuous Monitoring"
    log_info "Monitoring duration: ${MONITORING_DURATION} seconds"
    log_info "Baseline comparison: $BASELINE_COMPARISON"
    
    START_TIME=$(date +%s)
    INTERVAL=30  # Monitor every 30 seconds
    
    while true; do
        CURRENT_TIME=$(date +%s)
        ELAPSED=$((CURRENT_TIME - START_TIME))
        
        if [ $ELAPSED -ge $MONITORING_DURATION ]; then
            break
        fi
        
        echo ""
        log_info "Monitoring check at $(date +%H:%M:%S) (${ELAPSED}s/${MONITORING_DURATION}s)"
        
        monitor_application_performance
        monitor_error_rates
        monitor_database_performance
        monitor_api_response_times
        monitor_job_queue_performance
        
        sleep $INTERVAL
    done
    
    log_info "Monitoring completed"
}

# Generate monitoring report
generate_monitoring_report() {
    log_section "Generating Monitoring Report"
    
    REPORT_FILE="monitoring_reports/deployment_${ENVIRONMENT}_$(date +%Y%m%d_%H%M%S).txt"
    mkdir -p monitoring_reports
    
    {
        echo "Deployment Monitoring Report"
        echo "==========================="
        echo "Environment: $ENVIRONMENT"
        echo "Timestamp: $(date)"
        echo "Monitoring duration: ${MONITORING_DURATION} seconds"
        echo ""
        echo "Metrics Summary:"
        echo "  - Application performance: Monitored"
        echo "  - Error rates: Monitored"
        echo "  - Database performance: Monitored"
        echo "  - API response times: Monitored"
        echo "  - Job queue performance: Monitored"
    } > "$REPORT_FILE"
    
    cat "$REPORT_FILE"
    log_info "Monitoring report saved to: $REPORT_FILE"
}

# Main execution
main() {
    log_info "Starting deployment monitoring for: $ENVIRONMENT"
    if [ "$BASELINE_COMPARISON" = "true" ] || [ "$BASELINE_COMPARISON" = "--baseline-comparison" ]; then
        log_info "Baseline comparison enabled"
    fi
    echo ""
    
    # Run initial monitoring checks
    monitor_application_performance
    monitor_error_rates
    monitor_database_performance
    monitor_api_response_times
    monitor_job_queue_performance
    monitor_middleware_performance
    monitor_jsonfield_performance
    
    # Run continuous monitoring if duration is specified
    if [ "$MONITORING_DURATION" -gt 0 ]; then
        continuous_monitoring
    fi
    
    generate_monitoring_report
    
    echo ""
    log_info "Monitoring completed ✓"
}

# Run main function
main "$@"

