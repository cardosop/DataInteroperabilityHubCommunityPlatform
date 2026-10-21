#!/bin/bash
#
# Build and Scan Docker Images Script
#
# This script builds Docker images for all services and performs security scanning.
# Supports Trivy and Snyk scanning, and cosign signing.
#
# Usage:
#   ./scripts/build_and_scan_images.sh [--service SERVICE] [--scan-only] [--sign] [--registry REGISTRY]
#

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SERVICE=""
SCAN_ONLY=false
SIGN=false
REGISTRY="${REGISTRY:-ghcr.io}"
IMAGE_PREFIX="${IMAGE_PREFIX:-datainteroperabilityhub}"
TRIVY_ENABLED=true
SNYK_ENABLED=false
COSIGN_ENABLED=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --service)
            SERVICE="$2"
            shift 2
            ;;
        --scan-only)
            SCAN_ONLY=true
            shift
            ;;
        --sign)
            SIGN=true
            COSIGN_ENABLED=true
            shift
            ;;
        --registry)
            REGISTRY="$2"
            shift 2
            ;;
        --no-trivy)
            TRIVY_ENABLED=false
            shift
            ;;
        --snyk)
            SNYK_ENABLED=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

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
        log_error "Docker not found. Please install Docker."
        exit 1
    fi
    
    # Check Trivy
    if [ "$TRIVY_ENABLED" = true ]; then
        if ! command -v trivy &> /dev/null; then
            log_warn "Trivy not found. Install with: brew install trivy (macOS) or see https://aquasecurity.github.io/trivy/latest/getting-started/installation/"
            TRIVY_ENABLED=false
        fi
    fi
    
    # Check Snyk
    if [ "$SNYK_ENABLED" = true ]; then
        if ! command -v snyk &> /dev/null; then
            log_warn "Snyk not found. Install with: npm install -g snyk"
            SNYK_ENABLED=false
        fi
    fi
    
    # Check cosign
    if [ "$COSIGN_ENABLED" = true ]; then
        if ! command -v cosign &> /dev/null; then
            log_warn "cosign not found. Install with: brew install cosign (macOS) or see https://docs.sigstore.dev/cosign/installation/"
            COSIGN_ENABLED=false
        fi
    fi
    
    log_info "Prerequisites check complete."
}

build_image() {
    local service_name=$1
    local dockerfile=$2
    local context=$3
    local tag="${REGISTRY}/${IMAGE_PREFIX}-${service_name}:latest"
    
    log_info "Building image: $tag"
    
    if docker build -f "$dockerfile" -t "$tag" "$context"; then
        log_info "✓ Image built successfully: $tag"
        return 0
    else
        log_error "✗ Image build failed: $tag"
        return 1
    fi
}

scan_with_trivy() {
    local image_tag=$1
    
    if [ "$TRIVY_ENABLED" = false ]; then
        return 0
    fi
    
    log_info "Scanning with Trivy: $image_tag"
    
    if trivy image --severity HIGH,CRITICAL --exit-code 1 "$image_tag"; then
        log_info "✓ Trivy scan passed: $image_tag"
        return 0
    else
        log_error "✗ Trivy scan found vulnerabilities: $image_tag"
        return 1
    fi
}

scan_with_snyk() {
    local image_tag=$1
    
    if [ "$SNYK_ENABLED" = false ]; then
        return 0
    fi
    
    log_info "Scanning with Snyk: $image_tag"
    
    if snyk container test "$image_tag" --severity-threshold=high; then
        log_info "✓ Snyk scan passed: $image_tag"
        return 0
    else
        log_warn "⚠ Snyk scan found issues: $image_tag"
        return 0  # Don't fail on Snyk warnings
    fi
}

sign_image() {
    local image_tag=$1
    
    if [ "$COSIGN_ENABLED" = false ]; then
        return 0
    fi
    
    log_info "Signing image with cosign: $image_tag"
    
    if cosign sign "$image_tag"; then
        log_info "✓ Image signed successfully: $image_tag"
        return 0
    else
        log_warn "⚠ Image signing failed (may need COSIGN_PASSWORD or key): $image_tag"
        return 0  # Don't fail on signing errors
    fi
}

process_service() {
    local service_name=$1
    local dockerfile=$2
    local context=$3
    local image_tag="${REGISTRY}/${IMAGE_PREFIX}-${service_name}:latest"
    
    log_info "=========================================="
    log_info "Processing: $service_name"
    log_info "=========================================="
    
    local errors=0
    
    # Build image
    if [ "$SCAN_ONLY" = false ]; then
        if ! build_image "$service_name" "$dockerfile" "$context"; then
            ((errors++))
            return $errors
        fi
    fi
    
    # Scan with Trivy
    if ! scan_with_trivy "$image_tag"; then
        ((errors++))
    fi
    
    # Scan with Snyk
    if ! scan_with_snyk "$image_tag"; then
        # Snyk warnings don't fail the build
        :
    fi
    
    # Sign image
    if [ "$SIGN" = true ]; then
        if ! sign_image "$image_tag"; then
            # Signing errors don't fail the build
            :
        fi
    fi
    
    return $errors
}

main() {
    log_info "=========================================="
    log_info "Docker Image Build and Scan"
    log_info "=========================================="
    log_info ""
    
    # Pre-flight checks
    check_prerequisites
    
    # Define services
    declare -A services=(
        ["prefect-integration"]="services/prefect-integration/Dockerfile:."
        ["search-service"]="services/search-service/Dockerfile:."
        ["observability-service"]="services/observability-service/Dockerfile:."
        ["webhook-service"]="services/webhook-service/Dockerfile:."
    )
    
    local total_errors=0
    
    # Process services
    if [ -n "$SERVICE" ]; then
        if [[ -v services["$SERVICE"] ]]; then
            IFS=':' read -r dockerfile context <<< "${services[$SERVICE]}"
            process_service "$SERVICE" "$dockerfile" "$context" || total_errors=$?
        else
            log_error "Unknown service: $SERVICE"
            exit 1
        fi
    else
        # Process all services
        for service_name in "${!services[@]}"; do
            IFS=':' read -r dockerfile context <<< "${services[$service_name]}"
            process_service "$service_name" "$dockerfile" "$context" || total_errors=$?
            log_info ""
        done
    fi
    
    log_info "=========================================="
    if [ $total_errors -eq 0 ]; then
        log_info "✓ All images processed successfully"
    else
        log_error "✗ $total_errors error(s) occurred"
        exit 1
    fi
    log_info "=========================================="
}

# Run main function
main

