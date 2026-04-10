# datahub marketplace

Browse listings, place orders and manage entitlements.

## Synopsis

```
datahub marketplace [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `marketplace listings` | Browse marketplace listings |
| `marketplace orders` | Manage marketplace orders |
| `marketplace entitlements` | View and manage entitlements |

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
# Browse marketplace listings
datahub marketplace listings --format json

# View and manage entitlements
datahub marketplace entitlements <id>

# Use verbose output with a specific tenant
datahub marketplace listings --tenant acme --verbose
```

## Related

- API: [`/api/v1/marketplace/`](../api-reference/marketplace.md)
- SDK: [`MarketplaceAPI`](../sdk-reference/python/marketplace.md)
