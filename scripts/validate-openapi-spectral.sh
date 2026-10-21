#!/bin/bash
# Validate OpenAPI specification using Spectral

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_ROOT"

OPENAPI_SPEC="${1:-api/openapi-hub-v1.yaml}"
SPECTRAL_CONFIG="${PROJECT_ROOT}/.spectral.yaml"

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

# Check if Spectral is installed
if ! command -v spectral &> /dev/null; then
    print_info "Spectral not found. Installing..."
    
    # Try npm install
    if command -v npm &> /dev/null; then
        npm install -g @stoplight/spectral-cli
    elif command -v npx &> /dev/null; then
        print_info "Using npx to run Spectral..."
        SPECTRAL_CMD="npx -y @stoplight/spectral-cli"
    else
        print_error "npm or npx not found. Please install Node.js to use Spectral."
        exit 1
    fi
else
    SPECTRAL_CMD="spectral"
fi

# Create Spectral config if it doesn't exist
if [ ! -f "$SPECTRAL_CONFIG" ]; then
    print_info "Creating Spectral configuration..."
    cat > "$SPECTRAL_CONFIG" << 'EOF'
extends: ["spectral:oas", "spectral:asyncapi"]
rules:
  # OpenAPI rules
  openapi-tags:
    description: "All endpoints must have tags"
    severity: error
  operation-tags:
    description: "All operations must have at least one tag"
    severity: error
  operation-description:
    description: "All operations must have descriptions"
    severity: warn
  operation-operationId:
    description: "All operations must have operationId"
    severity: error
  operation-summary:
    description: "All operations should have summaries"
    severity: warn
  operation-singular-tag:
    description: "Operations should have a single tag"
    severity: warn
  path-params:
    description: "Path parameters must be defined"
    severity: error
  parameter-description:
    description: "All parameters must have descriptions"
    severity: warn
  request-body-name:
    description: "Request body should have a name"
    severity: warn
  response-description:
    description: "All responses must have descriptions"
    severity: error
  response-examples:
    description: "Responses should have examples"
    severity: warn
  schema-description:
    description: "All schemas should have descriptions"
    severity: warn
  # Custom rules for our API
  error-responses:
    description: "Operations should include standard error responses (400, 401, 403, 404, 500)"
    severity: warn
    given: "$.paths[*][*]"
    then:
      field: "responses"
      function: schema
      functionOptions:
        schema:
          type: object
          properties:
            "400":
              type: object
            "401":
              type: object
            "403":
              type: object
            "404":
              type: object
            "500":
              type: object
EOF
    print_info "Created Spectral configuration at $SPECTRAL_CONFIG"
fi

# Run Spectral validation
print_info "Validating OpenAPI spec with Spectral..."
print_info "Spec: $OPENAPI_SPEC"

if [ -n "$SPECTRAL_CMD" ] && [ "$SPECTRAL_CMD" != "spectral" ]; then
    # Using npx
    $SPECTRAL_CMD lint "$OPENAPI_SPEC" --format json > /tmp/spectral-output.json 2>&1 || SPECTRAL_EXIT=$?
else
    # Using installed spectral
    spectral lint "$OPENAPI_SPEC" --format json > /tmp/spectral-output.json 2>&1 || SPECTRAL_EXIT=$?
fi

# Check results
if [ -f /tmp/spectral-output.json ]; then
    ERROR_COUNT=$(python3 -c "import json, sys; data=json.load(open('/tmp/spectral-output.json')); print(len([r for r in data if r.get('severity') in [0, 1]]))" 2>/dev/null || echo "0")
    WARNING_COUNT=$(python3 -c "import json, sys; data=json.load(open('/tmp/spectral-output.json')); print(len([r for r in data if r.get('severity') == 2]))" 2>/dev/null || echo "0")
    
    if [ "$ERROR_COUNT" -gt 0 ] || [ "${SPECTRAL_EXIT:-0}" -ne 0 ]; then
        print_error "Spectral validation found $ERROR_COUNT errors and $WARNING_COUNT warnings"
        
        # Show errors
        if [ "$ERROR_COUNT" -gt 0 ]; then
            print_error "Errors:"
            python3 -c "
import json
with open('/tmp/spectral-output.json') as f:
    results = json.load(f)
    for r in results:
        if r.get('severity') in [0, 1]:  # Error or fatal
            print(f\"  {r.get('code', 'N/A')}: {r.get('message', 'N/A')} at {r.get('path', 'N/A')}\")
" 2>/dev/null || cat /tmp/spectral-output.json
        fi
        
        exit 1
    else
        print_info "✅ Spectral validation passed"
        if [ "$WARNING_COUNT" -gt 0 ]; then
            print_warn "Found $WARNING_COUNT warnings (non-blocking)"
        fi
        exit 0
    fi
else
    print_error "Spectral validation failed - no output generated"
    exit 1
fi
