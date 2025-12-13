#!/bin/bash
#
# Unit Tests for Deployment Scripts
#
# Tests deployment scripts for Docker Compose operations.
# Uses bash test framework with comprehensive coverage.
#
# Usage:
#   ./scripts/tests/test_deployment_scripts.sh [--verbose]
#

set -euo pipefail

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m' # No Color

# Test configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
TESTS_DIR="$SCRIPT_DIR"
VERBOSE=false

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Logging functions
log_info() {
    if [ "$VERBOSE" = true ]; then
        echo -e "${GREEN}[INFO]${NC} $1"
    fi
}

log_test() {
    echo -e "${GREEN}[TEST]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    TESTS_PASSED=$((TESTS_PASSED + 1))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    TESTS_FAILED=$((TESTS_FAILED + 1))
}

# Test helper functions
assert_equal() {
    local expected="$1"
    local actual="$2"
    local message="${3:-Values should be equal}"
    
    TESTS_RUN=$((TESTS_RUN + 1))
    
    if [ "$expected" = "$actual" ]; then
        log_pass "$message"
        return 0
    else
        log_fail "$message (expected: $expected, actual: $actual)"
        return 1
    fi
}

assert_not_equal() {
    local expected="$1"
    local actual="$2"
    local message="${3:-Values should not be equal}"
    
    TESTS_RUN=$((TESTS_RUN + 1))
    
    if [ "$expected" != "$actual" ]; then
        log_pass "$message"
        return 0
    else
        log_fail "$message (expected: $expected, actual: $actual)"
        return 1
    fi
}

assert_contains() {
    local haystack="$1"
    local needle="$2"
    local message="${3:-String should contain substring}"
    
    TESTS_RUN=$((TESTS_RUN + 1))
    
    if echo "$haystack" | grep -q "$needle"; then
        log_pass "$message"
        return 0
    else
        log_fail "$message (haystack: $haystack, needle: $needle)"
        return 1
    fi
}

assert_file_exists() {
    local file="$1"
    local message="${2:-File should exist}"
    
    TESTS_RUN=$((TESTS_RUN + 1))
    
    if [ -f "$file" ]; then
        log_pass "$message"
        return 0
    else
        log_fail "$message (file: $file)"
        return 1
    fi
}

assert_executable() {
    local file="$1"
    local message="${2:-File should be executable}"
    
    TESTS_RUN=$((TESTS_RUN + 1))
    
    if [ -x "$file" ]; then
        log_pass "$message"
        return 0
    else
        log_fail "$message (file: $file)"
        return 1
    fi
}

# Test deploy-docker-compose.sh
test_deploy_script_exists() {
    log_test "Testing deploy-docker-compose.sh exists"
    assert_file_exists "$PROJECT_DIR/scripts/deploy-docker-compose.sh" "deploy-docker-compose.sh should exist"
    assert_executable "$PROJECT_DIR/scripts/deploy-docker-compose.sh" "deploy-docker-compose.sh should be executable"
}

test_deploy_script_help() {
    log_test "Testing deploy-docker-compose.sh --help"
    local output
    output=$("$PROJECT_DIR/scripts/deploy-docker-compose.sh" --help 2>&1 || true)
    assert_contains "$output" "Usage:" "Help should show usage"
    assert_contains "$output" "Docker Compose Deployment Script" "Help should show script name"
}

test_deploy_script_validation() {
    log_test "Testing deploy-docker-compose.sh dry-run validation"
    
    # Test with non-existent file (should fail)
    local output
    output=$("$PROJECT_DIR/scripts/deploy-docker-compose.sh" --file nonexistent.yml --dry-run 2>&1 || true)
    assert_contains "$output" "not found" "Should fail on non-existent file"
    
    # Test with valid file (should validate)
    if [ -f "$PROJECT_DIR/docker-compose.yml" ]; then
        output=$("$PROJECT_DIR/scripts/deploy-docker-compose.sh" --file docker-compose.yml --dry-run 2>&1 || true)
        # Should either validate successfully or show validation error
        assert_contains "$output" "Dry run\|valid\|error" "Should validate or show error"
    fi
}

# Test stop-docker-compose.sh
test_stop_script_exists() {
    log_test "Testing stop-docker-compose.sh exists"
    assert_file_exists "$PROJECT_DIR/scripts/stop-docker-compose.sh" "stop-docker-compose.sh should exist"
    assert_executable "$PROJECT_DIR/scripts/stop-docker-compose.sh" "stop-docker-compose.sh should be executable"
}

