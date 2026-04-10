# datahub dq

Run data-quality checks and review results.

## Synopsis

```
datahub dq [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `dq run` | Run a dq profile check |
| `dq results` | View dq profile results |
| `dq profiles` | Manage dq profile profiles |
| `dq configure` | Configure dq profile settings |

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
# Run a dq profile check
datahub dq run --format json

# Configure dq profile settings
datahub dq configure <id>

# Use verbose output with a specific tenant
datahub dq run --tenant acme --verbose
```

## Related

- API: [`/api/v1/dq/`](../api-reference/dq.md)
- SDK: [`DataQualityAPI`](../sdk-reference/python/dataquality.md)
