# datahub virtualization

Virtualization management commands for virtual datasets, query execution, and topology exploration.

## Synopsis

```
datahub virtualization [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `virtualization info` | Get virtualization information |
| `virtualization datasets list` | List virtual datasets with filtering and pagination |
| `virtualization datasets create` | Create a new virtual dataset from a JSON file |
| `virtualization datasets get <id>` | Get virtual dataset details by ID |
| `virtualization datasets update <id>` | Update an existing virtual dataset |
| `virtualization datasets delete <id>` | Delete a virtual dataset |
| `virtualization queries execute` | Execute a query on a virtual dataset |
| `virtualization queries list` | List query executions with filtering |
| `virtualization queries get <id>` | Get query execution details by ID |
| `virtualization queries cancel <id>` | Cancel a running or pending query execution |
| `virtualization queries result <id>` | Get query execution result |
| `virtualization topology get` | Get complete virtualization topology |
| `virtualization topology get-dataset <id>` | Get topology view for a specific virtual dataset |

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
# List all virtual datasets
datahub virtualization datasets list

# Create a virtual dataset
datahub virtualization datasets create --file dataset-definition.json

# Execute a query
datahub virtualization queries execute --dataset-id <id> --sql "SELECT * FROM table"

# Get query result
datahub virtualization queries result <query-id> --format csv

# View topology
datahub virtualization topology get --format json
```

## Related

- API: [`/api/v1/virtualization/`](../api-reference/virtualization.md)
