#!/bin/bash
# Fetch and save OpenAPI specification from running API

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

OUTPUT_DIR="${1:-api}"
FORMAT="${2:-yaml}"

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

# Check if API service is running
if ! docker compose -f docker-compose.staging.yml ps api-service 2>&1 | grep -q "Up"; then
    print_error "API service is not running"
    print_info "Start it with: docker compose -f docker-compose.staging.yml up -d api-service"
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Determine file extension and content type
if [ "$FORMAT" = "yaml" ] || [ "$FORMAT" = "yml" ]; then
    OUTPUT_FILE="${OUTPUT_DIR}/openapi-hub-v1.yaml"
    CONTENT_TYPE="application/x-yaml"
    URL_SUFFIX="?format=yaml"
else
    OUTPUT_FILE="${OUTPUT_DIR}/openapi-hub-v1.json"
    CONTENT_TYPE="application/json"
    URL_SUFFIX=""
fi

print_info "Fetching OpenAPI specification..."
print_info "Format: $FORMAT"
print_info "Output: $OUTPUT_FILE"

# Fetch OpenAPI spec
docker compose -f docker-compose.staging.yml exec -T api-service \
    curl -s "http://localhost:8000/api/v1/openapi.json${URL_SUFFIX}" \
    -H "Accept: ${CONTENT_TYPE}" > "$OUTPUT_FILE" 2>&1

if [ $? -eq 0 ] && [ -s "$OUTPUT_FILE" ]; then
    # Validate it's valid JSON/YAML
    if [ "$FORMAT" = "yaml" ] || [ "$FORMAT" = "yml" ]; then
        python3 -c "import yaml; yaml.safe_load(open('$OUTPUT_FILE'))" 2>/dev/null || {
            print_error "Invalid YAML in fetched spec"
            exit 1
        }
    else
        python3 -c "import json; json.load(open('$OUTPUT_FILE'))" 2>/dev/null || {
            print_error "Invalid JSON in fetched spec"
            exit 1
        }
    fi
    
    FILE_SIZE=$(wc -c < "$OUTPUT_FILE")
    print_info "✅ OpenAPI spec saved successfully"
    print_info "   File: $OUTPUT_FILE"
    print_info "   Size: $FILE_SIZE bytes"
    
    # Show basic stats
    if command -v python3 &> /dev/null; then
        if [ "$FORMAT" = "yaml" ] || [ "$FORMAT" = "yml" ]; then
            python3 << EOF
import yaml
with open('$OUTPUT_FILE') as f:
    spec = yaml.safe_load(f)
    print(f"   OpenAPI Version: {spec.get('openapi', 'N/A')}")
    print(f"   Title: {spec.get('info', {}).get('title', 'N/A')}")
    print(f"   Paths: {len(spec.get('paths', {}))}")
    print(f"   Schemas: {len(spec.get('components', {}).get('schemas', {}))}")
EOF
        else
            python3 << EOF
import json
with open('$OUTPUT_FILE') as f:
    spec = json.load(f)
    print(f"   OpenAPI Version: {spec.get('openapi', 'N/A')}")
    print(f"   Title: {spec.get('info', {}).get('title', 'N/A')}")
    print(f"   Paths: {len(spec.get('paths', {}))}")
    print(f"   Schemas: {len(spec.get('components', {}).get('schemas', {}))}")
EOF
        fi
    fi
else
    print_error "Failed to fetch OpenAPI spec"
    exit 1
fi
