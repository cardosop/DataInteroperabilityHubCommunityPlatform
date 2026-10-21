#!/bin/bash
# Generate API client from OpenAPI spec

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

echo "Generating TypeScript client from OpenAPI spec..."
echo "Spec: $OPENAPI_SPEC"

cd "$SDK_DIR"

npx @openapitools/openapi-generator-cli generate \
  -i "$OPENAPI_SPEC" \
  -g typescript-axios \
  -o ./generated \
  --additional-properties=typescriptThreePlus=true,withInterfaces=true,modelPropertyNaming=original

echo "Generation complete!"
echo "Generated files are in ./generated"