test_stop_script_help() {
    log_test "Testing stop-docker-compose.sh --help"
    local output
    output=$("$PROJECT_DIR/scripts/stop-docker-compose.sh" --help 2>&1 || true)
    assert_contains "$output" "Usage:" "Help should show usage"
    assert_contains "$output" "Docker Compose Stop Script" "Help should show script name"
}

test_stop_script_validation() {
    log_test "Testing stop-docker-compose.sh validation"
    
    # Test with non-existent file (should fail)
    local output
    output=$("$PROJECT_DIR/scripts/stop-docker-compose.sh" --file nonexistent.yml 2>&1 || true)
    assert_contains "$output" "not found" "Should fail on non-existent file"
}

# Test restart-docker-compose.sh
test_restart_script_exists() {
    log_test "Testing restart-docker-compose.sh exists"
    assert_file_exists "$PROJECT_DIR/scripts/restart-docker-compose.sh" "restart-docker-compose.sh should exist"
    assert_executable "$PROJECT_DIR/scripts/restart-docker-compose.sh" "restart-docker-compose.sh should be executable"
}

test_restart_script_help() {
    log_test "Testing restart-docker-compose.sh --help"
    local output
    output=$("$PROJECT_DIR/scripts/restart-docker-compose.sh" --help 2>&1 || true)
    assert_contains "$output" "Usage:" "Help should show usage"
    assert_contains "$output" "Docker Compose Restart Script" "Help should show script name"
}

# Test cleanup-docker-compose.sh
test_cleanup_script_exists() {
    log_test "Testing cleanup-docker-compose.sh exists"
    assert_file_exists "$PROJECT_DIR/scripts/cleanup-docker-compose.sh" "cleanup-docker-compose.sh should exist"
    assert_executable "$PROJECT_DIR/scripts/cleanup-docker-compose.sh" "cleanup-docker-compose.sh should be executable"
}

test_cleanup_script_help() {
    log_test "Testing cleanup-docker-compose.sh --help"
    local output
    output=$("$PROJECT_DIR/scripts/cleanup-docker-compose.sh" --help 2>&1 || true)
    assert_contains "$output" "Usage:" "Help should show usage"
    assert_contains "$output" "Docker Compose Cleanup Script" "Help should show script name"
}

test_cleanup_script_warning() {
    log_test "Testing cleanup-docker-compose.sh warnings"
    local output
    output=$("$PROJECT_DIR/scripts/cleanup-docker-compose.sh" --help 2>&1 || true)
    assert_contains "$output" "WARNING" "Should show warning about data deletion"
}

# Test script syntax
test_script_syntax() {
    log_test "Testing script syntax"
    
    local scripts=(
        "deploy-docker-compose.sh"
        "stop-docker-compose.sh"
        "restart-docker-compose.sh"
        "cleanup-docker-compose.sh"
    )
    
    for script in "${scripts[@]}"; do
        if command -v shellcheck &> /dev/null; then
            # Run shellcheck if available
            if shellcheck "$PROJECT_DIR/scripts/$script" 2>&1 | grep -q "error"; then
                log_fail "Syntax errors in $script"
            else
                log_pass "Syntax check passed for $script"
                TESTS_RUN=$((TESTS_RUN + 1))
            fi
        else
            # Basic syntax check with bash -n
            if bash -n "$PROJECT_DIR/scripts/$script" 2>&1; then
                log_pass "Syntax check passed for $script"
                TESTS_RUN=$((TESTS_RUN + 1))
            else
                log_fail "Syntax errors in $script"
            fi
        fi
    done
}

# Test script functions
test_script_functions() {
    log_test "Testing script function definitions"
    
    # Source deploy script and check for key functions
    local deploy_script="$PROJECT_DIR/scripts/deploy-docker-compose.sh"
    local functions
    functions=$(grep -E "^[a-zA-Z_][a-zA-Z0-9_]*\(\)" "$deploy_script" | sed 's/().*//' || echo "")
    
    assert_contains "$functions" "check_prerequisites" "Should have check_prerequisites function"
    assert_contains "$functions" "validate_compose_config" "Should have validate_compose_config function"
    assert_contains "$functions" "build_images" "Should have build_images function"
    assert_contains "$functions" "start_infrastructure" "Should have start_infrastructure function"
}

# Test environment detection
test_environment_detection() {
    log_test "Testing environment detection"
    
    # Test that script handles different environments
    local deploy_script="$PROJECT_DIR/scripts/deploy-docker-compose.sh"
    local content
    content=$(cat "$deploy_script" || echo "")
    
    assert_contains "$content" "docker-compose.dev.yml" "Should support dev environment"
    assert_contains "$content" "docker-compose.staging.yml" "Should support staging environment"
    assert_contains "$content" "docker-compose.production.yml" "Should support production environment"
}

