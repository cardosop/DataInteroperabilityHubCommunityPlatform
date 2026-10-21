#!/bin/bash
#
# Start All Services for Development and Testing
#
# This script starts all services required for development and testing in the correct order:
# 1. Infrastructure services (PostgreSQL, Redis, MinIO, Fuseki)
# 2. Core application services (API, Worker)
# 3. Workflow services (Workflow Engine, Workflow Registry)
# 4. Event bus services (Event Bus Health, Event Schema Registry)
# 5. Microservices (Semantic, DQ, Compliance, DataContract, Search, Observability, Webhook)
# 6. Prefect services (Prefect Server, Prefect DB, Prefect Worker, Prefect Integration)
# 7. Monitoring services (Prometheus, Grafana, Jaeger, Alertmanager)
# 8. API Gateway (Traefik)
# 9. Frontend (optional, runs separately via npm)
#
# Usage:
#   ./scripts/start-all-services.sh [--env ENV] [--skip-frontend] [--skip-monitoring] [--services SERVICES]
#
# Options:
#   --env ENV           Environment (dev, staging, production) - default: dev
#   --skip-frontend    Skip starting frontend dev server
#   --skip-monitoring  Skip starting monitoring services
#   --services SERVICES Comma-separated list of specific services to start
#   --check-only       Only check service status, don't start anything
#   --stop-first       Stop existing services before starting
#

set -euo pipefail

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly CYAN='\033[0;36m'
readonly NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${ENVIRONMENT:-dev}"
COMPOSE_FILE=""
SKIP_FRONTEND=false
SKIP_MONITORING=false
SERVICES=""
CHECK_ONLY=false
STOP_FIRST=false
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Logging functions
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

log_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --env)
                ENVIRONMENT="$2"
                shift 2
                ;;
            --skip-frontend)
                SKIP_FRONTEND=true
                shift
                ;;
            --skip-monitoring)
                SKIP_MONITORING=true
                shift
                ;;
            --services)
                SERVICES="$2"
                shift 2
                ;;
            --check-only)
                CHECK_ONLY=true
                shift
                ;;
            --stop-first)
                STOP_FIRST=true
                shift
                ;;
            --help)
                cat << EOF
Start All Services for Development and Testing

Usage:
  $0 [OPTIONS]

Options:
  --env ENV           Environment (dev, staging, production) - default: dev
  --skip-frontend     Skip starting frontend dev server
  --skip-monitoring   Skip starting monitoring services
  --services SERVICES Comma-separated list of specific services to start
  --check-only        Only check service status, don't start anything
  --stop-first        Stop existing services before starting
  --help              Show this help message

Examples:
  $0                                    # Start all services in dev environment
  $0 --env staging                      # Start all services in staging environment
  $0 --skip-monitoring                  # Start services without monitoring
  $0 --services postgres,redis,api      # Start only specific services
  $0 --check-only                       # Check status of all services
EOF
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                echo "Use --help for usage information"
                exit 1
                ;;
        esac
    done
}

# Determine compose file based on environment
determine_compose_file() {
    case "$ENVIRONMENT" in
        dev|development)
            COMPOSE_FILE="docker-compose.dev.yml"
            ;;
        staging)
            COMPOSE_FILE="docker-compose.staging.yml"
            ;;
        prod|production)
            COMPOSE_FILE="docker-compose.production.yml"
            ;;
        *)
            log_error "Unknown environment: $ENVIRONMENT"
            log_info "Valid environments: dev, staging, production"
            exit 1
            ;;
    esac

    if [ ! -f "$PROJECT_DIR/$COMPOSE_FILE" ]; then
        log_error "Docker Compose file not found: $COMPOSE_FILE"
        exit 1
    fi

    log_info "Using Docker Compose file: $COMPOSE_FILE"
}

# Check if Docker is running
check_docker() {
    if ! docker info > /dev/null 2>&1; then
        log_error "Docker is not running. Please start Docker and try again."
        exit 1
    fi
    log_info "Docker is running"
}

# Check service health
check_service_health() {
    local service_name=$1
    local port=$2
    local max_attempts=${3:-30}
    local attempt=0

    log_step "Checking health of $service_name on port $port..."

    while [ $attempt -lt $max_attempts ]; do
        if docker compose -f "$PROJECT_DIR/$COMPOSE_FILE" exec -T "$service_name" \
            curl -f -s "http://localhost:$port/health" > /dev/null 2>&1 || \
           curl -f -s "http://localhost:$port/health" > /dev/null 2>&1; then
            log_info "✅ $service_name is healthy"
            return 0
        fi

        attempt=$((attempt + 1))
        if [ $attempt -lt $max_attempts ]; then
            sleep 2
        fi
    done

    log_warn "⚠️  $service_name health check timeout (may still be starting)"
    return 1
}

