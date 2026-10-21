# datahub mesh

Data Mesh management commands for domains, topology, policies, and compliance.

## Synopsis

```
datahub mesh [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `mesh info` | Get data mesh information |
| `mesh domains list` | List data mesh domains with filtering and pagination |
| `mesh domains create` | Create a new data mesh domain |
| `mesh domains get <id>` | Get domain details by ID |
| `mesh domains update <id>` | Update an existing data mesh domain |
| `mesh domains delete <id>` | Delete a data mesh domain |
| `mesh topology get` | Get complete data mesh topology |
| `mesh topology get-domain <id>` | Get topology view for a specific domain |
| `mesh policies apply` | Apply a policy to a data mesh domain |
| `mesh policies list` | List policies applied to a domain |
| `mesh policies remove` | Remove a policy from a domain |
| `mesh compliance check <id>` | Check compliance status for a domain |
| `mesh compliance report <id>` | Get compliance report for a domain |

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
# List all domains
datahub mesh domains list

# Create a new domain
datahub mesh domains create --name "Customer 360" --description "Customer data products"

# View full topology
datahub mesh topology get --format json

# Check domain compliance
datahub mesh compliance check <domain-id>

# Apply a policy to a domain
datahub mesh policies apply --domain-id <id> --policy "data-retention-90d"
```

## Related

- API: [`/api/v1/mesh/`](../api-reference/mesh.md)
