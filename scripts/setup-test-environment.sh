#!/bin/bash
# Comprehensive Test Environment Setup Script
# This script sets up the complete test environment with all required services
# Usage: ./scripts/setup-test-environment.sh [start|stop|restart|status|logs|clean]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

COMPOSE_FILE="docker-compose.test.yml"
ENV_FILE=".env.test"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

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
    if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
        print_error "Docker Compose is not installed or not available"
        exit 1
    fi
    
    if docker compose version &> /dev/null; then
        COMPOSE_CMD="docker compose"
    else
        COMPOSE_CMD="docker-compose"
    fi
}

# Function to check if .env.test exists
check_env_file() {
    if [ ! -f "$ENV_FILE" ]; then
        print_warn ".env.test file not found. Creating from .env.test.example..."
        if [ -f ".env.test.example" ]; then
            cp .env.test.example "$ENV_FILE"
            print_info "Created .env.test from .env.test.example"
            print_warn "Please review and customize .env.test if needed"
        else
            print_error ".env.test.example not found. Please create .env.test manually"
            exit 1
        fi
    fi
}

# Function to wait for service health
wait_for_service() {
    local service=$1
    local max_attempts=30
    local attempt=1
    
    print_info "Waiting for $service to be healthy..."
    
    while [ $attempt -le $max_attempts ]; do
        if $COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps "$service" | grep -q "healthy"; then
            print_info "$service is healthy"
            return 0
        fi
        
        if [ $attempt -eq $max_attempts ]; then
            print_error "$service did not become healthy within timeout"
            return 1
        fi
        
        sleep 2
        attempt=$((attempt + 1))
    done
}

# Function to start test environment
start_environment() {
    print_info "Starting test environment..."
    
    check_docker_compose
    check_env_file
    
    # Network will be created by docker-compose, no need to create manually
    
    # Start infrastructure services first
    print_info "Starting infrastructure services (PostgreSQL, Redis, MinIO, Fuseki)..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d \
        postgres-test \
        redis-test \
        minio-test \
        fuseki-test
    
    # Wait for infrastructure services
    wait_for_service "postgres-test"
    wait_for_service "redis-test"
    wait_for_service "minio-test"
    wait_for_service "fuseki-test"
    
    # Start microservices
    print_info "Starting microservices (DataContract, DQ, Compliance, Semantic)..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d \
        datacontract-service-test \
        dq-service-test \
        compliance-service-test \
        semantic-service-test
    
    # Wait for microservices
    wait_for_service "datacontract-service-test"
    wait_for_service "dq-service-test"
    wait_for_service "compliance-service-test"
    wait_for_service "semantic-service-test"
    
    # Start Prefect services
    print_info "Starting Prefect services..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d \
        prefect-db-test \
        prefect-server-test \
        prefect-worker-test
    
    wait_for_service "prefect-db-test"
    wait_for_service "prefect-server-test"
    
    # Start API and Worker services
    print_info "Starting API and Worker services..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$ENV_FILE" up -d \
        api-service-test \
        worker-service-test
    
    # Wait for API service
    wait_for_service "api-service-test"
    wait_for_service "worker-service-test"
    
    print_info "Test environment started successfully!"
    print_info "Run 'docker compose -f $COMPOSE_FILE --env-file $ENV_FILE ps' to check status"
}

# Function to stop test environment
stop_environment() {
    print_info "Stopping test environment..."
    
    check_docker_compose
    check_env_file
    
    $COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down
    
    print_info "Test environment stopped"
}

# Function to restart test environment
restart_environment() {
    print_info "Restarting test environment..."
    stop_environment
    sleep 2
    start_environment
}

# Function to show status
show_status() {
    check_docker_compose
    check_env_file
    
    print_info "Test environment status:"
    $COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
    
    echo ""
    print_info "Service health checks:"
    $COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps --format json | \
        jq -r '.[] | "\(.Name): \(.Health // "N/A")"' 2>/dev/null || \
        $COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps
}

