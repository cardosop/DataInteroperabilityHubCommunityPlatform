#!/bin/bash
# Run Performance Tests Against Staging Environment
# This script runs performance tests and documents results

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
API_URL="${API_URL:-http://localhost:8001}"
RESULTS_DIR="${RESULTS_DIR:-performance-test-results}"
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

wait_for_services() {
    log_info "Waiting for staging services to be ready..."
    
    local max_attempts=120
    local attempt=0
    
    while [ $attempt -lt $max_attempts ]; do
        if curl -f "$API_URL/health/" &> /dev/null; then
            log_info "API service is ready"
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        log_error "API service failed to become ready"
        exit 1
    fi
}

run_performance_tests() {
    log_info "Running performance tests..."
    
    # Create results directory
    mkdir -p "$RESULTS_DIR"
    
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local results_file="$RESULTS_DIR/performance-results-$timestamp.json"
    
    # Set environment variables
    export API_BASE_URL="$API_URL"
    export STAGING_ENV=true
    export PERFORMANCE_TEST=true
    
    # Run pytest performance tests
    log_info "Running pytest performance tests..."
    pytest tests/performance/ -v --tb=short --json-report --json-report-file="$results_file" || true
    
    log_info "Performance test results saved to $results_file"
}

verify_performance_targets() {
    log_info "Verifying performance targets..."
    
    # Performance targets
    local targets=(
        "P95_LATENCY_MS:500"
        "ERROR_RATE_PERCENT:1"
        "THROUGHPUT_RPS:100"
    )
    
    log_info "Performance targets:"
    for target in "${targets[@]}"; do
        local name="${target%%:*}"
        local value="${target##*:}"
        log_info "  $name: $value"
    done
    
    log_warn "Manual verification required. Check test results for actual values."
}

document_results() {
    log_info "Documenting performance test results..."
    
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local doc_file="$RESULTS_DIR/performance-report-$timestamp.md"
    
    cat > "$doc_file" << EOF
# Performance Test Results

**Date**: $(date)
**Environment**: Staging
**API URL**: $API_URL

## Test Execution

- **Test Suite**: pytest performance tests
- **Results Directory**: $RESULTS_DIR

## Performance Targets

- **P95 Latency**: < 500ms
- **Error Rate**: < 1%
- **Throughput**: > 100 RPS

## Results

See JSON results file for detailed metrics.

## Notes

- Tests run against staging environment
- Results may vary based on environment load
- Production targets may differ

EOF
    
    log_info "Performance test report saved to $doc_file"
}

# Main execution
main() {
    log_info "Running performance tests against staging: $API_URL"
    
    wait_for_services
    run_performance_tests
    verify_performance_targets
    document_results
    
    log_info "Performance testing completed!"
    log_info "Results available in: $RESULTS_DIR"
}

# Run main function
main "$@"

