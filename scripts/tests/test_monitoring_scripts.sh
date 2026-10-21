#!/bin/bash
#
# Unit Tests for Monitoring Scripts
#
# Tests monitoring scripts for services, workflows, and event bus.
#
# Usage:
#   ./scripts/tests/test_monitoring_scripts.sh [--verbose]
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
    
    if echo "$haystack" | grep -q -- "$needle"; then
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

# Test monitor-services.sh
test_monitor_services_script_exists() {
    log_test "Testing monitor-services.sh exists"
    assert_file_exists "$PROJECT_DIR/scripts/monitor-services.sh" "monitor-services.sh should exist"
    assert_executable "$PROJECT_DIR/scripts/monitor-services.sh" "monitor-services.sh should be executable"
}

test_monitor_services_script_help() {
    log_test "Testing monitor-services.sh --help"
    local output
    output=$("$PROJECT_DIR/scripts/monitor-services.sh" --help 2>&1 || true)
    assert_contains "$output" "Usage:" "Help should show usage"
    assert_contains "$output" "Service Monitoring Script" "Help should show script name"
}

test_monitor_services_script_options() {
    log_test "Testing monitor-services.sh options"
    local script="$PROJECT_DIR/scripts/monitor-services.sh"
    local content
    content=$(cat "$script" || echo "")
    
    assert_contains "$content" "env ENV" "Should support --env option"
    assert_contains "$content" "format FORMAT" "Should support --format option"
    assert_contains "$content" "prometheus-url" "Should support --prometheus-url option"
    assert_contains "$content" "services SERVICES" "Should support --services option"
    assert_contains "$content" "watch" "Should support --watch option"
}

# Test monitor-workflows.sh
test_monitor_workflows_script_exists() {
    log_test "Testing monitor-workflows.sh exists"
    assert_file_exists "$PROJECT_DIR/scripts/monitor-workflows.sh" "monitor-workflows.sh should exist"
    assert_executable "$PROJECT_DIR/scripts/monitor-workflows.sh" "monitor-workflows.sh should be executable"
}

test_monitor_workflows_script_help() {
    log_test "Testing monitor-workflows.sh --help"
    local output
    output=$("$PROJECT_DIR/scripts/monitor-workflows.sh" --help 2>&1 || true)
    assert_contains "$output" "Usage:" "Help should show usage"
    assert_contains "$output" "Workflow Monitoring Script" "Help should show script name"
}

test_monitor_workflows_script_options() {
    log_test "Testing monitor-workflows.sh options"
    local script="$PROJECT_DIR/scripts/monitor-workflows.sh"
    local content
    content=$(cat "$script" || echo "")
    
    assert_contains "$content" "workflow-name" "Should support --workflow-name option"
    assert_contains "$content" "workflow_instances_running" "Should query workflow metrics"
    assert_contains "$content" "workflow_execution_duration" "Should query workflow duration"
}

# Test monitor-event-bus.sh
test_monitor_event_bus_script_exists() {
    log_test "Testing monitor-event-bus.sh exists"
    assert_file_exists "$PROJECT_DIR/scripts/monitor-event-bus.sh" "monitor-event-bus.sh should exist"
    assert_executable "$PROJECT_DIR/scripts/monitor-event-bus.sh" "monitor-event-bus.sh should be executable"
}

test_monitor_event_bus_script_help() {
    log_test "Testing monitor-event-bus.sh --help"
    local output
    output=$("$PROJECT_DIR/scripts/monitor-event-bus.sh" --help 2>&1 || true)
    assert_contains "$output" "Usage:" "Help should show usage"
    assert_contains "$output" "Event Bus Monitoring Script" "Help should show script name"
}

test_monitor_event_bus_script_options() {
    log_test "Testing monitor-event-bus.sh options"
    local script="$PROJECT_DIR/scripts/monitor-event-bus.sh"
    local content
    content=$(cat "$script" || echo "")
    
    assert_contains "$content" "event-type" "Should support --event-type option"
    assert_contains "$content" "event_published_total" "Should query event publish metrics"
    assert_contains "$content" "event_dlq_size" "Should query DLQ metrics"
}

