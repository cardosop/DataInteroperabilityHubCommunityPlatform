# datahub lineage

Explore data lineage and dependency graphs.

## Synopsis

```
datahub lineage [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `lineage list` | List all lineages |
| `lineage get` | Get a lineage by ID |
| `lineage trace` | Trace lineage upstream or downstream |
| `lineage visualize` | Render a lineage graph |

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
# List all lineages
datahub lineage list --format json

# Get a lineage by ID
datahub lineage get <id>

# Use verbose output with a specific tenant
datahub lineage list --tenant acme --verbose
```

## Related

- API: [`/api/v1/lineage/`](../api-reference/lineage.md)
- SDK: [`LineageAPI`](../sdk-reference/python/lineage.md)
