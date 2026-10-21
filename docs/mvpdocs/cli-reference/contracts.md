# datahub contracts

Manage and validate data contracts (ODCS/SLA).

## Synopsis

```
datahub contracts [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `contracts list` | List all contracts |
| `contracts get` | Get a contract by ID |
| `contracts create` | Create a new contract |
| `contracts validate` | Validate a contract against its schema |
| `contracts lint` | Lint a contract definition |
| `contracts diff` | Diff two contract versions |

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
# List all contracts
datahub contracts list --format json

# Get a contract by ID
datahub contracts get <id>

# Use verbose output with a specific tenant
datahub contracts list --tenant acme --verbose
```

## Related

- API: [`/api/v1/contracts/`](../api-reference/contracts.md)
- SDK: [`ContractsAPI`](../sdk-reference/python/contracts.md)
