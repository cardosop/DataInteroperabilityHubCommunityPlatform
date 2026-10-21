# SDK Generation Scripts

## Generate API Client

Generate TypeScript client from OpenAPI spec:

```bash
./scripts/generate-api.sh
```

This script:
1. Reads the OpenAPI spec from `../../api/openapi-hub-v1.yaml`
2. Generates TypeScript client using openapi-generator
3. Outputs generated code to `./generated/`

## Prerequisites

- OpenAPI spec must be generated first (via Django drf-spectacular)
- Node.js and npm must be installed
- `@openapitools/openapi-generator-cli` will be installed automatically via npm

