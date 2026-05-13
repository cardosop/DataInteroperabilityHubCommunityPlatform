# datahub transformation

Transformation pipeline management commands for data wrangling, pipeline orchestration, and run monitoring.

## Synopsis

```
datahub transformation [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `transformation pipelines list` | List transformation pipelines |
| `transformation pipelines get <id>` | Get pipeline details |
| `transformation pipelines create` | Create a transformation pipeline |
| `transformation pipelines update <id>` | Update a transformation pipeline |
| `transformation pipelines delete <id>` | Delete a transformation pipeline |
| `transformation pipelines validate` | Validate a pipeline configuration |
| `transformation runs list` | List transformation runs |
| `transformation runs get <id>` | Get transformation run details |
| `transformation runs submit` | Submit a new transformation run |
| `transformation runs cancel <id>` | Cancel a running transformation |
| `transformation plan-limits` | Show transformation plan limits and current usage |

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
# List all pipelines
datahub transformation pipelines list

# Create a transformation pipeline
datahub transformation pipelines create --config pipeline.json

# Validate a pipeline configuration
datahub transformation pipelines validate --file pipeline.yaml

# Submit a transformation run
datahub transformation runs submit --pipeline-id <id> --input data.csv

# Cancel a running transformation
datahub transformation runs cancel <run-id>

# Check plan limits
datahub transformation plan-limits
```

## Related

- API: [`/api/v1/transformation/`](../api-reference/transformation.md)
