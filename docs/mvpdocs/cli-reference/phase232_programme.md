# datahub phase232-programme

Phase 232 compliance programme — catalogue and lightweight list probes for the seven compliance surfaces (breach, consent, DPIA, DSAR, processor agreements, RoPA, and public portal).

## Synopsis

```
datahub phase232-programme [OPTIONS] COMMAND [ARGS]...
```

## Subcommands

| Command | Description |
|---------|-------------|
| `phase232-programme catalogue` | Print canonical list endpoints for all seven programme surfaces (no HTTP) |
| `phase232-programme probe-lists` | GET each list endpoint with `--limit` (requires login or API key) |

## Options

| Flag | Description |
|------|-------------|
| `--limit <n>` | Max items per probe (default: 10) — used with `probe-lists` |

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
# Print all compliance surface endpoints (offline)
datahub phase232-programme catalogue

# Probe all list endpoints with a limit of 20 items each
datahub phase232-programme probe-lists --limit 20

# Probe with verbose output
datahub phase232-programme probe-lists --limit 5 --verbose
```

## Programme Surfaces

The seven Phase 232 compliance programme surfaces:

| Surface | List endpoint |
|---------|--------------|
| Breach | `/api/v1/breach/` |
| Consent | `/api/v1/consent/` |
| DPIA | `/api/v1/dpia/` |
| DSAR | `/api/v1/dsar/` |
| Processor Agreements | `/api/v1/processor-agreements/` |
| RoPA | `/api/v1/ropa/` |
| Public Portal | Public-facing compliance pages |

## Related

- API: [`/api/v1/`](../api-reference/index.md)
- Compliance docs: [`docs/mvpdocs/concepts/compliance-runs.md`](../concepts/compliance-runs.md)
