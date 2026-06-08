# Business Rules Rollout Runbook — Phase 274

## Status
Authoritative. Phase 274 deployment playbook.

## Rolling deploy order
1. Deploy migrations (Tenant flags: `marketplace_publish_compliance_gate_enabled`, `continuous_compliance_enforcement_enabled`).
2. Deploy backend with `RuleChain` primitive + per-rule changes.
3. Deploy frontend with compliance threshold badge + asset activation three-state UX.
4. Enable `marketplace.listing.publish` chain on 5% of tenants; monitor for 24h.
5. Ramp to 100% over 3 days.

## Smoke tests
```bash
# BR1: Publish non-compliant listing → 422
curl -X POST /api/v1/marketplace/listings/ -H "Authorization: Bearer $TOKEN" \
  -d '{"asset_id":"...","pricing_model":"REQUEST_APPROVAL"}' | jq '.error.code'
# Expected: COMPLIANCE_THRESHOLD_EXCEEDED or COMPLIANCE_RUN_REQUIRED

# BR3: SPARQL on flag-off tenant → 403
curl "/api/v1/semantic/sparql/?query=SELECT+*+WHERE+{+?s+?p+?o+}+LIMIT+1" \
  -H "Authorization: Bearer $FLAG_OFF_TOKEN" | jq '.error.code'
# Expected: SEMANTIC_FEATURE_DISABLED

# BR4: Asset activation → 409 while scan runs
curl -X POST /api/v1/assets/{id}/activate/ -H "Authorization: Bearer $TOKEN" | jq '.error.code'
# Expected: COMPLIANCE_SCAN_PENDING (if scan not yet completed)
```

## Rollback
Set `Tenant.marketplace_publish_compliance_gate_enabled=False` per-tenant to revert BR1.
Set `Tenant.continuous_compliance_enforcement_enabled=False` per-tenant to revert BR18.

## Maintenance

- **Owner**: Platform Engineering
- **Last reviewed**: 2026-05-13
- **Next review**: 2026-08-11
