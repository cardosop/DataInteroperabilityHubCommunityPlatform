#!/usr/bin/env bash
# Regenerate sdk/typescript from the committed OpenAPI baseline (Phase 231.9+).
#
# Why not package.json → api/openapi-hub-v1.yaml?
#   That file is often absent locally (not committed / generated elsewhere).
#   Baseline JSON is the contract artifact from:
#     docker compose run --rm --no-deps api-service \
#       python scripts/contract_test_openapi.py --update-baseline
#
# Requires: Docker (OpenAPI Generator runs in openapitools/openapi-generator-cli).
# --skip-validate-spec: baseline uses constructs (e.g. response schema "content")
# that openapi-generator's strict validator rejects; generation still succeeds.

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

mkdir -p "${ROOT}/sdk/typescript"

exec docker run --rm \
  -u "$(id -u):$(id -g)" \
  -v "${ROOT}:/local" \
  openapitools/openapi-generator-cli:v7.14.0 generate \
  --skip-validate-spec \
  -i /local/docs/api/openapi-baseline.json \
  -g typescript-axios \
  -o /local/sdk/typescript \
  --additional-properties=typescriptThreePlus=true,withInterfaces=true
