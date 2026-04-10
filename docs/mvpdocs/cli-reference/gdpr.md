# datahub gdpr

GDPR data-subject requests: export, erase, consent.

## Synopsis

```
datahub gdpr [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `gdpr export` | Export GDPR request data |
| `gdpr erase` | Submit an erasure request |
| `gdpr consent` | Manage consent records |
| `gdpr status` | Show current GDPR request status |

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
# Export GDPR request data
datahub gdpr export --format json

# Show current GDPR request status
datahub gdpr status <id>

# Use verbose output with a specific tenant
datahub gdpr export --tenant acme --verbose
```

## Related

- API: [`/api/v1/gdpr/`](../api-reference/gdpr.md)
- SDK: [`GDPRAPI`](../sdk-reference/python/gdpr.md)
