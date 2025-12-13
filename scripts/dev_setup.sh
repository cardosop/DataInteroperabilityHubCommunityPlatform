#!/bin/bash
#
# Development Environment Setup Script
#
# This script sets up the development environment including:
# - Python virtual environment
# - Dependencies installation
# - Pre-commit hooks
# - Database setup
#
# Usage:
#   ./scripts/dev_setup.sh [--skip-db] [--skip-pre-commit]
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SKIP_DB=false
SKIP_PRE_COMMIT=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-db)
            SKIP_DB=true
            shift
            ;;
        --skip-pre-commit)
            SKIP_PRE_COMMIT=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

main() {
    log_info "=========================================="
    log_info "Development Environment Setup"
    log_info "=========================================="
    log_info ""
    
    # Check Python version
    log_info "Checking Python version..."
    if ! python3 --version | grep -E "Python 3\.(12|13|14)"; then
        log_error "Python 3.12+ required. Found: $(python3 --version)"
        exit 1
    fi
    log_info "✓ Python version OK"
    
    # Create virtual environment
    if [ ! -d "venv" ]; then
        log_info "Creating virtual environment..."
        python3 -m venv venv
        log_info "✓ Virtual environment created"
    else
        log_info "✓ Virtual environment already exists"
    fi
    
    # Activate virtual environment
    log_info "Activating virtual environment..."
    source venv/bin/activate
    
    # Upgrade pip
    log_info "Upgrading pip..."
    pip install --upgrade pip setuptools wheel
    
    # Install dependencies
    log_info "Installing dependencies..."
    pip install -r requirements.txt
    pip install -r requirements-dev.txt
    log_info "✓ Dependencies installed"
    
    # Install pre-commit hooks
    if [ "$SKIP_PRE_COMMIT" = false ]; then
        log_info "Installing pre-commit hooks..."
        pre-commit install
        log_info "✓ Pre-commit hooks installed"
    else
        log_warn "Skipping pre-commit hooks installation"
    fi
    
    # Setup database (if not skipped)
    if [ "$SKIP_DB" = false ]; then
        log_info "Setting up database..."
        if docker compose ps postgres | grep -q "Up"; then
            log_info "PostgreSQL is running, running migrations..."
            python hub/manage.py migrate
            log_info "✓ Database migrations completed"
        else
            log_warn "PostgreSQL is not running. Start with: docker compose up -d postgres"
        fi
    else
        log_warn "Skipping database setup"
    fi
    
    log_info ""
    log_info "=========================================="
    log_info "✓ Development environment setup complete!"
    log_info "=========================================="
    log_info ""
    log_info "Next steps:"
    log_info "  1. Activate virtual environment: source venv/bin/activate"
    log_info "  2. Start services: docker compose up -d"
    log_info "  3. Run migrations: python hub/manage.py migrate"
    log_info "  4. Start development server: python hub/manage.py runserver"
}

main

