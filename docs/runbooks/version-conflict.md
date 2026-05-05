# Version conflict (optimistic-locking) — runbook

**Phase**: 250.0.19 (250.7.B operational support)

## Scope

PATCH operations failing with HTTP 412 `ASSET_VERSION_MISMATCH` or 428 `ASSET_IF_MATCH_REQUIRED` due to optimistic-locking enforcement.

## Symptoms

- Customer ticket: "I keep getting 412 when editing my asset".
- Grafana panel "ASSET_VERSION_MISMATCH events" shows spike.
- Audit event `ASSET_PATCH_MISSING_IF_MATCH` volume during soak window.

## Healthy 412 / 428 patterns (NOT incidents)

These are EXPECTED — the system is working correctly:

- Two TENANT_ADMINs editing the same asset; one gets 412 → the 3-way merge UX kicks in → user picks resolution → 200.
- Old browser tab attempts PATCH after server-side update → 412 → page-refresh resolves it.

## Incident patterns (require remediation)

### Pattern A: Frontend not sending `If-Match` after enforcement flip

Symptoms: `ASSET_IF_MATCH_REQUIRED` 428 errors spike from web traffic; SDK + CLI traffic unaffected.

Diagnosis: frontend bundle is stale; users on old SPA versions don't send `If-Match`.

Remediation:
1. Revert the enforcement flip:
   ```
   kubectl set env deployment/hub-api -n hub-staging OPTIMISTIC_LOCK_REQUIRE_IF_MATCH=False
   ```
2. Investigate frontend deploy; ensure latest bundle is being served.
3. Re-enable enforcement after frontend converges.

### Pattern B: 3-way merge UX broken

Symptoms: customers report 412s with no recovery option; merge dialog doesn't render.

Diagnosis: frontend `useUpdateAsset` mutation handler regression.

Remediation:
1. Open Eng ticket; assign to Frontend Lead.
2. Confirm Figma sign-off pre-deploy was done.
3. Hot-fix the mutation handler.

### Pattern C: SDK consumer hard-coded to ignore 412

Symptoms: external integrator reports loss of writes; their writes are landing as 412 silently.

Diagnosis: integrator's SDK / client is not honouring the 412 response.

Remediation:
1. Send the integrator the [docs/api/idempotency.md](../api/idempotency.md) + the optimistic-locking section.
2. Provide the canonical retry-with-fresh-version flow.
3. Internal: assess if the SDK ships a default retry-with-merge or if integrators are responsible. Phase 250.7.B SDK story.

### Pattern D: ETag generation regression

Symptoms: every PATCH returns 412 even on first attempt with a fresh GET.

Diagnosis: the version field is not incrementing OR ETag computation is broken.

Remediation:
1. Confirm `Asset.version` is set on save:
   ```
   from hub.apps.assets.models import Asset
   a = Asset.objects.first()
   v1 = a.version
   a.save()
   v2 = a.version
   assert v2 > v1, "Version not incrementing"
   ```
2. If broken, hot-fix the model `save()` override.
3. Soak with `OPTIMISTIC_LOCK_REQUIRE_IF_MATCH=False` until verified.

## Verification

- Grafana "412 rate" returns to baseline within 10 min of remediation.
- `ASSET_PATCH_MISSING_IF_MATCH` audit event volume drops to zero.
- A test PATCH with stale `If-Match` deterministically returns 412.

## Escalation

- SDK consumer escalation: customer-success → Eng EM.
- Frontend regression: Frontend Lead.
- Model `save()` regression: Eng EM + DPO if data-integrity affected.
