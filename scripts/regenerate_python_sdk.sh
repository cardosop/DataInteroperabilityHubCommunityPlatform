#!/usr/bin/env bash
# Regenerate sdk/python from the committed OpenAPI baseline (Phase 277.B.103).
#
# Uses the same baseline JSON as regenerate_typescript_sdk.sh.
# Requires: Docker (OpenAPI Generator runs in openapitools/openapi-generator-cli).
#
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASELINE="${ROOT}/docs/api/openapi-baseline.json"

if [[ ! -f "${BASELINE}" ]]; then
  echo "Missing ${BASELINE}" >&2
  echo "Generate it with: docker compose run --rm --no-deps api-service \\" >&2
  echo "  python scripts/contract_test_openapi.py --update-baseline" >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required to run openapi-generator-cli" >&2
  exit 1
fi

mkdir -p "${ROOT}/sdk/python_generated"

docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "${ROOT}:/local" \
  openapitools/openapi-generator-cli:v7.14.0 generate \
  --skip-validate-spec \
  -i /local/docs/api/openapi-baseline.json \
  -g python \
  -o /local/sdk/python_generated \
  --additional-properties=packageName=datahub_interoperability,projectName=datahub-interoperability-sdk,packageVersion="${SDK_VERSION:-0.0.0-dev}"

echo "Python SDK regenerated at sdk/python_generated/"
