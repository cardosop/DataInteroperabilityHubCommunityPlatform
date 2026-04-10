# datahub search

Full-text and faceted search across the catalogue.

## Synopsis

```
datahub search [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `search query` | Run a search query |
| `search suggest` | Get search suggestions |
| `search facets` | List available search facets |

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
# Run a search query
datahub search query --format json

# List available search facets
datahub search facets <id>

# Use verbose output with a specific tenant
datahub search query --tenant acme --verbose
```

## Related

- API: [`/api/v1/search/`](../api-reference/search.md)
- SDK: [`SearchAPI`](../sdk-reference/python/search.md)
