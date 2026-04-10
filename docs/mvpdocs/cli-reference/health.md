# datahub health

Check platform health and run diagnostics.

## Synopsis

```
datahub health [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `health check` | Run a health check |
| `health status` | Show current health status |
| `health diagnostics` | Run platform diagnostics |

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
# Run a health check
datahub health check --format json

# Run platform diagnostics
datahub health diagnostics <id>

# Use verbose output with a specific tenant
datahub health check --tenant acme --verbose
```

## Related

- API: [`/api/v1/health/`](../api-reference/health.md)
- SDK: [`HealthAPI`](../sdk-reference/python/health.md)
