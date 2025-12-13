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
    
    # First, check for pending migrations and create them if needed
    log_info "Checking for pending migrations..."
    PENDING_OUTPUT=$(docker compose -f "$COMPOSE_FILE" run --rm api-service python hub/manage.py makemigrations --dry-run 2>&1 || true)
    
    if echo "$PENDING_OUTPUT" | grep -q "Migrations for"; then
        log_warn "Pending migrations detected. Creating migrations..."
        docker compose -f "$COMPOSE_FILE" run --rm api-service python hub/manage.py makemigrations --noinput
        log_info "Migrations created successfully"
    else
        log_info "No pending migrations detected"
    fi
    
    # Now apply migrations
    log_info "Applying migrations..."
    docker compose -f "$COMPOSE_FILE" run --rm api-service python hub/manage.py migrate --noinput
    log_info "Database migrations completed"
}

setup_minio_bucket() {
    log_info "Setting up MinIO bucket..."
    docker compose -f "$COMPOSE_FILE" run --rm api-service python scripts/setup_minio_bucket.py
    log_info "MinIO bucket setup completed"
}

start_services() {
    log_info "Starting application services..."
    
    # Stop and remove any existing containers that might conflict with port bindings
    log_info "Stopping any conflicting containers..."
    docker compose -f "$COMPOSE_FILE" stop datacontract-service semantic-service compliance-service dq-service api-service worker-service 2>/dev/null || true
    docker compose -f "$COMPOSE_FILE" rm -f datacontract-service semantic-service compliance-service dq-service api-service worker-service 2>/dev/null || true
    
    # Also check for containers from base docker-compose.yml that might conflict
    if docker ps -a --format "{{.Names}}" | grep -q "^hub-datacontract$"; then
        log_warn "Stopping conflicting base datacontract container..."
        docker stop hub-datacontract 2>/dev/null || true
        docker rm hub-datacontract 2>/dev/null || true
    fi
    
    # Use --force-recreate to ensure containers are recreated and port conflicts are resolved
    docker compose -f "$COMPOSE_FILE" up -d --force-recreate \
        semantic-service \
        datacontract-service \
        compliance-service \
        dq-service \
        api-service \
        worker-service
    
    log_info "Waiting for services to be healthy..."
    local max_attempts=120
    local attempt=0
    
    # Wait for all services to be healthy
    local services_ready=0
    local total_services=6
    
    while [ $attempt -lt $max_attempts ] && [ $services_ready -lt $total_services ]; do
        services_ready=0
        
        # Check API service (with trailing slash)
        if curl -f -L --max-time 2 --connect-timeout 1 http://localhost:8001/health/ &> /dev/null; then
            services_ready=$((services_ready + 1))
        fi
        
        # Check DataContract service
        if curl -f -L --max-time 2 --connect-timeout 1 http://localhost:8086/health &> /dev/null; then
            services_ready=$((services_ready + 1))
        fi
        
        # Check Semantic service
        if curl -f -L --max-time 2 --connect-timeout 1 http://localhost:8082/health &> /dev/null; then
            services_ready=$((services_ready + 1))
        fi
        
        # Check Compliance service
        if curl -f -L --max-time 2 --connect-timeout 1 http://localhost:8083/health &> /dev/null; then
            services_ready=$((services_ready + 1))
        fi
        
        # Check DQ service
        if curl -f -L --max-time 2 --connect-timeout 1 http://localhost:8084/health &> /dev/null; then
            services_ready=$((services_ready + 1))
        fi
        
        # Check Worker service
        if curl -f -L --max-time 2 --connect-timeout 1 http://localhost:8085/healthz &> /dev/null; then
            services_ready=$((services_ready + 1))
        fi
        
        if [ $services_ready -eq $total_services ]; then
            log_info "All application services are healthy ($services_ready/$total_services)"
            break
        fi
        
        attempt=$((attempt + 1))
        if [ $((attempt % 10)) -eq 0 ]; then
            log_info "Waiting for services... ($services_ready/$total_services ready, attempt $attempt/$max_attempts)"
        fi
        sleep 2
    done
    
    if [ $services_ready -lt $total_services ]; then
        log_error "Not all services became healthy ($services_ready/$total_services ready after $attempt attempts)"
        log_error "Checking service logs..."
        docker compose -f "$COMPOSE_FILE" logs --tail=20 api-service datacontract-service semantic-service compliance-service dq-service worker-service
        exit 1
    fi
    
    log_info "Application services are healthy"
}

start_monitoring() {
    log_info "Starting monitoring services..."
    docker compose -f "$COMPOSE_FILE" up -d prometheus grafana jaeger alertmanager
    log_info "Monitoring services started"
    
    # Give monitoring services a moment to start and application services to reconnect
    log_info "Waiting for monitoring services to stabilize..."
    sleep 3
}

verify_deployment() {
    log_info "Verifying deployment..."
    
    # Give services a moment to fully stabilize after monitoring services start
    # This ensures all services have reconnected to monitoring endpoints
    log_info "Waiting for services to stabilize after monitoring startup..."
    sleep 10
    
    local services=(
        "http://localhost:8001/health/:API Service"
        "http://localhost:8086/health:DataContract Service"
        "http://localhost:8082/health:Semantic Service"
        "http://localhost:8083/health:Compliance Service"
        "http://localhost:8084/health:DQ Service"
        "http://localhost:8085/healthz:Worker Service"
    )
    
    local failed=0
    
    for service in "${services[@]}"; do
        local url="${service%%:*}"
        local name="${service##*:}"
        
        # Use curl with -L to follow redirects and -f to fail on HTTP errors
        # Also add a timeout to prevent hanging
        # Retry up to 3 times with increasing delays
        local retry_count=0
        local max_retries=3
        local success=false
        
        while [ $retry_count -lt $max_retries ]; do
            if curl -f -L --max-time 10 --connect-timeout 5 "$url" &> /dev/null; then
                log_info "$name is healthy"
                success=true
                break
            fi
            retry_count=$((retry_count + 1))
            if [ $retry_count -lt $max_retries ]; then
                log_warn "$name health check failed, retrying ($retry_count/$max_retries)..."
                sleep 2
            fi
        done
        
        if [ "$success" = false ]; then
            log_error "$name health check failed after $max_retries attempts"
            failed=$((failed + 1))
        fi
    done
    
    if [ $failed -gt 0 ]; then
        log_error "Deployment verification failed: $failed service(s) unhealthy"
        exit 1
    fi
    
    # Verify OpenTelemetry metrics endpoint (for API service)
    log_info "Verifying OpenTelemetry metrics endpoint..."
    if [ -f "$SCRIPT_DIR/verify_metrics_deployment.sh" ]; then
        if "$SCRIPT_DIR/verify_metrics_deployment.sh" staging "http://localhost:8001" > /dev/null 2>&1; then
            log_info "Metrics endpoint verification passed"
        else
            log_warn "Metrics endpoint verification had issues (check manually with: ./scripts/verify_metrics_deployment.sh staging http://localhost:8001)"
        fi
    else
        # Fallback: basic metrics check
        if curl -f -s "http://localhost:8001/metrics/" > /dev/null 2>&1; then
            log_info "Metrics endpoint accessible"
        else
            log_warn "Metrics endpoint check failed (may be normal if metrics not enabled)"
        fi
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