# Function to show logs
show_logs() {
    local service=${1:-""}
    
    check_docker_compose
    check_env_file
    
    if [ -z "$service" ]; then
        print_info "Showing logs for all services (Ctrl+C to exit)..."
        $COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$ENV_FILE" logs -f
    else
        print_info "Showing logs for $service (Ctrl+C to exit)..."
        $COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$ENV_FILE" logs -f "$service"
    fi
}

# Function to clean test environment
clean_environment() {
    print_warn "This will remove all test containers, volumes, and networks"
    read -p "Are you sure? (yes/no): " confirm
    
    if [ "$confirm" != "yes" ]; then
        print_info "Cleanup cancelled"
        return
    fi
    
    check_docker_compose
    check_env_file
    
    print_info "Stopping and removing containers..."
    $COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$ENV_FILE" down -v
    
    print_info "Removing test network..."
    docker network rm hub-test-net 2>/dev/null || true
    
    print_info "Test environment cleaned"
}

# Function to run database migrations
run_migrations() {
    print_info "Running database migrations..."
    
    check_docker_compose
    check_env_file
    
    # Wait for postgres to be ready
    wait_for_service "postgres-test"
    
    # Run migrations in API service container
    $COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T api-service-test \
        python hub/manage.py migrate --noinput
    
    print_info "Migrations completed"
}

# Function to create test database
create_test_database() {
    print_info "Creating test database..."
    
    check_docker_compose
    check_env_file
    
    # Wait for postgres to be ready
    wait_for_service "postgres-test"
    
    # Create database if it doesn't exist
    $COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$ENV_FILE" exec -T postgres-test \
        psql -U "${POSTGRES_USER:-hub_test}" -c "CREATE DATABASE ${POSTGRES_DB:-hub_test};" 2>/dev/null || \
        print_info "Database already exists or creation failed (this is OK)"
}

# Function to verify environment
verify_environment() {
    print_info "Verifying test environment..."
    
    check_docker_compose
    check_env_file
    
    local all_healthy=true
    
    # Check each service
    services=(
        "postgres-test"
        "redis-test"
        "minio-test"
        "fuseki-test"
        "datacontract-service-test"
        "dq-service-test"
        "compliance-service-test"
        "semantic-service-test"
        "api-service-test"
        "worker-service-test"
        "prefect-server-test"
    )
    
    for service in "${services[@]}"; do
        if $COMPOSE_CMD -f "$COMPOSE_FILE" --env-file "$ENV_FILE" ps "$service" | grep -q "healthy"; then
            print_info "✓ $service is healthy"
        else
            print_error "✗ $service is not healthy"
            all_healthy=false
        fi
    done
    
    if [ "$all_healthy" = true ]; then
        print_info "All services are healthy!"
        return 0
    else
        print_error "Some services are not healthy. Check logs with: $0 logs"
        return 1
    fi
}

# Main command handler
case "${1:-start}" in
    start)
        start_environment
        sleep 5
        verify_environment
        ;;
    stop)
        stop_environment
        ;;
    restart)
        restart_environment
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "${2:-}"
        ;;
    clean)
        clean_environment
        ;;
    migrate)
        run_migrations
        ;;
    create-db)
        create_test_database
        ;;
    verify)
        verify_environment
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status|logs [service]|clean|migrate|create-db|verify}"
        echo ""
        echo "Commands:"
        echo "  start      - Start the test environment"
        echo "  stop       - Stop the test environment"
        echo "  restart    - Restart the test environment"
        echo "  status     - Show status of all services"
        echo "  logs       - Show logs (optionally for a specific service)"
        echo "  clean      - Remove all containers, volumes, and networks"
        echo "  migrate    - Run database migrations"
        echo "  create-db  - Create test database"
        echo "  verify     - Verify all services are healthy"
        exit 1
        ;;
esac
