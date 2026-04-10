# datahub assets

Manage data assets (datasets, files, schemas).

## Synopsis

```
datahub assets [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `assets list` | List all assets |
| `assets get` | Get an asset by ID |
| `assets create` | Create a new asset |
| `assets update` | Update an existing asset |
| `assets archive` | Archive an asset |
| `assets publish` | Publish an asset |

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
# List all assets
datahub assets list --format json

# Get an asset by ID
datahub assets get <id>

# Use verbose output with a specific tenant
datahub assets list --tenant acme --verbose
```

## Related

- API: [`/api/v1/assets/`](../api-reference/assets.md)
- SDK: [`AssetsAPI`](../sdk-reference/python/assets.md)