# Wait for infrastructure to be ready
wait_for_infrastructure() {
    log_section "Waiting for Infrastructure Services"

    log_step "Waiting for PostgreSQL..."
    docker compose -f "$PROJECT_DIR/$COMPOSE_FILE" exec -T postgres \
        pg_isready -U "${POSTGRES_USER:-hub}" > /dev/null 2>&1 || sleep 5

    log_step "Waiting for Redis..."
    docker compose -f "$PROJECT_DIR/$COMPOSE_FILE" exec -T redis \
        redis-cli ping > /dev/null 2>&1 || sleep 5

    log_step "Waiting for MinIO..."
    sleep 5  # MinIO takes a moment to initialize

    log_step "Waiting for Fuseki..."
    sleep 5  # Fuseki takes a moment to initialize

    log_info "✅ Infrastructure services are ready"
}

# Start infrastructure services
start_infrastructure() {
    log_section "Starting Infrastructure Services"

    local infra_services=("postgres" "redis" "minio" "fuseki")

    if [ -n "$SERVICES" ]; then
        # Filter services if specific services requested
        local requested_services
        IFS=',' read -ra requested_services <<< "$SERVICES"
        local filtered_services=()
        for service in "${infra_services[@]}"; do
            for req_service in "${requested_services[@]}"; do
                if [ "$service" = "$req_service" ]; then
                    filtered_services+=("$service")
                    break
                fi
            done
        done
        if [ ${#filtered_services[@]} -eq 0 ]; then
            log_info "No infrastructure services to start"
            return 0
        fi
        infra_services=("${filtered_services[@]}")
    fi

    if docker compose -f "$PROJECT_DIR/$COMPOSE_FILE" up -d "${infra_services[@]}"; then
        log_info "✅ Infrastructure services started"
        wait_for_infrastructure
        return 0
    else
        log_error "Failed to start infrastructure services"
        return 1
    fi
}

# Start core application services
start_core_services() {
    log_section "Starting Core Application Services"

    local core_services=("api-service" "worker-service")

    if [ -n "$SERVICES" ]; then
        local requested_services
        IFS=',' read -ra requested_services <<< "$SERVICES"
        local filtered_services=()
        for service in "${core_services[@]}"; do
            for req_service in "${requested_services[@]}"; do
                if [ "$service" = "$req_service" ]; then
                    filtered_services+=("$service")
                    break
                fi
            done
        done
        if [ ${#filtered_services[@]} -eq 0 ]; then
            log_info "No core services to start"
            return 0
        fi
        core_services=("${filtered_services[@]}")
    fi

    if docker compose -f "$PROJECT_DIR/$COMPOSE_FILE" up -d "${core_services[@]}"; then
        log_info "✅ Core services started"
        sleep 5
        return 0
    else
        log_error "Failed to start core services"
        return 1
    fi
}

# Start workflow services
start_workflow_services() {
    log_section "Starting Workflow Services"

    local workflow_services=("workflow-engine-service" "workflow-registry-service")

    if [ -n "$SERVICES" ]; then
        local requested_services
        IFS=',' read -ra requested_services <<< "$SERVICES"
        local filtered_services=()
        for service in "${workflow_services[@]}"; do
            for req_service in "${requested_services[@]}"; do
                if [ "$service" = "$req_service" ]; then
                    filtered_services+=("$service")
                    break
                fi
            done
        done
        if [ ${#filtered_services[@]} -eq 0 ]; then
            log_info "No workflow services to start"
            return 0
        fi
        workflow_services=("${filtered_services[@]}")
    fi

    if docker compose -f "$PROJECT_DIR/$COMPOSE_FILE" up -d "${workflow_services[@]}"; then
        log_info "✅ Workflow services started"
        sleep 3
        return 0
    else
        log_error "Failed to start workflow services"
        return 1
    fi
}

# Start event bus services
start_event_bus_services() {
    log_section "Starting Event Bus Services"

    local event_services=("event-bus-health-service" "event-schema-registry-service")

    if [ -n "$SERVICES" ]; then
        local requested_services
        IFS=',' read -ra requested_services <<< "$SERVICES"
        local filtered_services=()
        for service in "${event_services[@]}"; do
            for req_service in "${requested_services[@]}"; do
                if [ "$service" = "$req_service" ]; then
                    filtered_services+=("$service")
                    break
                fi
            done
        done
        if [ ${#filtered_services[@]} -eq 0 ]; then
            log_info "No event bus services to start"
            return 0
        fi
        event_services=("${filtered_services[@]}")
    fi

    if docker compose -f "$PROJECT_DIR/$COMPOSE_FILE" up -d "${event_services[@]}"; then
        log_info "✅ Event bus services started"
        sleep 3
        return 0
    else
        log_error "Failed to start event bus services"
        return 1
    fi
}

# Start microservices
start_microservices() {
    log_section "Starting Microservices"

    local microservices=(
        "semantic-service"
        "dq-service"
        "compliance-service"
        "datacontract-service"
        "search-service"
        "observability-service"
        "webhook-service"
    )

    if [ -n "$SERVICES" ]; then
        local requested_services
        IFS=',' read -ra requested_services <<< "$SERVICES"
        local filtered_services=()
        for service in "${microservices[@]}"; do
            for req_service in "${requested_services[@]}"; do
                if [ "$service" = "$req_service" ]; then
                    filtered_services+=("$service")
                    break
                fi
            done
        done
        if [ ${#filtered_services[@]} -eq 0 ]; then
            log_info "No microservices to start"
            return 0
        fi
        microservices=("${filtered_services[@]}")
    fi

    if docker compose -f "$PROJECT_DIR/$COMPOSE_FILE" up -d "${microservices[@]}"; then
        log_info "✅ Microservices started"
        sleep 5

        # Check health of microservices
        for service in "${microservices[@]}"; do
            case $service in
                semantic-service)
                    check_service_health "$service" 8081 15 || true
                    ;;
                dq-service)
                    check_service_health "$service" 8083 15 || true
                    ;;
                compliance-service)
                    check_service_health "$service" 8082 15 || true
                    ;;
                datacontract-service)
                    check_service_health "$service" 8080 15 || true
                    ;;
                search-service)
                    check_service_health "$service" 8085 15 || true
                    ;;
                observability-service)
                    check_service_health "$service" 8086 15 || true
                    ;;
                webhook-service)
                    check_service_health "$service" 8087 15 || true
                    ;;
            esac
        done

        return 0
    else
        log_error "Failed to start microservices"
        return 1
    fi
}

# Start Prefect services
start_prefect_services() {
    log_section "Starting Prefect Services"

    local prefect_services=("prefect-db" "prefect-server" "prefect-worker" "prefect-integration-service")

    if [ -n "$SERVICES" ]; then
        local requested_services
        IFS=',' read -ra requested_services <<< "$SERVICES"
        local filtered_services=()
        for service in "${prefect_services[@]}"; do
            for req_service in "${requested_services[@]}"; do
                if [ "$service" = "$req_service" ]; then
                    filtered_services+=("$service")
                    break
                fi
            done
        done
        if [ ${#filtered_services[@]} -eq 0 ]; then
            log_info "No Prefect services to start"
            return 0
        fi
        prefect_services=("${filtered_services[@]}")
    fi

    if docker compose -f "$PROJECT_DIR/$COMPOSE_FILE" up -d "${prefect_services[@]}"; then
        log_info "✅ Prefect services started"
        sleep 5
        return 0
    else
        log_error "Failed to start Prefect services"
        return 1
    fi
}

# Start monitoring services
start_monitoring_services() {
    if [ "$SKIP_MONITORING" = true ]; then
        log_info "Skipping monitoring services (--skip-monitoring)"
        return 0
    fi

    log_section "Starting Monitoring Services"

    local monitoring_services=("prometheus" "grafana" "jaeger" "alertmanager")

    if [ -n "$SERVICES" ]; then
        local requested_services
        IFS=',' read -ra requested_services <<< "$SERVICES"
        local filtered_services=()
        for service in "${monitoring_services[@]}"; do
            for req_service in "${requested_services[@]}"; do
                if [ "$service" = "$req_service" ]; then
                    filtered_services+=("$service")
                    break
                fi
            done
        done
        if [ ${#filtered_services[@]} -eq 0 ]; then
            log_info "No monitoring services to start"
            return 0
        fi
        monitoring_services=("${filtered_services[@]}")
    fi

    if docker compose -f "$PROJECT_DIR/$COMPOSE_FILE" up -d "${monitoring_services[@]}"; then
        log_info "✅ Monitoring services started"
        sleep 3
        return 0
    else
        log_error "Failed to start monitoring services"
        return 1
    fi
}

# Start API gateway
start_api_gateway() {
    log_section "Starting API Gateway"

    if [ -n "$SERVICES" ] && [[ ! "$SERVICES" =~ traefik ]]; then
        log_info "Traefik not in requested services, skipping"
        return 0
    fi

    if docker compose -f "$PROJECT_DIR/$COMPOSE_FILE" up -d traefik; then
        log_info "✅ API Gateway (Traefik) started"
        sleep 3
        return 0
    else
        log_error "Failed to start API Gateway"
        return 1
    fi
}

# Start frontend
start_frontend() {
    if [ "$SKIP_FRONTEND" = true ]; then
        log_info "Skipping frontend (--skip-frontend)"
        return 0
    fi

    log_section "Starting Frontend Development Server"

    if [ ! -d "$PROJECT_DIR/frontend" ]; then
        log_warn "Frontend directory not found, skipping frontend"
        return 0
    fi

    if ! command -v npm > /dev/null 2>&1; then
        log_warn "npm not found, skipping frontend. Install Node.js to run frontend."
        return 0
    fi

    cd "$PROJECT_DIR/frontend"

    if [ ! -d "node_modules" ]; then
        log_info "Installing frontend dependencies..."
        npm install
    fi

    log_info "Starting frontend dev server..."
    log_info "Frontend will be available at http://localhost:3000"
    log_info "Press Ctrl+C to stop the frontend server"

    # Start frontend in background
    npm run dev &
    FRONTEND_PID=$!
    echo $FRONTEND_PID > /tmp/frontend-dev-server.pid

    log_info "✅ Frontend dev server started (PID: $FRONTEND_PID)"
    log_info "To stop frontend: kill $FRONTEND_PID or pkill -f 'vite'"
}

# Check service status
check_service_status() {
    log_section "Service Status"

    docker compose -f "$PROJECT_DIR/$COMPOSE_FILE" ps

    echo ""
    log_info "Service URLs:"
    log_info "  API Service:        http://localhost:8000"
    log_info "  API Docs:           http://localhost:8000/api/v1/docs"
    log_info "  MinIO Console:      http://localhost:9001"
    log_info "  Fuseki:             http://localhost:3030"
    log_info "  Grafana:            http://localhost:3001"
    log_info "  Prometheus:         http://localhost:9090"
    log_info "  Jaeger:             http://localhost:16686"
    if [ "$SKIP_FRONTEND" != true ]; then
        log_info "  Frontend:            http://localhost:3000"
    fi
}

# Stop existing services
stop_existing_services() {
    log_section "Stopping Existing Services"

    if docker compose -f "$PROJECT_DIR/$COMPOSE_FILE" ps -q | grep -q .; then
        log_info "Stopping existing services..."
        docker compose -f "$PROJECT_DIR/$COMPOSE_FILE" down
        sleep 2
        log_info "✅ Existing services stopped"
    else
        log_info "No existing services to stop"
    fi
}

# Main execution
main() {
    log_section "Starting All Services for Development and Testing"

    parse_args "$@"
    determine_compose_file
    check_docker

    if [ "$CHECK_ONLY" = true ]; then
        check_service_status
        exit 0
    fi

    if [ "$STOP_FIRST" = true ]; then
        stop_existing_services
    fi

    # Start services in order
    start_infrastructure || exit 1
    start_core_services || exit 1
    start_workflow_services || exit 1
    start_event_bus_services || exit 1
    start_microservices || exit 1
    start_prefect_services || exit 1
    start_monitoring_services || exit 1
    start_api_gateway || exit 1
    start_frontend || true  # Frontend is optional

    # Show final status
    check_service_status

    log_section "All Services Started"
    log_info "✅ Development environment is ready!"
    log_info ""
    log_info "Useful commands:"
    log_info "  View logs:        docker compose -f $COMPOSE_FILE logs -f [service]"
    log_info "  Stop services:    docker compose -f $COMPOSE_FILE down"
    log_info "  Check status:     docker compose -f $COMPOSE_FILE ps"
    log_info "  Restart service:  docker compose -f $COMPOSE_FILE restart [service]"
}

# Run main function
main "$@"

