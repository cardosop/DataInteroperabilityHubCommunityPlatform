#!/bin/bash
# Production Deployment Script
# Deploys to production environment with blue-green strategy

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
STRATEGY="${1:-blue-green}"
ENVIRONMENT="${2:-green}"
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

confirm_production_deployment() {
    log_warn "WARNING: This will deploy to PRODUCTION environment"
    log_warn "Strategy: $STRATEGY"
    log_warn "Environment: $ENVIRONMENT"
    echo ""
    read -p "Are you sure you want to proceed? (yes/no): " CONFIRM
    
    if [ "$CONFIRM" != "yes" ]; then
        log_info "Production deployment cancelled"
        exit 0
    fi
}

# Pre-deployment checks
run_pre_deployment_checks() {
    log_section "Running Pre-Deployment Checks"
    
    if ./scripts/pre_deployment_checks.sh production; then
        log_info "Pre-deployment checks passed"
    else
        log_error "Pre-deployment checks failed"
        exit 1
    fi
}

# Create backups
create_backups() {
    log_section "Creating Backups"
    
    if ./scripts/create_backup.sh production; then
        log_info "Backups created successfully"
    else
        log_error "Backup creation failed"
        exit 1
    fi
}

# Deploy infrastructure
deploy_infrastructure() {
    log_section "Deploying Infrastructure"
    
    COMPOSE_FILE="docker-compose.production.yml"
    
    if [ ! -f "$COMPOSE_FILE" ]; then
        log_error "Production Docker Compose file not found: $COMPOSE_FILE"
        exit 1
    fi
    
    log_info "Pulling latest Docker images..."
    docker compose -f "$COMPOSE_FILE" pull
    
    log_info "Building application images..."
    docker compose -f "$COMPOSE_FILE" build
    
    log_info "Starting infrastructure services..."
    docker compose -f "$COMPOSE_FILE" up -d postgres redis minio
    
    log_info "Waiting for infrastructure services to be healthy..."
    sleep 10
    
    # Check infrastructure health
    if docker compose -f "$COMPOSE_FILE" ps postgres redis minio | grep -q "Up"; then
        log_info "Infrastructure services started successfully"
    else
        log_error "Some infrastructure services failed to start"
        exit 1
    fi
}

# Deploy application services
deploy_application_services() {
    log_section "Deploying Application Services"
    
    COMPOSE_FILE="docker-compose.production.yml"
    
    log_info "Starting application services..."
    docker compose -f "$COMPOSE_FILE" up -d api-service worker-service
    
    log_info "Waiting for application services to be healthy..."
    sleep 15
    
    # Check application health
    if docker compose -f "$COMPOSE_FILE" ps api-service worker-service | grep -q "Up"; then
        log_info "Application services started successfully"
    else
        log_error "Some application services failed to start"
        exit 1
    fi
}

# Run database migrations
run_database_migrations() {
    log_section "Running Database Migrations"
    
    if ./scripts/run_migrations.sh production --monitor; then
        log_info "Database migrations completed successfully"
    else
        log_error "Database migrations failed"
        exit 1
    fi
}

# Verify deployment
verify_deployment() {
    log_section "Verifying Deployment"
    
    if ./scripts/verify_deployment.sh production; then
        log_info "Deployment verification passed"
    else
        log_error "Deployment verification failed"
        exit 1
    fi
}

# Run smoke tests
run_smoke_tests() {
    log_section "Running Smoke Tests"
    
    if ./scripts/smoke-tests.sh production; then
        log_info "Smoke tests passed"
    else
        log_error "Smoke tests failed"
        exit 1
    fi
}

# Switch traffic (for blue-green deployment)
switch_traffic() {
    log_section "Switching Traffic"
    
    if [ "$STRATEGY" = "blue-green" ]; then
        log_info "Switching traffic from blue to green environment..."
        
        # This is a placeholder - actual implementation depends on load balancer configuration
        # For Kubernetes, this would be: kubectl patch service api-service -p '{"spec":{"selector":{"version":"green"}}}'
        # For Docker Compose, this would involve updating nginx/load balancer configuration
        
        log_warn "Traffic switching must be done manually or via infrastructure automation"
        log_info "After switching traffic, monitor the green environment for issues"
    else
        log_info "Traffic switching not required for strategy: $STRATEGY"
    fi
}

# Main execution
main() {
    log_info "Starting production deployment"
    log_info "Strategy: $STRATEGY"
    log_info "Environment: $ENVIRONMENT"
    echo ""
    
    confirm_production_deployment
    run_pre_deployment_checks
    create_backups
    deploy_infrastructure
    deploy_application_services
    run_database_migrations
    verify_deployment
    run_smoke_tests
    switch_traffic
    
    echo ""
    log_info "Production deployment completed successfully ✓"
    log_warn "Please monitor the deployment closely for the next 24 hours"
    log_info "Use './scripts/monitor_deployment.sh production --baseline-comparison' to monitor"
}

# Run main function
main "$@"

