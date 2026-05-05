#!/bin/bash
# Run E2E Tests Against Staging Environment
# This script configures and runs E2E tests against the staging environment

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
API_URL="${API_URL:-http://localhost:8001}"
BATCH="${1:-all}"
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

wait_for_services() {
    log_info "Waiting for staging services to be ready..."
    
    local max_attempts=120
    local attempt=0
    
    # Wait for API service
    while [ $attempt -lt $max_attempts ]; do
        if curl -f "$API_URL/health/" &> /dev/null; then
            log_info "API service is ready"
            break
        fi
        attempt=$((attempt + 1))
        sleep 2
    done
    
    if [ $attempt -eq $max_attempts ]; then
        log_error "API service failed to become ready"
        exit 1
    fi
    
    log_info "All services are ready"
}

run_batch() {
    local batch_num=$1
    log_info "Running E2E test batch $batch_num..."
    
    export API_BASE_URL="$API_URL"
    export STAGING_ENV=true
    export USE_REAL_SERVICES=true
    export PYTHONPATH="${PROJECT_DIR}:${PYTHONPATH:-}"
    export DJANGO_SETTINGS_MODULE=hub.settings
    
    # Staging service URLs
    export REDIS_URL="${REDIS_URL:-redis://localhost:6380/0}"
    export DATABASE_URL="${DATABASE_URL:-postgresql://hub_staging:hub_staging_secure@localhost:5433/hub_staging}"
    export DATACONTRACT_SERVICE_URL="${DATACONTRACT_SERVICE_URL:-http://localhost:8081}"
    export DQ_SERVICE_URL="${DQ_SERVICE_URL:-http://localhost:8084}"
    export COMPLIANCE_SERVICE_URL="${COMPLIANCE_SERVICE_URL:-http://localhost:8083}"
    export SEMANTIC_SERVICE_URL="${SEMANTIC_SERVICE_URL:-http://localhost:8082}"
    
    # Prefer .venv (Python 3.12 — the supported runtime) over the
    # legacy venv (which on some hosts was created against
    # Python 3.14 and breaks on dependency version skew).
    if [ -f ".venv/bin/pytest" ]; then
        .venv/bin/pytest tests/e2e/ -m "e2e_batch${batch_num}" -v --tb=short
    elif [ -f "venv/bin/pytest" ]; then
        venv/bin/pytest tests/e2e/ -m "e2e_batch${batch_num}" -v --tb=short
    elif command -v pytest &> /dev/null; then
        pytest tests/e2e/ -m "e2e_batch${batch_num}" -v --tb=short
    else
        log_error "pytest not found"
        exit 1
    fi
}

run_all_batches() {
    log_info "Running all E2E test batches..."
    
    export API_BASE_URL="$API_URL"
    export STAGING_ENV=true
    export USE_REAL_SERVICES=true
    export PYTHONPATH="${PROJECT_DIR}:${PYTHONPATH:-}"
    export DJANGO_SETTINGS_MODULE=hub.settings
    
    # Staging service URLs
    export REDIS_URL="${REDIS_URL:-redis://localhost:6380/0}"
    export DATABASE_URL="${DATABASE_URL:-postgresql://hub_staging:hub_staging_secure@localhost:5433/hub_staging}"
    export DATACONTRACT_SERVICE_URL="${DATACONTRACT_SERVICE_URL:-http://localhost:8081}"
    export DQ_SERVICE_URL="${DQ_SERVICE_URL:-http://localhost:8084}"
    export COMPLIANCE_SERVICE_URL="${COMPLIANCE_SERVICE_URL:-http://localhost:8083}"
    export SEMANTIC_SERVICE_URL="${SEMANTIC_SERVICE_URL:-http://localhost:8082}"
    
    # Prefer .venv (Python 3.12) over the legacy venv (see batch
    # function above for rationale).
    if [ -f ".venv/bin/pytest" ]; then
        .venv/bin/pytest tests/e2e/ -m e2e -v --tb=short
    elif [ -f "venv/bin/pytest" ]; then
        venv/bin/pytest tests/e2e/ -m e2e -v --tb=short
    elif command -v pytest &> /dev/null; then
        pytest tests/e2e/ -m e2e -v --tb=short
    else
        log_error "pytest not found"
        exit 1
    fi
}

# Main execution
main() {
    log_info "Running E2E tests against staging environment: $API_URL"
    
    wait_for_services
    
    case "$BATCH" in
        all)
            run_all_batches
            ;;
        1|2|3|4|5)
            run_batch "$BATCH"
            ;;
        *)
            log_error "Invalid batch number: $BATCH (must be 1-5 or 'all')"
            exit 1
            ;;
    esac
    
    log_info "E2E tests completed"
}

# Run main function
main "$@"