# Test script syntax
test_script_syntax() {
    log_test "Testing script syntax"
    
    local scripts=(
        "monitor-services.sh"
        "monitor-workflows.sh"
        "monitor-event-bus.sh"
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
    
    # Test monitor-services.sh functions
    local services_script="$PROJECT_DIR/scripts/monitor-services.sh"
    local services_content
    services_content=$(cat "$services_script" || echo "")
    
    assert_contains "$services_content" "check_service_health" "Should have check_service_health function"
    assert_contains "$services_content" "get_container_status" "Should have get_container_status function"
    assert_contains "$services_content" "query_prometheus" "Should have query_prometheus function"
    
    # Test monitor-workflows.sh functions
    local workflows_script="$PROJECT_DIR/scripts/monitor-workflows.sh"
    local workflows_content
    workflows_content=$(cat "$workflows_script" || echo "")
    
    assert_contains "$workflows_content" "get_workflow_metrics" "Should have get_workflow_metrics function"
    assert_contains "$workflows_content" "check_workflow_engine_status" "Should have check_workflow_engine_status function"
    
    # Test monitor-event-bus.sh functions
    local event_bus_script="$PROJECT_DIR/scripts/monitor-event-bus.sh"
    local event_bus_content
    event_bus_content=$(cat "$event_bus_script" || echo "")
    
    assert_contains "$event_bus_content" "get_event_bus_metrics" "Should have get_event_bus_metrics function"
    assert_contains "$event_bus_content" "check_event_bus_status" "Should have check_event_bus_status function"
}

# Test error handling
test_error_handling() {
    log_test "Testing error handling"
    
    local scripts=(
        "monitor-services.sh"
        "monitor-workflows.sh"
        "monitor-event-bus.sh"
    )
    
    for script in "${scripts[@]}"; do
        local script_path="$PROJECT_DIR/scripts/$script"
        local content
        content=$(cat "$script_path" || echo "")
        
        assert_contains "$content" "set -euo pipefail" "Should use strict error handling"
        assert_contains "$content" "log_error" "Should have error logging"
    done
}

# Test output formats
test_output_formats() {
    log_test "Testing output format support"
    
    local scripts=(
        "monitor-services.sh"
        "monitor-workflows.sh"
        "monitor-event-bus.sh"
    )
    
    for script in "${scripts[@]}"; do
        local script_path="$PROJECT_DIR/scripts/$script"
        local content
        content=$(cat "$script_path" || echo "")
        
        assert_contains "$content" "--format" "Should support --format option"
        assert_contains "$content" "OUTPUT_FORMAT" "Should have OUTPUT_FORMAT variable"
        assert_contains "$content" "json" "Should support JSON output"
        assert_contains "$content" "text" "Should support text output"
    done
}

# Test Prometheus integration
test_prometheus_integration() {
    log_test "Testing Prometheus integration"
    
    local scripts=(
        "monitor-services.sh"
        "monitor-workflows.sh"
        "monitor-event-bus.sh"
    )
    
    for script in "${scripts[@]}"; do
        local script_path="$PROJECT_DIR/scripts/$script"
        local content
        content=$(cat "$script_path" || echo "")
        
        assert_contains "$content" "--prometheus-url" "Should support --prometheus-url option"
        assert_contains "$content" "query_prometheus" "Should have Prometheus query function"
        assert_contains "$content" "/api/v1/query" "Should use Prometheus API"
    done
}

# Test environment detection
test_environment_detection() {
    log_test "Testing environment detection"
    
    local scripts=(
        "monitor-services.sh"
        "monitor-workflows.sh"
        "monitor-event-bus.sh"
    )
    
    for script in "${scripts[@]}"; do
        local script_path="$PROJECT_DIR/scripts/$script"
        local content
        content=$(cat "$script_path" || echo "")
        
        assert_contains "$content" "docker-compose.dev.yml" "Should support dev environment"
        assert_contains "$content" "docker-compose.staging.yml" "Should support staging environment"
        assert_contains "$content" "docker-compose.production.yml" "Should support production environment"
    done
}

# Run all tests
run_all_tests() {
    echo "=========================================="
    echo "Monitoring Scripts Test Suite"
    echo "=========================================="
    echo ""
    
    test_monitor_services_script_exists
    test_monitor_services_script_help
    test_monitor_services_script_options
    
    test_monitor_workflows_script_exists
    test_monitor_workflows_script_help
    test_monitor_workflows_script_options
    
    test_monitor_event_bus_script_exists
    test_monitor_event_bus_script_help
    test_monitor_event_bus_script_options
    
    test_script_syntax
    test_script_functions
    test_error_handling
    test_output_formats
    test_prometheus_integration
    test_environment_detection
    
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

