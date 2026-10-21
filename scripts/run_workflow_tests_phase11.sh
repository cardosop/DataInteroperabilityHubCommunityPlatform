#!/bin/bash
# Script to run Phase 11 workflow tests systematically
# Runs tests in cycles: test → evaluate → fix → repeat

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if docker compose is available
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif docker compose version &> /dev/null 2>&1; then
    DOCKER_COMPOSE="docker compose"
else
    echo -e "${RED}Error: docker-compose or docker compose not found${NC}"
    exit 1
fi

# Check if api-service is running
if ! $DOCKER_COMPOSE ps api-service | grep -q "Up"; then
    echo -e "${RED}Error: api-service is not running. Please start services with: $DOCKER_COMPOSE up -d${NC}"
    exit 1
fi

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Phase 11 Workflow Test Runner${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Test files to run (Phase 4 Integration Tests)
PHASE4_TESTS=(
    "hub/apps/orchestration/tests/test_workflow_business_rules_integration.py"
    "hub/apps/orchestration/tests/test_workflow_task_business_rules_integration.py"
    "hub/apps/orchestration/tests/test_product_creation_workflow.py"
    "hub/apps/orchestration/tests/test_odps_workflow_events.py"
)

# Test files to run (Phase 6 E2E Tests)
PHASE6_TESTS=(
    "tests/e2e/test_contract_first_comprehensive.py"
    "tests/e2e/test_data_first_comprehensive.py"
    "tests/e2e/test_odps_journeys_comprehensive.py"
    "tests/e2e/test_asset_operations.py"
    "tests/e2e/test_dataset_operations.py"
    "tests/e2e/test_marketplace_comprehensive.py"
    "tests/e2e/test_scheduled_ingestion.py"
    "tests/e2e/test_job_orchestration.py"
)

# Function to run tests with timeout
run_test_file() {
    local test_file=$1
    local phase=$2
    local timeout_seconds=${3:-300}
    
    echo -e "${YELLOW}Running $phase test: $test_file${NC}"
    
    # Check if file exists
    if [ ! -f "$test_file" ]; then
        echo -e "${RED}  ✗ Test file not found: $test_file${NC}"
        return 1
    fi
    
    # Run test with timeout
    local result
    result=$(timeout $timeout_seconds $DOCKER_COMPOSE exec -T api-service bash -c "cd /app && python -m pytest '$test_file' -v --tb=short --maxfail=1" 2>&1)
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}  ✓ Test passed: $test_file${NC}"
        return 0
    elif [ $exit_code -eq 124 ]; then
        echo -e "${RED}  ✗ Test timed out after ${timeout_seconds}s: $test_file${NC}"
        echo "$result" | tail -50
        return 1
    else
        echo -e "${RED}  ✗ Test failed: $test_file${NC}"
        echo "$result" | tail -100
        return 1
    fi
}

# Function to run Phase 4 tests
run_phase4_tests() {
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Phase 4: Integration Tests${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    
    local failed_tests=()
    local passed_tests=()
    
    for test_file in "${PHASE4_TESTS[@]}"; do
        if run_test_file "$test_file" "Phase 4" 300; then
            passed_tests+=("$test_file")
        else
            failed_tests+=("$test_file")
        fi
        echo ""
    done
    
    echo -e "${GREEN}Phase 4 Summary:${NC}"
    echo -e "  Passed: ${#passed_tests[@]}"
    echo -e "  Failed: ${#failed_tests[@]}"
    
    if [ ${#failed_tests[@]} -gt 0 ]; then
        echo -e "${RED}Failed tests:${NC}"
        for test in "${failed_tests[@]}"; do
            echo -e "  - $test"
        done
        return 1
    fi
    
    return 0
}

# Function to run Phase 6 tests
run_phase6_tests() {
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Phase 6: E2E Tests${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo ""
    
    local failed_tests=()
    local passed_tests=()
    
    for test_file in "${PHASE6_TESTS[@]}"; do
        if run_test_file "$test_file" "Phase 6" 600; then
            passed_tests+=("$test_file")
        else
            failed_tests+=("$test_file")
        fi
        echo ""
    done
    
    echo -e "${GREEN}Phase 6 Summary:${NC}"
    echo -e "  Passed: ${#passed_tests[@]}"
    echo -e "  Failed: ${#failed_tests[@]}"
    
    if [ ${#failed_tests[@]} -gt 0 ]; then
        echo -e "${RED}Failed tests:${NC}"
        for test in "${failed_tests[@]}"; do
            echo -e "  - $test"
        done
        return 1
    fi
    
    return 0
}

# Main execution
main() {
    local phase=${1:-"all"}
    
    case $phase in
        phase4)
            run_phase4_tests
            ;;
        phase6)
            run_phase6_tests
            ;;
        all|*)
            echo "Running all tests..."
            run_phase4_tests
            phase4_result=$?
            
            if [ $phase4_result -eq 0 ]; then
                run_phase6_tests
                phase6_result=$?
                
                if [ $phase6_result -eq 0 ]; then
                    echo -e "${GREEN}========================================${NC}"
                    echo -e "${GREEN}All tests passed!${NC}"
                    echo -e "${GREEN}========================================${NC}"
                    exit 0
                else
                    echo -e "${RED}Phase 6 tests failed${NC}"
                    exit 1
                fi
            else
                echo -e "${RED}Phase 4 tests failed, skipping Phase 6${NC}"
                exit 1
            fi
            ;;
    esac
}

main "$@"
