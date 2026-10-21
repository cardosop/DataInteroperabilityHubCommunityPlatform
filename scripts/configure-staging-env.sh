#!/bin/bash
# Configure Staging Environment
# This script helps configure staging environment variables and secrets

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
ENV_FILE=".env.staging"
EXAMPLE_FILE=".env.staging.example"
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

create_env_file() {
    if [ -f "$ENV_FILE" ]; then
        log_warn "$ENV_FILE already exists"
        read -p "Overwrite? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_info "Keeping existing $ENV_FILE"
            return
        fi
    fi
    
    if [ ! -f "$EXAMPLE_FILE" ]; then
        log_error "$EXAMPLE_FILE not found"
        exit 1
    fi
    
    log_info "Creating $ENV_FILE from $EXAMPLE_FILE..."
    cp "$EXAMPLE_FILE" "$ENV_FILE"
    log_info "$ENV_FILE created. Please update with actual values."
}

generate_secret_key() {
    log_info "Generating Django SECRET_KEY..."
    python3 -c "import secrets; print(secrets.token_urlsafe(50))"
}

configure_secrets() {
    log_info "Configuring secrets..."
    
    # Generate SECRET_KEY if not set
    if ! grep -q "^SECRET_KEY=" "$ENV_FILE" || grep -q "^SECRET_KEY=$" "$ENV_FILE"; then
        log_info "Generating SECRET_KEY..."
        SECRET_KEY=$(generate_secret_key)
        if grep -q "^SECRET_KEY=" "$ENV_FILE"; then
            sed -i "s|^SECRET_KEY=.*|SECRET_KEY=$SECRET_KEY|" "$ENV_FILE"
        else
            echo "SECRET_KEY=$SECRET_KEY" >> "$ENV_FILE"
        fi
        log_info "SECRET_KEY generated and set"
    fi
    
    log_info "Secrets configuration complete"
    log_warn "Please review and update the following in $ENV_FILE:"
    log_warn "  - Database passwords"
    log_warn "  - Email service credentials (SendGrid/SES/SMTP)"
    log_warn "  - MinIO credentials"
    log_warn "  - Grafana admin password"
}

verify_configuration() {
    log_info "Verifying configuration..."
    
    local errors=0
    
    # Check required variables
    local required_vars=(
        "SECRET_KEY"
        "POSTGRES_PASSWORD"
        "MINIO_ROOT_PASSWORD"
    )
    
    for var in "${required_vars[@]}"; do
        if ! grep -q "^${var}=" "$ENV_FILE" || grep -q "^${var}=$" "$ENV_FILE"; then
            log_error "Required variable $var is not set"
            errors=$((errors + 1))
        fi
    done
    
    if [ $errors -eq 0 ]; then
        log_info "Configuration verification passed"
        return 0
    else
        log_error "Configuration verification failed: $errors error(s)"
        return 1
    fi
}

# Main execution
main() {
    log_info "Configuring staging environment..."
    
    create_env_file
    configure_secrets
    
    if verify_configuration; then
        log_info "Staging environment configuration complete!"
        log_info "Next steps:"
        log_info "  1. Review and update $ENV_FILE with actual values"
        log_info "  2. Run: ./scripts/deploy-staging.sh"
    else
        log_error "Configuration incomplete. Please fix errors and try again."
        exit 1
    fi
}

# Run main function
main "$@"

