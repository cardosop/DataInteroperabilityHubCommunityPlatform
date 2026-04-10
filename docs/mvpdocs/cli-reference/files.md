# datahub files

Upload, download and manage files attached to assets.

## Synopsis

```
datahub files [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `files list` | List all files |
| `files get` | Get a file by ID |
| `files upload` | Upload a file |
| `files download` | Download a file |
| `files delete` | Delete a file |

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
# List all files
datahub files list --format json

# Get a file by ID
datahub files get <id>

# Use verbose output with a specific tenant
datahub files list --tenant acme --verbose
```

## Related

- API: [`/api/v1/files/`](../api-reference/files.md)
- SDK: [`FilesAPI`](../sdk-reference/python/files.md)
