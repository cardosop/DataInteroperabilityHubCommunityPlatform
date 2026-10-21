# datahub governance

Manage governance policies, retention rules and consent.

## Synopsis

```
datahub governance [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `governance policies` | Manage governance policies |
| `governance retention` | Manage retention rules |
| `governance consent` | Manage consent records |

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
# Manage governance policies
datahub governance policies --format json

# Manage consent records
datahub governance consent <id>

# Use verbose output with a specific tenant
datahub governance policies --tenant acme --verbose
```

## Related

- API: [`/api/v1/governance/`](../api-reference/governance.md)
- SDK: [`GovernanceAPI`](../sdk-reference/python/governance.md)
