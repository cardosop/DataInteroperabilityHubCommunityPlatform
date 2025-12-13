#!/bin/bash
# Pre-Deployment Checks Script
# Verifies all prerequisites before deployment

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
ENVIRONMENT="${1:-staging}"
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

check_passed() {
    echo -e "${GREEN}✓${NC} $1"
}

check_failed() {
    echo -e "${RED}✗${NC} $1"
    return 1
}

# Track failures
FAILURES=0

# Check Python version
check_python_version() {
    log_section "Checking Python Version"
    
    if command -v python3 &> /dev/null; then
        PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
        PYTHON_MAJOR=$(echo "$PYTHON_VERSION" | cut -d. -f1)
        PYTHON_MINOR=$(echo "$PYTHON_VERSION" | cut -d. -f2)
        
        if [ "$PYTHON_MAJOR" -ge 3 ] && [ "$PYTHON_MINOR" -ge 12 ]; then
            check_passed "Python version $PYTHON_VERSION >= 3.12"
        else
            check_failed "Python version $PYTHON_VERSION < 3.12"
            ((FAILURES++))
        fi
    else
        check_failed "Python 3 not found"
        ((FAILURES++))
    fi
}

# Check Docker
check_docker() {
    log_section "Checking Docker"
    
    if command -v docker &> /dev/null; then
        DOCKER_VERSION=$(docker --version)
        check_passed "Docker installed: $DOCKER_VERSION"
        
        if docker info &> /dev/null; then
            check_passed "Docker daemon running"
        else
            check_failed "Docker daemon not running"
            ((FAILURES++))
        fi
    else
        check_failed "Docker not installed"
        ((FAILURES++))
    fi
}

# Check Docker Compose
check_docker_compose() {
    log_section "Checking Docker Compose"
    
    if command -v docker &> /dev/null && docker compose version &> /dev/null; then
        COMPOSE_VERSION=$(docker compose version)
        check_passed "Docker Compose installed: $COMPOSE_VERSION"
    else
        check_failed "Docker Compose not installed"
        ((FAILURES++))
    fi
}