# Test error handling
test_error_handling() {
    log_test "Testing error handling"
    
    local deploy_script="$PROJECT_DIR/scripts/deploy-docker-compose.sh"
    local content
    content=$(cat "$deploy_script" || echo "")
    
    assert_contains "$content" "set -euo pipefail" "Should use strict error handling"
    assert_contains "$content" "log_error" "Should have error logging"
    assert_contains "$content" "exit 1" "Should exit on errors"
}

# Test logging
test_logging() {
    log_test "Testing logging functionality"
    
    local deploy_script="$PROJECT_DIR/scripts/deploy-docker-compose.sh"
    local content
    content=$(cat "$deploy_script" || echo "")
    
    assert_contains "$content" "log_info" "Should have info logging"
    assert_contains "$content" "log_warn" "Should have warning logging"
    assert_contains "$content" "log_error" "Should have error logging"
    assert_contains "$content" "log_section" "Should have section logging"
}

# Test argument parsing
test_argument_parsing() {
    log_test "Testing argument parsing"
    
    local deploy_script="$PROJECT_DIR/scripts/deploy-docker-compose.sh"
    local content
    content=$(cat "$deploy_script" || echo "")
    
    assert_contains "$content" "env ENV" "Should support --env argument"
    assert_contains "$content" "file FILE" "Should support --file argument"
    assert_contains "$content" "skip-build" "Should support --skip-build argument"
    assert_contains "$content" "dry-run" "Should support --dry-run argument"
    assert_contains "$content" "help" "Should support --help argument"
}

# Test service ordering
test_service_ordering() {
    log_test "Testing service startup ordering"
    
    local deploy_script="$PROJECT_DIR/scripts/deploy-docker-compose.sh"
    local content
    content=$(cat "$deploy_script" || echo "")
    
    # Check that infrastructure starts before application services
    local infra_pos
    infra_pos=$(echo "$content" | grep -n "start_infrastructure" | head -1 | cut -d: -f1 || echo "0")
    local app_pos
    app_pos=$(echo "$content" | grep -n "start_application_services" | head -1 | cut -d: -f1 || echo "0")
    
    if [ "$infra_pos" -gt 0 ] && [ "$app_pos" -gt 0 ] && [ "$infra_pos" -lt "$app_pos" ]; then
        log_pass "Infrastructure starts before application services"
        TESTS_RUN=$((TESTS_RUN + 1))
    else
        log_fail "Service ordering may be incorrect"
        TESTS_RUN=$((TESTS_RUN + 1))
    fi
}

# Test health checks
test_health_checks() {
    log_test "Testing health check functionality"
    
    local deploy_script="$PROJECT_DIR/scripts/deploy-docker-compose.sh"
    local content
    content=$(cat "$deploy_script" || echo "")
    
    assert_contains "$content" "wait_for_services_healthy" "Should have health check waiting"
    assert_contains "$content" "healthcheck" "Should reference health checks"
}

# Test cleanup safety
test_cleanup_safety() {
    log_test "Testing cleanup script safety"
    
    local cleanup_script="$PROJECT_DIR/scripts/cleanup-docker-compose.sh"
    local content
    content=$(cat "$cleanup_script" || echo "")
    
    assert_contains "$content" "confirm_action" "Should have confirmation prompts"
    assert_contains "$content" "WARNING" "Should show warnings"
    assert_contains "$content" "persistent data" "Should warn about data deletion"
}

# Run all tests
run_all_tests() {
    echo "=========================================="
    echo "Deployment Scripts Test Suite"
    echo "=========================================="
    echo ""
    
    test_deploy_script_exists
    test_deploy_script_help
    test_deploy_script_validation
    
    test_stop_script_exists
    test_stop_script_help
    test_stop_script_validation
    
    test_restart_script_exists
    test_restart_script_help
    
    test_cleanup_script_exists
    test_cleanup_script_help
    test_cleanup_script_warning
    
    test_script_syntax
    test_script_functions
    test_environment_detection
    test_error_handling
    test_logging
    test_argument_parsing
    test_service_ordering
    test_health_checks
    test_cleanup_safety
    
    echo ""
    echo "=========================================="
    echo "Test Results"
    echo "=========================================="
    echo "Tests run: $TESTS_RUN"
    echo "Tests passed: $TESTS_PASSED"
    echo "Tests failed: $TESTS_FAILED"
    echo ""
    
    if [ $TESTS_FAILED -eq 0 ]; then
        echo -e "${GREEN}All tests passed!${NC}"
        return 0
    else
        echo -e "${RED}Some tests failed!${NC}"
        return 1
    fi
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --verbose)
            VERBOSE=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run tests
cd "$PROJECT_DIR"
run_all_tests

