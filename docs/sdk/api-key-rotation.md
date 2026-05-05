# SDK API key rotation cadence

**Phase**: 250.4.7
**Last reviewed**: 2026-05-04
**Cadence**: 90 days

The Meshant Python SDK authenticates against the hub via an
`Authorization: Bearer <api_token>` header (or the equivalent
`ApiKey <key>` header for service-to-service tokens). Both the
user-facing `api_token` and the service-to-service
`INTERNAL_API_KEY` (used by the Phase 240 DQ worker → hub
callback path) rotate on the **same 90-day cadence** as the DQ
service per Phase 240.1.D.

## Rotation policy

| Key type | Used by | Rotation cadence | Owner |
|---|---|---|---|
| User API token | Interactive callers (data engineers, CLI) | 90 days OR on suspected leak | User self-rotation via UI |
| `INTERNAL_API_KEY` | DQ worker → hub callback (Phase 240 + 250.4 SDK ↔ hub) | 90 days OR on suspected leak | Platform SRE rotation |
| Worker API key (`HUB_WORKER_API_KEY`) | Scheduled-ingestion worker → hub `/internal/` | 90 days | Platform SRE rotation |

## Why 90 days

Mirrors **Phase 240.1.D's DQ-service key rotation cadence**:
the value balances credential-blast-radius against rotation
operational toil. Industry baseline (NIST SP 800-63B Rev 4) is
"unlimited if no compromise" but most regulated tenants demand
≤ 90 days for service tokens. 90 days lands at the regulator-
expected ceiling.

## Operator playbook

Same shape as the Phase 240.1.D DQ-service rotation:

1. **T-7 days** (one week before rotation): platform SRE
   notifies tenants via the in-app banner that user tokens
   minted before `<rotation_ts - 90d>` will be revoked at
   `<rotation_ts>`. Tenants self-mint a new token via the
   tenant settings UI.
2. **T-0** (rotation day, 02:00 UTC off-peak): SRE rotates the
   `INTERNAL_API_KEY` and `HUB_WORKER_API_KEY` via the
   secrets-manager rotation pipeline. Hub deploys the new keys
   atomically (rolling restart with both old + new keys in the
   accept set for 60 minutes).
3. **T+1 hour**: the old keys' accept window closes. Any
   request with the old key returns `401` with structured
   error `code="API_KEY_EXPIRED"`.
4. **T+1 day**: SRE reviews the audit log for any
   `API_KEY_EXPIRED` events from real (non-bot) clients and
   reaches out to those tenants directly.

## Self-service rotation (user tokens)

Tenants can self-rotate at any time via:

```
POST /api/v1/auth/api-keys/
{
    "name": "ci-runner",
    "scopes": ["assets:write", "contracts:write"]
}
```

The response carries the new token; existing tokens for the
same `name` are revoked atomically. The CI/CD pipeline updates
the secret-manager value before the rotation timestamp; SDK
clients pick up the new value on next process restart.

## Detecting key leaks

The hub emits an audit-event `API_KEY_LEAK_SUSPECTED` when:
* A single key fires from > 5 distinct IP CIDR ranges within
  1 hour (suggests credential sharing).
* A key fires from a country / region not in the tenant's
  configured allow-list.

The audit-event triggers an automatic 24-hour grace-revoke
notification to the tenant admin. The admin can either
self-rotate (preferred) OR confirm "this is expected" via the
admin UI.

## Related documentation

* [./programmatic-asset-creation.md](./programmatic-asset-creation.md) — DE-1 SDK guide.
* Phase 240.1.D DQ-service rotation runbook — same shape, same
  cadence.
* `docs/runbooks/api-key-rotation.md` (planned, post-Phase-235) —
  consolidated operator playbook.
