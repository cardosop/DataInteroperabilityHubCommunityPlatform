# datahub tenants

Manage tenants, switch context and list members.

## Synopsis

```
datahub tenants [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `tenants list` | List all tenants |
| `tenants get` | Get a tenant by ID |
| `tenants create` | Create a new tenant |
| `tenants switch` | Switch active tenant |
| `tenants members` | List tenant members |

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
# List all tenants
datahub tenants list --format json

# Get a tenant by ID
datahub tenants get <id>

# Use verbose output with a specific tenant
datahub tenants list --tenant acme --verbose
```

## Related

- API: [`/api/v1/tenants/`](../api-reference/tenants.md)
- SDK: [`TenantsAPI`](../sdk-reference/python/tenants.md)
