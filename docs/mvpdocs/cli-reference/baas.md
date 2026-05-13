# datahub baas

BaaS (Backend as a Service) management commands for API keys, usage tracking, developer portal docs, customer management, and billing reports.

## Synopsis

```
datahub baas [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `baas api-keys create` | Create a new API key |
| `baas api-keys list` | List API keys |
| `baas api-keys get <id>` | Get API key details |
| `baas api-keys update <id>` | Update an API key |
| `baas api-keys revoke <id>` | Revoke an API key (soft delete) |
| `baas api-keys rotate <id>` | Rotate an API key with grace period |
| `baas usage stats` | Get usage statistics |
| `baas usage by-endpoint` | Get usage breakdown by endpoint |
| `baas usage by-tenant` | Get usage breakdown by tenant (admin only) |
| `baas docs show` | Display API documentation |
| `baas docs openapi` | Display OpenAPI schema |
| `baas docs sdks` | Display SDK download links |
| `baas customers list` | List BaaS customers |
| `baas customers usage <id>` | Get usage for a specific customer |
| `baas billing-reports list` | List billing reports |
| `baas billing-reports get <id>` | Get billing report details |
| `baas billing-reports generate` | Generate a billing report |
| `baas billing-reports finalize <id>` | Finalize a billing report |
| `baas billing-reports export <id>` | Export a billing report |
| `baas billing-reports send <id>` | Send a billing report via email |

## Common Options

| Flag | Description |
|------|-------------|
| `--format json\|table\|yaml` | Output format (default: table) |
| `--tenant <slug>` | Tenant context override |
| `-v, --verbose` | Verbose output |
| `--no-color` | Disable coloured output |
| `--timeout <seconds>` | Request timeout (default: 30) |

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments |
| 3 | Authentication failure |
| 4 | Resource not found |

## Examples

```bash
# Create an API key
datahub baas api-keys create --name "my-app-key" --tier PRO

# List all API keys
datahub baas api-keys list

# View usage statistics
datahub baas usage stats --format json

# Generate a billing report
datahub baas billing-reports generate --period 2026-04

# Export a finalized billing report
datahub baas billing-reports export <report-id> --format pdf

# Rotate an expiring API key
datahub baas api-keys rotate <key-id> --grace-days 7
```

## Related

- API: [`/api/v1/baas/`](../api-reference/baas.md)