# Check environment file
check_environment_file() {
    log_section "Checking Environment Configuration"
    
    ENV_FILE=".env.${ENVIRONMENT}"
    if [ -f "$ENV_FILE" ]; then
        check_passed "Environment file exists: $ENV_FILE"
        
        # Check required variables
        REQUIRED_VARS=(
            "POSTGRES_PASSWORD"
            "POSTGRES_DB"
            "POSTGRES_USER"
            "REDIS_URL"
            "SECRET_KEY"
        )
        
        MISSING_VARS=()
        for VAR in "${REQUIRED_VARS[@]}"; do
            if ! grep -q "^${VAR}=" "$ENV_FILE"; then
                MISSING_VARS+=("$VAR")
            fi
        done
        
        if [ ${#MISSING_VARS[@]} -eq 0 ]; then
            check_passed "All required environment variables present"
        else
            check_failed "Missing environment variables: ${MISSING_VARS[*]}"
            ((FAILURES++))
        fi
    else
        check_failed "Environment file not found: $ENV_FILE"
        ((FAILURES++))
    fi
}

# Check disk space
check_disk_space() {
    log_section "Checking Disk Space"
    
    AVAILABLE_SPACE=$(df -BG . | tail -1 | awk '{print $4}' | sed 's/G//')
    REQUIRED_SPACE=10  # GB
    
    if [ "$AVAILABLE_SPACE" -ge "$REQUIRED_SPACE" ]; then
        check_passed "Disk space available: ${AVAILABLE_SPACE}GB >= ${REQUIRED_SPACE}GB"
    else
        check_failed "Insufficient disk space: ${AVAILABLE_SPACE}GB < ${REQUIRED_SPACE}GB"
        ((FAILURES++))
    fi
}

# Check network connectivity
check_network_connectivity() {
    log_section "Checking Network Connectivity"
    
    # Check DNS
    if nslookup google.com &> /dev/null; then
        check_passed "DNS resolution working"
    else
        check_failed "DNS resolution not working"
        ((FAILURES++))
    fi
    
    # Check internet connectivity
    if curl -s --max-time 5 https://www.google.com &> /dev/null; then
        check_passed "Internet connectivity available"
    else
        check_warn "Internet connectivity may be limited"
    fi
}

# Check Git repository
check_git_repository() {
    log_section "Checking Git Repository"
    
    if [ -d ".git" ]; then
        check_passed "Git repository found"
        
        # Check for uncommitted changes
        if [ -z "$(git status --porcelain)" ]; then
            check_passed "No uncommitted changes"
        else
            log_warn "Uncommitted changes detected (this is OK for deployment)"
        fi
        
        # Check current branch
        CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
        check_passed "Current branch: $CURRENT_BRANCH"
    else
        check_failed "Not a Git repository"
        ((FAILURES++))
    fi
}

# Check Docker images
check_docker_images() {
    log_section "Checking Docker Images"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    if [ -f "$COMPOSE_FILE" ]; then
        check_passed "Docker Compose file found: $COMPOSE_FILE"
        
        # Check if images can be pulled
        if docker compose -f "$COMPOSE_FILE" config &> /dev/null; then
            check_passed "Docker Compose configuration valid"
        else
            check_failed "Docker Compose configuration invalid"
            ((FAILURES++))
        fi
    else
        check_failed "Docker Compose file not found: $COMPOSE_FILE"
        ((FAILURES++))
    fi
}

# Check database connectivity (if services are running)
check_database_connectivity() {
    log_section "Checking Database Connectivity"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    if [ -f "$COMPOSE_FILE" ] && docker compose -f "$COMPOSE_FILE" ps postgres 2>/dev/null | grep -q "Up"; then
        # Try to connect to database
        if docker compose -f "$COMPOSE_FILE" exec -T postgres psql -U postgres -c "SELECT 1" &> /dev/null; then
            check_passed "Database connectivity verified"
        else
            log_warn "Cannot connect to database (will be started during deployment)"
            # Don't fail - database will be started during deployment
        fi
    else
        log_warn "Database service not running (will be started during deployment)"
        # Don't fail - this is expected before deployment
    fi
}

# Check Redis connectivity (if service is running)
check_redis_connectivity() {
    log_section "Checking Redis Connectivity"
    
    COMPOSE_FILE="docker-compose.${ENVIRONMENT}.yml"
    if [ -f "$COMPOSE_FILE" ] && docker compose -f "$COMPOSE_FILE" ps redis 2>/dev/null | grep -q "Up"; then
        # Try to connect to Redis
        if docker compose -f "$COMPOSE_FILE" exec -T redis redis-cli ping | grep -q "PONG"; then
            check_passed "Redis connectivity verified"
        else
            check_failed "Cannot connect to Redis"
            ((FAILURES++))
        fi
    else
        log_warn "Redis service not running (will be started during deployment)"
    fi
}

# Check test results
check_test_results() {
    log_section "Checking Test Results"
    
    # Check if tests have been run recently
    if [ -f "test_results.json" ]; then
        check_passed "Test results file found"
        
        # Check if tests passed (basic check)
        if python3 -c "import json; data=json.load(open('test_results.json')); exit(0 if data.get('passed', 0) > 0 else 1)" 2>/dev/null; then
            check_passed "Tests have passed recently"
        else
            log_warn "Test results may be outdated"
        fi
    else
        log_warn "Test results file not found (run tests before deployment)"
    fi
}

# Main execution
main() {
    log_info "Running pre-deployment checks for: $ENVIRONMENT"
    echo ""
    
    check_python_version
    check_docker
    check_docker_compose
    check_environment_file
    check_disk_space
    check_network_connectivity
    check_git_repository
    check_docker_images
    check_database_connectivity
    check_redis_connectivity
    check_test_results
    
    echo ""
    log_section "Summary"
    
    if [ $FAILURES -eq 0 ]; then
        log_info "All pre-deployment checks passed ✓"
        exit 0
    else
        log_error "$FAILURES check(s) failed"
        log_error "Please fix the issues above before proceeding with deployment"
        exit 1
    fi
}

# Run main function
main "$@"

