# Federated import degradation — runbook

**Phase**: 250.0.19 (250.5.A / D250.16 operational support)

## Scope

Manage degraded operation of federated assets (`Asset.source_type=FEDERATED`): source-tenant deletion grace, marketplace connection failures, federated-import flag flips.

## Symptoms

- Tenant ticket: "I lost access to a federated asset" → likely flag flip OR source-tenant tombstoned.
- Audit events `FEDERATED_SOURCE_TENANT_DELETED` volume spike.
- HTTP 410 Gone on federated-asset reads.
- Marketplace connector circuit breaker OPEN.

## Diagnosis matrix

| Symptom | Likely cause | Remediation |
|---|---|---|
| HTTP 403 `FEDERATED_IMPORT_DISABLED` | Tenant `federated_import_enabled=False` | Path A |
| HTTP 410 `FEDERATED_SOURCE_TENANT_DELETED` | Source tenant deleted; consumer in 90-day grace | Path B |
| HTTP 503 / circuit-breaker open | Marketplace upstream unhealthy | Path C |
| HTTP 404 on cross-tenant federated read | By-design existence-leak protection | NOT an incident |

## Path A: federated-import flag flipped OFF

After Phase 250.5.A deploy, `federated_import_enabled` defaults to `False` for all tenants. Tenants with prior implicit federated access need explicit opt-in.

1. Tenant sees banner on `AssetCreatePage`: "Federated import is disabled. Enable in tenant settings."
2. Tenant admin navigates to `/settings/integrations/enable-federated`.
3. UI prompts for DPO + Legal sign-off (per ADR-AST-002 + RACI matrix); requires uploaded sign-off doc.
4. Flag flips → audit event `TENANT_FEDERATED_IMPORT_ENABLED`.
5. Existing federated assets become accessible again.

If the tenant cannot get sign-off OR doesn't want federation, advise migrating federated assets to local (download once + re-upload as `data_strategy=DOWNLOAD_ALL`).

## Path B: source-tenant deleted

Per D250.16, when a source tenant deletes itself, consumer-side federated copies are tombstoned (`Asset.source_tenant_deleted_at` set) for 90 days, after which they are hard-deleted.

1. Tenant ticket: "I can't access asset X any more."
2. Diagnosis:
   ```
   from hub.apps.assets.models import Asset
   a = Asset.objects.get(id='<asset_id>')
   print(a.source_type, a.source_tenant_deleted_at)
   ```
3. If `source_tenant_deleted_at` is set:
   - Compute grace expiration: `source_tenant_deleted_at + timedelta(days=90)`.
   - Inform tenant of the deadline.
   - Offer: **export now** via `POST /api/v1/assets/{id}/export-federated/`; produces a one-time downloadable copy.
4. After grace expires, hard-delete cascades; recovery is impossible.

## Path C: marketplace connector circuit-breaker OPEN

Federated assets depend on the source marketplace's API (CKAN, AWS Data Exchange, dados.gov.br). If the upstream is unhealthy, the marketplace connector circuit opens.

1. Diagnosis:
   ```
   from hub.apps.integrations.models import MarketplaceConnection
   for c in MarketplaceConnection.objects.filter(is_active=True):
       print(c.id, c.marketplace_type, c.circuit_breaker_state)
   ```
2. Circuit OPEN → upstream issue. Check upstream status page; wait for cool-down (per Phase 240's `service_breakers` timeout).
3. If sustained: contact marketplace operator; consider migrating affected assets off federation.

## Verification

After remediation:
- HTTP 410 / 403 / 503 rates return to baseline.
- Audit `FEDERATED_SOURCE_TENANT_DELETED` volume falls to baseline (these only fire on deletion events).
- No new circuit-breaker `OPEN` transitions for 1 hour.

## Escalation

- Sustained marketplace upstream outage: Customer Success + Marketplace partnership team.
- DPO + Legal sign-off blocking flag-flip: Phase 250.5.A RACI escalation.
- Suspected data leak via federated path: Sec on-call → DPO → Legal.

## Related

- ADR: [docs/adr/asset-creation/ADR-AST-002-federated-import-flag-and-skip-dq.md](../adr/asset-creation/ADR-AST-002-federated-import-flag-and-skip-dq.md)
- Audit: [docs/audit-reports/gap-14-external-resource-ssrf-idor-2026-05-03.md](../audit-reports/gap-14-external-resource-ssrf-idor-2026-05-03.md)
