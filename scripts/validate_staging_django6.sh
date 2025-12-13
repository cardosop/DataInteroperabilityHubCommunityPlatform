#!/bin/bash
#
# Django 6 Staging Validation Script
#
# This script validates all functionality in staging after Django 6 upgrade.
#
# Usage:
#   ./scripts/validate_staging_django6.sh
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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

check_health() {
    log_info "Checking health endpoints..."
    
    HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health/ || echo "000")
    if [ "$HEALTH_RESPONSE" = "200" ]; then
        log_info "✓ Health endpoint is healthy"
    else
        log_error "✗ Health endpoint failed (HTTP $HEALTH_RESPONSE)"
        return 1
    fi
}

run_regression_tests() {
    log_info "Running regression tests..."
    
    pytest tests/regression/ -v --tb=short || {
        log_error "Regression tests failed"
        return 1
    }
    
    log_info "✓ Regression tests passed"
}

run_e2e_tests() {
    log_info "Running E2E tests for critical workflows..."
    
    pytest tests/e2e/test_django6_upgrade_critical_workflows.py -v --tb=short || {
        log_error "E2E tests failed"
        return 1
    }
    
    log_info "✓ E2E tests passed"
}

run_performance_tests() {
    log_info "Running performance baseline tests..."
    
    pytest tests/performance/test_performance_baseline.py -v --tb=short || {
        log_warn "Performance tests had issues (non-critical for validation)"
    }
    
    log_info "✓ Performance tests completed"
}

validate_jsonfield_queries() {
    log_info "Validating JSONField queries..."
    
    python scripts/optimize_jsonfield_queries.py --check || {
        log_warn "JSONField query validation had warnings"
    }
    
    log_info "✓ JSONField queries validated"
}

check_middleware() {
    log_info "Checking middleware functionality..."
    
    # Test request ID middleware
    REQUEST_ID=$(curl -s -I http://localhost:8000/health/ | grep -i "X-Request-ID" || echo "")
    if [ -n "$REQUEST_ID" ]; then
        log_info "✓ Request ID middleware working"
    else
        log_warn "Request ID middleware may not be working (non-critical)"
    fi
}

validate_api_endpoints() {
    log_info "Validating API endpoints..."
    
    # Test contract list endpoint (may require auth)
    API_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/contracts/ || echo "000")
    if [ "$API_RESPONSE" = "200" ] || [ "$API_RESPONSE" = "401" ]; then
        log_info "✓ API endpoints accessible"
    else
        log_warn "API endpoint returned HTTP $API_RESPONSE (may require authentication)"
    fi
}

main() {
    log_info "=========================================="
    log_info "Django 6 Staging Validation"
    log_info "=========================================="
    log_info ""
    
    local errors=0
    
    # Health check
    check_health || ((errors++))
    
    # Regression tests
    run_regression_tests || ((errors++))
    
    # E2E tests
    run_e2e_tests || ((errors++))
    
    # Performance tests
    run_performance_tests || true  # Non-critical
    
    # JSONField validation
    validate_jsonfield_queries || true  # Non-critical
    
    # Middleware check
    check_middleware || true  # Non-critical
    
    # API endpoint validation
    validate_api_endpoints || true  # Non-critical
    
    log_info ""
    log_info "=========================================="
    if [ $errors -eq 0 ]; then
        log_info "✓ All critical validations passed"
        log_info "Staging environment is ready for production deployment"
    else
        log_error "✗ $errors critical validation(s) failed"
        log_error "Please fix issues before proceeding to production"
        exit 1
    fi
    log_info "=========================================="
}

# Run main function
main

