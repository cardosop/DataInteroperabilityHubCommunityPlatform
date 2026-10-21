#!/bin/bash
# Generate Python API client from OpenAPI spec

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SDK_DIR="$(dirname "$SCRIPT_DIR")"
ROOT_DIR="$(dirname "$SDK_DIR")"

OPENAPI_SPEC="${ROOT_DIR}/api/openapi-hub-v1.yaml"

if [ ! -f "$OPENAPI_SPEC" ]; then
  echo "Error: OpenAPI spec not found at $OPENAPI_SPEC"
  echo "Please generate the OpenAPI spec first using drf-spectacular"
  exit 1
fi

echo "Generating Python client from OpenAPI spec..."
echo "Spec: $OPENAPI_SPEC"

cd "$SDK_DIR"

# Use openapi-generator if available, otherwise use docker
if command -v openapi-generator &> /dev/null; then
    openapi-generator generate \
        -i "$OPENAPI_SPEC" \
        -g python \
        -o ./generated \
        --additional-properties=packageName=datahub_interoperability.generated,packageVersion=1.0.0,library=httpx
else
    echo "openapi-generator not found. Using Docker..."
    docker run --rm \
        -v "${ROOT_DIR}:/local" \
        openapitools/openapi-generator-cli generate \
        -i "/local/api/openapi-hub-v1.yaml" \
        -g python \
        -o "/local/sdk/python/generated" \
        --additional-properties=packageName=datahub_interoperability.generated,packageVersion=1.0.0,library=httpx
fi

echo "Generation complete!"
echo "Generated files are in ./generated"

