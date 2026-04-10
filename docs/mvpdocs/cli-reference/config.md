# datahub config

Read and write CLI and tenant configuration.

## Synopsis

```
datahub config [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `config get` | Get a config by ID |
| `config set` | Set a configuration value |
| `config list` | List all configs |
| `config reset` | Reset configuration to defaults |
| `config show` | Show current configuration |

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
# Get a config by ID
datahub config get --format json

# Get a config by ID
datahub config get <id>

# Use verbose output with a specific tenant
datahub config get --tenant acme --verbose
```

## Related

- API: [`/api/v1/config/`](../api-reference/config.md)
- SDK: [`ConfigAPI`](../sdk-reference/python/config.md)
