# datahub semantic

Semantic layer: resolve terms, SPARQL queries, browse.

## Synopsis

```
datahub semantic [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `semantic resolve` | Resolve a semantic term |
| `semantic sparql` | Execute a SPARQL query |
| `semantic browse` | Browse the semantic layer |

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
# Resolve a semantic term
datahub semantic resolve --format json

# Browse the semantic layer
datahub semantic browse <id>

# Use verbose output with a specific tenant
datahub semantic resolve --tenant acme --verbose
```

## Related

- API: [`/api/v1/semantic/`](../api-reference/semantic.md)
- SDK: [`SemanticAPI`](../sdk-reference/python/semantic.md)
