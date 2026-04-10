# datahub billing

View usage, invoices, quotas and plan details.

## Synopsis

```
datahub billing [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `billing usage` | View current usage metrics |
| `billing invoices` | List invoices |
| `billing quotas` | View quota limits and consumption |
| `billing upgrade` | Upgrade the current plan |

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
# View current usage metrics
datahub billing usage --format json

# Upgrade the current plan
datahub billing upgrade <id>

# Use verbose output with a specific tenant
datahub billing usage --tenant acme --verbose
```

## Related

- API: [`/api/v1/billing/`](../api-reference/billing.md)
- SDK: [`BillingAPI`](../sdk-reference/python/billing.md)
