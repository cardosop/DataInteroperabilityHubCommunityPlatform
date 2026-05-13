# datahub scheduled-ingestion

Scheduled ingestion management commands for recurring data ingestion from external sources (S3, GCS, Azure Blob, HTTP, FTP, SFTP, Database).

## Synopsis

```
datahub scheduled-ingestion [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `scheduled-ingestion list` | List scheduled ingestions |
| `scheduled-ingestion get <id>` | Get scheduled ingestion details |
| `scheduled-ingestion create` | Create a scheduled ingestion |
| `scheduled-ingestion update <id>` | Update a scheduled ingestion |
| `scheduled-ingestion trigger <id>` | Manually trigger a scheduled ingestion run |
| `scheduled-ingestion runs <id>` | List runs for a scheduled ingestion |
| `scheduled-ingestion run-detail <id>` | Get run details for a scheduled ingestion run |

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
# List all scheduled ingestions
datahub scheduled-ingestion list

# Create a scheduled ingestion from a JSON config
datahub scheduled-ingestion create --config ingestion-config.json

# Manually trigger an ingestion run
datahub scheduled-ingestion trigger <ingestion-id>

# View recent runs
datahub scheduled-ingestion runs <ingestion-id> --limit 10

# Get run details
datahub scheduled-ingestion run-detail <run-id> --format json
```

## Related

- API: [`/api/v1/scheduled-ingestions/`](../api-reference/scheduled-ingestions.md)
