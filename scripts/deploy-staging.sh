#!/bin/bash
# Staging Deployment Script
# This script deploys the Data Interoperability Hub to staging environment

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
COMPOSE_FILE="docker-compose.staging.yml"
ENV_FILE=".env.staging"
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

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed"
        exit 1
    fi
    
    # Check Docker Compose
    if ! command -v docker compose &> /dev/null; then
        log_error "Docker Compose is not installed"
        exit 1
    fi
    
    # Check environment file
    if [ ! -f "$ENV_FILE" ]; then
        log_warn "Environment file $ENV_FILE not found"
        log_info "Creating $ENV_FILE from .env.staging.example..."
        if [ -f ".env.staging.example" ]; then
            cp .env.staging.example "$ENV_FILE"
            log_warn "Please update $ENV_FILE with actual values before proceeding"
            exit 1
        else
            log_error ".env.staging.example not found"
            exit 1
        fi
    fi
    
    log_info "Prerequisites check passed"
}

build_images() {
    log_info "Building Docker images..."
    docker compose -f "$COMPOSE_FILE" build --no-cache
    log_info "Docker images built successfully"
}

start_infrastructure() {
    log_info "Starting infrastructure services..."
    docker compose -f "$COMPOSE_FILE" up -d postgres redis minio fuseki
    
    log_info "Waiting for infrastructure services to be healthy..."
    local max_attempts=60
    local attempt=0
    
    # Wait for PostgreSQL
    while [ $attempt -lt $max_attempts ]; do
        if docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U hub_staging &> /dev/null; then
            log_info "PostgreSQL is ready"
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        log_error "PostgreSQL failed to become ready"
        exit 1
    fi
    
    # Wait for Redis
    attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if docker compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping &> /dev/null; then
            log_info "Redis is ready"
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        log_error "Redis failed to become ready"
        exit 1
    fi
    
    # Wait for MinIO
    attempt=0
    while [ $attempt -lt $max_attempts ]; do
        if curl -f http://localhost:9010/minio/health/live &> /dev/null; then
            log_info "MinIO is ready"
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        log_error "MinIO failed to become ready"
        exit 1
    fi
    
    log_info "Infrastructure services are healthy"
}

run_migrations() {
    log_info "Running database migrations..."
    docker compose -f "$COMPOSE_FILE" run --rm api-service python manage.py migrate --noinput
    log_info "Database migrations completed"
}

setup_minio_bucket() {
    log_info "Setting up MinIO bucket..."
    docker compose -f "$COMPOSE_FILE" run --rm api-service python scripts/setup_minio_bucket.py
    log_info "MinIO bucket setup completed"
}

start_services() {
    log_info "Starting application services..."
    docker compose -f "$COMPOSE_FILE" up -d \
        semantic-service \
        datacontract-service \
        compliance-service \
        dq-service \
        api-service \
        worker-service
    
    log_info "Waiting for services to be healthy..."
    local max_attempts=120
    local attempt=0
    
    # Wait for API service
    while [ $attempt -lt $max_attempts ]; do
        if curl -f http://localhost:8001/health &> /dev/null; then
            log_info "API service is healthy"
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        log_error "API service failed to become healthy"
        docker compose -f "$COMPOSE_FILE" logs api-service
        exit 1
    fi
    
    log_info "Application services are healthy"
}

start_monitoring() {
    log_info "Starting monitoring services..."
    docker compose -f "$COMPOSE_FILE" up -d prometheus grafana jaeger alertmanager
    log_info "Monitoring services started"
}

verify_deployment() {
    log_info "Verifying deployment..."
    
    local services=(
        "http://localhost:8001/health:API Service"
        "http://localhost:8081/health:DataContract Service"
        "http://localhost:8082/health:Semantic Service"
        "http://localhost:8083/health:Compliance Service"
        "http://localhost:8084/health:DQ Service"
        "http://localhost:8081/healthz:Worker Service"
    )
    
    local failed=0
    
    for service in "${services[@]}"; do
        local url="${service%%:*}"
        local name="${service##*:}"
        
        if curl -f "$url" &> /dev/null; then
            log_info "$name is healthy"
        else
            log_error "$name health check failed"
            failed=$((failed + 1))
        fi
    done
    
    if [ $failed -gt 0 ]; then
        log_error "Deployment verification failed: $failed service(s) unhealthy"
        exit 1
    fi
    
    log_info "Deployment verification passed"
}

show_status() {
    log_info "Deployment Status:"
    docker compose -f "$COMPOSE_FILE" ps
    
    echo ""
    log_info "Service URLs:"
    echo "  API Service: http://localhost:8001"
    echo "  Grafana: http://localhost:3001"
    echo "  Prometheus: http://localhost:9091"
    echo "  Jaeger: http://localhost:16687"
    echo "  MinIO Console: http://localhost:9011"
}

# Main deployment flow
main() {
    log_info "Starting staging deployment..."
    
    check_prerequisites
    build_images
    start_infrastructure
    run_migrations
    setup_minio_bucket
    start_services
    start_monitoring
    verify_deployment
    show_status
    
    log_info "Staging deployment completed successfully!"
}

# Run main function
main "$@"

