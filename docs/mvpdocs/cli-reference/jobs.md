# datahub jobs

Monitor and control background jobs and tasks.

## Synopsis

```
datahub jobs [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `jobs list` | List all jobs |
| `jobs get` | Get a job by ID |
| `jobs status` | Show current job status |
| `jobs cancel` | Cancel a running job |
| `jobs logs` | Stream logs for a job |

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
# List all jobs
datahub jobs list --format json

# Get a job by ID
datahub jobs get <id>

# Use verbose output with a specific tenant
datahub jobs list --tenant acme --verbose
```

## Related

- API: [`/api/v1/jobs/`](../api-reference/jobs.md)
- SDK: [`JobsAPI`](../sdk-reference/python/jobs.md)
