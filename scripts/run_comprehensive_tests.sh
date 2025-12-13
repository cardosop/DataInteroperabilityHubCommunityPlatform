#!/bin/bash
# Comprehensive Test Execution Script
# Runs all test suites for deployment verification

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${1:-staging}"
TEST_TYPE="${2:-all}"
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

# Track test results
TEST_RESULTS=()
TEST_FAILURES=0

# Run unit tests
run_unit_tests() {
    log_section "Running Unit Tests"
    
    if [ -d "tests/unit" ]; then
        log_info "Running unit tests..."
        if python -m pytest tests/unit/ -v --tb=short 2>&1 | tee /tmp/unit_tests.log; then
            log_info "✓ Unit tests passed"
            TEST_RESULTS+=("unit:passed")
        else
            log_error "✗ Unit tests failed"
            TEST_RESULTS+=("unit:failed")
            ((TEST_FAILURES++))
        fi
    else
        log_warn "Unit tests directory not found"
    fi
}

# Run integration tests
run_integration_tests() {
    log_section "Running Integration Tests"
    
    if [ -d "tests/integration" ]; then
        log_info "Running integration tests..."
        if python -m pytest tests/integration/ -v --tb=short 2>&1 | tee /tmp/integration_tests.log; then
            log_info "✓ Integration tests passed"
            TEST_RESULTS+=("integration:passed")
        else
            log_error "✗ Integration tests failed"
            TEST_RESULTS+=("integration:failed")
            ((TEST_FAILURES++))
        fi
    else
        log_warn "Integration tests directory not found"
    fi
}

# Run E2E tests
run_e2e_tests() {
    log_section "Running E2E Tests"
    
    if [ -d "tests/e2e" ]; then
        log_info "Running E2E tests..."
        if python -m pytest tests/e2e/ -v --tb=short 2>&1 | tee /tmp/e2e_tests.log; then
            log_info "✓ E2E tests passed"
            TEST_RESULTS+=("e2e:passed")
        else
            log_error "✗ E2E tests failed"
            TEST_RESULTS+=("e2e:failed")
            ((TEST_FAILURES++))
        fi
    else
        log_warn "E2E tests directory not found"
    fi
}

# Run regression tests
run_regression_tests() {
    log_section "Running Regression Tests"
    
    if [ -d "tests/regression" ]; then
        log_info "Running regression tests..."
        if python -m pytest tests/regression/ -v --tb=short 2>&1 | tee /tmp/regression_tests.log; then
            log_info "✓ Regression tests passed"
            TEST_RESULTS+=("regression:passed")
        else
            log_error "✗ Regression tests failed"
            TEST_RESULTS+=("regression:failed")
            ((TEST_FAILURES++))
        fi
    else
        log_warn "Regression tests directory not found"
    fi
}

# Run security tests
run_security_tests() {
    log_section "Running Security Tests"
    
    if [ -d "tests/security" ]; then
        log_info "Running security tests..."
        if python -m pytest tests/security/ -v --tb=short 2>&1 | tee /tmp/security_tests.log; then
            log_info "✓ Security tests passed"
            TEST_RESULTS+=("security:passed")
        else
            log_error "✗ Security tests failed"
            TEST_RESULTS+=("security:failed")
            ((TEST_FAILURES++))
        fi
    else
        log_warn "Security tests directory not found"
    fi
}

# Run performance tests
run_performance_tests() {
    log_section "Running Performance Tests"
    
    if [ -d "tests/performance" ]; then
        log_info "Running performance tests..."
        if python -m pytest tests/performance/ -v --tb=short 2>&1 | tee /tmp/performance_tests.log; then
            log_info "✓ Performance tests passed"
            TEST_RESULTS+=("performance:passed")
        else
            log_error "✗ Performance tests failed"
            TEST_RESULTS+=("performance:failed")
            ((TEST_FAILURES++))
        fi
    else
        log_warn "Performance tests directory not found"
    fi
}

# Generate test report
generate_test_report() {
    log_section "Test Report"
    
    REPORT_FILE="test_reports/comprehensive_${ENVIRONMENT}_$(date +%Y%m%d_%H%M%S).txt"
    mkdir -p test_reports
    
    {
        echo "Comprehensive Test Report"
        echo "========================"
        echo "Environment: $ENVIRONMENT"
        echo "Timestamp: $(date)"
        echo ""
        echo "Test Results:"
        for RESULT in "${TEST_RESULTS[@]}"; do
            TYPE=$(echo "$RESULT" | cut -d: -f1)
            STATUS=$(echo "$RESULT" | cut -d: -f2)
            echo "  - $TYPE: $STATUS"
        done
        echo ""
        echo "Summary:"
        echo "  Total test suites: ${#TEST_RESULTS[@]}"
        echo "  Failed test suites: $TEST_FAILURES"
        echo "  Passed test suites: $((${#TEST_RESULTS[@]} - TEST_FAILURES))"
    } > "$REPORT_FILE"
    
    cat "$REPORT_FILE"
    log_info "Test report saved to: $REPORT_FILE"
}

# Main execution
main() {
    log_info "Running comprehensive tests for: $ENVIRONMENT"
    log_info "Test type: $TEST_TYPE"
    echo ""
    
    case "$TEST_TYPE" in
        unit)
            run_unit_tests
            ;;
        integration)
            run_integration_tests
            ;;
        e2e)
            run_e2e_tests
            ;;
        regression)
            run_regression_tests
            ;;
        security)
            run_security_tests
            ;;
        performance)
            run_performance_tests
            ;;
        all)
            run_unit_tests
            run_integration_tests
            run_e2e_tests
            run_regression_tests
            run_security_tests
            run_performance_tests
            ;;
        *)
            log_error "Unknown test type: $TEST_TYPE"
            log_info "Available types: unit, integration, e2e, regression, security, performance, all"
            exit 1
            ;;
    esac
    
    generate_test_report
    
    echo ""
    if [ $TEST_FAILURES -eq 0 ]; then
        log_info "All tests passed ✓"
        exit 0
    else
        log_error "$TEST_FAILURES test suite(s) failed"
        exit 1
    fi
}

# Run main function
main "$@"
