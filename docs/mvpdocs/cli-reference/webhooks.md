# datahub webhooks

Register, test and manage webhook endpoints.

## Synopsis

```
datahub webhooks [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `webhooks list` | List all webhooks |
| `webhooks create` | Create a new webhook |
| `webhooks test` | Send a test event to a webhook |
| `webhooks delete` | Delete a webhook |

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
# List all webhooks
datahub webhooks list --format json

# Delete a webhook
datahub webhooks delete <id>

# Use verbose output with a specific tenant
datahub webhooks list --tenant acme --verbose
```

## Related

- API: [`/api/v1/webhooks/`](../api-reference/webhooks.md)
- SDK: [`WebhooksAPI`](../sdk-reference/python/webhooks.md)
