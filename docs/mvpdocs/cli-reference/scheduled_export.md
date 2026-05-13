# datahub scheduled-export

Scheduled export management commands for recurring data exports to external destinations (S3, GCS, Azure Blob, Snowflake, BigQuery, Databricks, Athena).

## Synopsis

```
datahub scheduled-export [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `scheduled-export list` | List scheduled exports |
| `scheduled-export get <id>` | Get scheduled export details |
| `scheduled-export create` | Create a scheduled export |
| `scheduled-export update <id>` | Update a scheduled export |
| `scheduled-export trigger <id>` | Manually trigger a scheduled export run |
| `scheduled-export runs <id>` | List runs for a scheduled export |
| `scheduled-export run-detail <id>` | Get run details for a scheduled export run |

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
# List all scheduled exports
datahub scheduled-export list

# Create a scheduled export from a JSON config
datahub scheduled-export create --config export-config.json

# Manually trigger an export run
datahub scheduled-export trigger <export-id>

# View recent runs
datahub scheduled-export runs <export-id> --limit 10

# Get run details
datahub scheduled-export run-detail <run-id> --format json
```

## Related

- API: [`/api/v1/scheduled-exports/`](../api-reference/scheduled-exports.md)
