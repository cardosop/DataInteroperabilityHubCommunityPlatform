#!/bin/bash
# Script to run Docker Compose integration tests
#
# This script:
# 1. Starts Docker Compose services
# 2. Waits for services to be healthy
# 3. Runs integration tests
# 4. Cleans up services
#
# Usage:
#   ./scripts/run_docker_compose_integration_tests.sh [--keep-services] [--services SERVICE1,SERVICE2]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default options
KEEP_SERVICES=false
SERVICES_TO_START=""
TEST_MARKER="integration"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --keep-services)
            KEEP_SERVICES=true
            shift
            ;;
        --services)
            SERVICES_TO_START="$2"
            shift 2
            ;;
        --marker)
            TEST_MARKER="$2"
            shift 2
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--keep-services] [--services SERVICE1,SERVICE2] [--marker MARKER]"
            exit 1
            ;;
    esac
done

# Function to print colored output
print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if Docker Compose is available
check_docker_compose() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    if ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not available"
        exit 1
    fi
}

# Function to wait for service to be healthy
wait_for_service_healthy() {
    local service_name=$1
    local timeout=${2:-300}
    local elapsed=0
    
    print_info "Waiting for $service_name to be healthy..."
    
    while [ $elapsed -lt $timeout ]; do
        if docker compose ps --format json "$service_name" | grep -q '"Health":"healthy"'; then
            print_info "$service_name is healthy"
            return 0
        fi
        
        # Check if service is running (even if not healthy yet)
        local state=$(docker compose ps --format json "$service_name" | grep -o '"State":"[^"]*"' | cut -d'"' -f4)
        if [ "$state" != "running" ]; then
            print_error "$service_name is not running (state: $state)"
            docker compose logs --tail=50 "$service_name"
            return 1
        fi
        
        sleep 2
        elapsed=$((elapsed + 2))
    done
    
    print_error "$service_name failed to become healthy within ${timeout}s"
    docker compose logs --tail=100 "$service_name"
    return 1
}

# Function to start services
start_services() {
    print_info "Starting Docker Compose services..."
    
    if [ -n "$SERVICES_TO_START" ]; then
        # Start specific services
        IFS=',' read -ra SERVICES <<< "$SERVICES_TO_START"
        docker compose up -d "${SERVICES[@]}"
        
        # Wait for each service
        for service in "${SERVICES[@]}"; do
            wait_for_service_healthy "$service"
        done
    else
        # Start infrastructure services first
        print_info "Starting infrastructure services..."
        docker compose up -d postgres redis minio fuseki
        
        # Wait for infrastructure
        wait_for_service_healthy "postgres"
        wait_for_service_healthy "redis"
        
        # Start application services
        print_info "Starting application services..."
        docker compose up -d \
            workflow-engine-service \
            workflow-registry-service \
            event-bus-health-service \
            event-schema-registry-service \
            api-service \
            worker-service
        
        # Wait for application services
        wait_for_service_healthy "workflow-engine-service"
        wait_for_service_healthy "workflow-registry-service"
        wait_for_service_healthy "event-bus-health-service"
        wait_for_service_healthy "event-schema-registry-service"
    fi
    
    print_info "All services are healthy"
}

# Function to stop services
stop_services() {
    if [ "$KEEP_SERVICES" = true ]; then
        print_info "Keeping services running (--keep-services flag set)"
        return
    fi
    
    print_info "Stopping Docker Compose services..."
    docker compose down -v || true
    print_info "Services stopped"
}

# Function to run tests
run_tests() {
    print_info "Running Docker Compose integration tests..."
    
    # Set environment variables for pytest
    export PYTEST_DOCKER_COMPOSE_RUNTIME=1
    export SKIP_DJANGO_SETUP=1
    # Unset DJANGO_SETTINGS_MODULE to prevent pytest-django from loading Django
    unset DJANGO_SETTINGS_MODULE
    
    # Run tests with coverage
    pytest \
        tests/integration/test_docker_compose_deployment.py \
        -v \
        --tb=short \
        -m "integration and docker_compose_runtime" \
        --cov=tests.integration.test_docker_compose_deployment \
        --cov-report=term-missing \
        --cov-report=html:tests/integration/coverage_html \
        --cov-fail-under=95 \
        "$@"
    
    local exit_code=$?
    
    if [ $exit_code -eq 0 ]; then
        print_info "All tests passed!"
    else
        print_error "Some tests failed (exit code: $exit_code)"
    fi
    
    return $exit_code
}

# Main execution
main() {
    print_info "Starting Docker Compose integration test runner"
    
    # Check prerequisites
    check_docker_compose
    
    # Trap to ensure cleanup
    trap 'stop_services' EXIT
    
    # Start services
    start_services
    
    # Run tests
    run_tests
    local test_exit_code=$?
    
    # Cleanup (handled by trap, but explicit for clarity)
    stop_services
    
    exit $test_exit_code
}

# Run main function
main "$@"

