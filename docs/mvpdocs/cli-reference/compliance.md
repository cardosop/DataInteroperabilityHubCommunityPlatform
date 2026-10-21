# datahub compliance

Scan assets for compliance violations and review results.

## Synopsis

```
datahub compliance [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `compliance scan` | Run a compliance scan |
| `compliance results` | View compliance results |
| `compliance profiles` | Manage compliance profiles |
| `compliance configure` | Configure compliance settings |

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
# Run a compliance scan
datahub compliance scan --format json

# Configure compliance settings
datahub compliance configure <id>

# Use verbose output with a specific tenant
datahub compliance scan --tenant acme --verbose
```

## Related

- API: [`/api/v1/compliance/`](../api-reference/compliance.md)
- SDK: [`ComplianceAPI`](../sdk-reference/python/compliance.md)
