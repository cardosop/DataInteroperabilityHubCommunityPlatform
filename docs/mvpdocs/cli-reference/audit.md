# datahub audit

Query and export the audit log.

## Synopsis

```
datahub audit [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `audit list` | List all audit entrys |
| `audit export` | Export audit entry data |
| `audit filter` | Filter audit entry entries |

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
# List all audit entrys
datahub audit list --format json

# Filter audit entry entries
datahub audit filter <id>

# Use verbose output with a specific tenant
datahub audit list --tenant acme --verbose
```

## Related

- API: [`/api/v1/audit/`](../api-reference/audit.md)
- SDK: [`AuditAPI`](../sdk-reference/python/audit.md)
