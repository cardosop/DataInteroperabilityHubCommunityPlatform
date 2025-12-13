#!/bin/bash
# Generate frontend API client from OpenAPI specification

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

OPENAPI_SPEC="${1:-api/openapi-hub-v1.yaml}"
OUTPUT_DIR="${2:-frontend/src/api/generated}"
CLIENT_TYPE="${3:-typescript-axios}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if OpenAPI spec exists
if [ ! -f "$OPENAPI_SPEC" ]; then
    print_error "OpenAPI spec not found at $OPENAPI_SPEC"
    print_info "Generating OpenAPI spec first..."
    
    # Try to generate from running API
    if docker compose -f docker-compose.staging.yml ps api-service 2>&1 | grep -q "Up"; then
        print_info "Fetching OpenAPI spec from running API..."
        mkdir -p "$(dirname "$OPENAPI_SPEC")"
        docker compose -f docker-compose.staging.yml exec -T api-service \
            curl -s http://localhost:8000/api/v1/openapi.yaml > "$OPENAPI_SPEC" 2>&1 || {
            print_error "Failed to fetch OpenAPI spec from API"
            exit 1
        }
    else
        print_error "API service not running. Please start it or provide OpenAPI spec path."
        exit 1
    fi
fi

# Check if openapi-generator is available
if ! command -v openapi-generator &> /dev/null && ! command -v npx &> /dev/null; then
    print_error "openapi-generator not found. Please install it:"
    print_info "  npm install -g @openapitools/openapi-generator-cli"
    exit 1
fi

# Use npx if openapi-generator not directly available
if command -v openapi-generator &> /dev/null; then
    GENERATOR_CMD="openapi-generator"
else
    GENERATOR_CMD="npx @openapitools/openapi-generator-cli"
fi

print_info "Generating frontend API client from OpenAPI spec..."
print_info "Spec: $OPENAPI_SPEC"
print_info "Output: $OUTPUT_DIR"
print_info "Client Type: $CLIENT_TYPE"

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Generate API client based on type
case "$CLIENT_TYPE" in
    typescript-axios)
        print_info "Generating TypeScript Axios client..."
        $GENERATOR_CMD generate \
            -i "$OPENAPI_SPEC" \
            -g typescript-axios \
            -o "$OUTPUT_DIR" \
            --additional-properties=typescriptThreePlus=true,withInterfaces=true,modelPropertyNaming=original,supportsES6=true,enumPropertyNaming=original,stringEnums=true,withSeparateModelsAndApi=true,apiPackage=api,modelPackage=models
        ;;
    typescript-fetch)
        print_info "Generating TypeScript Fetch client..."
        $GENERATOR_CMD generate \
            -i "$OPENAPI_SPEC" \
            -g typescript-fetch \
            -o "$OUTPUT_DIR" \
            --additional-properties=typescriptThreePlus=true,withInterfaces=true,modelPropertyNaming=original,supportsES6=true,enumPropertyNaming=original,stringEnums=true
        ;;
    javascript)
        print_info "Generating JavaScript client..."
        $GENERATOR_CMD generate \
            -i "$OPENAPI_SPEC" \
            -g javascript \
            -o "$OUTPUT_DIR" \
            --additional-properties=supportsES6=true
        ;;
    *)
        print_error "Unknown client type: $CLIENT_TYPE"
        print_info "Supported types: typescript-axios, typescript-fetch, javascript"
        exit 1
        ;;
esac

if [ $? -eq 0 ]; then
    print_info "✅ Frontend API client generated successfully"
    print_info "Generated files are in $OUTPUT_DIR"
    
    # Count generated files
    FILE_COUNT=$(find "$OUTPUT_DIR" -type f \( -name "*.ts" -o -name "*.js" \) 2>/dev/null | wc -l)
    print_info "Generated $FILE_COUNT files"
    
    # Create index file if it doesn't exist
    if [ ! -f "$OUTPUT_DIR/index.ts" ] && [ ! -f "$OUTPUT_DIR/index.js" ]; then
        print_info "Creating index file..."
        if [ "$CLIENT_TYPE" = "typescript-axios" ] || [ "$CLIENT_TYPE" = "typescript-fetch" ]; then
            cat > "$OUTPUT_DIR/index.ts" << 'EOF'
/**
 * Generated API Client
 * 
 * This file is auto-generated from the OpenAPI specification.
 * Do not edit manually.
 */

export * from './api';
export * from './models';
EOF
        fi
    fi
else
    print_error "Failed to generate frontend API client"
    exit 1
fi
