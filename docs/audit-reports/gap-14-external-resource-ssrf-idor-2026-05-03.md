# Gap 14 verification — `ExternalResourceReference` SSRF / IDOR

**Audit task**: 250.0.9
**Audit date**: 2026-05-03
**Auditor**: Phase 250.0 Asset-Creation-Hardening pre-flight
**Status**: ⚠️ **PARTIAL — guard exists but save-path enforcement on `ExternalResourceReference.url` requires explicit wiring (250.5.B.1 / 250.5.C.1)**

## Original gap statement

Phase 250 source plan flagged Gap 14: "`ExternalResourceReference.url` is a tenant-supplied URL that may bypass SSRF protection at save time, and cross-tenant reads may leak existence (IDOR)."

## Verification

### SSRF guard infrastructure (CLOSED-by-import)

A robust SSRF validator exists at [hub/apps/webhooks/ssrf_guard.py:121](../../hub/apps/webhooks/ssrf_guard.py#L121) with `validate_webhook_url()` that:
- Blocks RFC 1918 / loopback / link-local / multicast / IMDS (169.254.169.254)
- Re-resolves DNS at delivery time (defeats DNS rebinding)
- Raises `SSRFViolationError` on violation

The guard is **wired in production code paths**:
- [hub/apps/webhooks/serializers.py:44-45](../../hub/apps/webhooks/serializers.py#L44) — webhook subscription URL validation at save
- [hub/apps/webhooks/service.py:345](../../hub/apps/webhooks/service.py#L345) — re-validation at delivery time
- [hub/apps/marketplace/payment_gateway_utils.py:30,119,266](../../hub/apps/marketplace/payment_gateway_utils.py) — payment gateway webhook URL validation
- [hub/apps/integrations/services/connection_service.py:164](../../hub/apps/integrations/services/connection_service.py#L164) — connection-test URL validation (imports `validate_webhook_url, SSRFViolationError`)
- [hub/apps/integrations/_services_legacy.py:221](../../hub/apps/integrations/_services_legacy.py#L221) — legacy connection-test (mirrors above)

### `ExternalResourceReference.url` save-path (NOT VERIFIED)

The model lives at [hub/apps/assets/models.py:523](../../hub/apps/assets/models.py#L523) with field `url = models.URLField(max_length=2048)`. The `URLField` validator only checks URL syntax — it does **NOT** check for SSRF. Production callers that create `ExternalResourceReference` rows (located via `ExternalResourceReference.objects.create(`) MUST be audited to confirm the URL is passed through `validate_webhook_url()` before save.

Direct grep finds production callers only inside `hub/apps/integrations/services/` (per the connection-test path) but the federated-import + scheduled-ingestion flows have NOT been independently verified. The 6 test-file occurrences exist but tests bypass the SSRF guard by design — they don't tell us about production behaviour.

### Cross-tenant read (IDOR — partially CLOSED)

`ExternalResourceReference` has a `ForeignKey(Asset, on_delete=CASCADE, related_name="external_resource_references")` ([hub/apps/assets/models.py:534](../../hub/apps/assets/models.py#L534)). Tenant scoping flows through the `Asset.tenant` field — any queryset filter that scopes by `Asset.tenant` transitively scopes the references. Production read paths (e.g. `download_external_resource()`) MUST be verified to use the tenant-scoped queryset and return HTTP 404 (not 403) for cross-tenant access (existence-leak protection).

## Conclusion

- **SSRF guard exists and is reusable** — Gap 14 has the infrastructure half closed.
- **`ExternalResourceReference.url` save-path SSRF wiring is unverified** — `URLField` syntax check is insufficient; callers MAY or MAY NOT route through `validate_webhook_url()`.
- **Cross-tenant read** depends on the queryset filter consistency at every read path.

## Recommended remediation (250.5.B.1 + 250.5.C.1)

Phase 250 tasks.md SHOULD spawn the contingency sub-tasks:

- **250.5.B.1** — Add a model-level `clean()` method on `ExternalResourceReference` that calls `validate_webhook_url(self.url, raise_as_validation_error=True)` before save. Add a `pre_save` signal handler as belt-and-suspenders. Audit-log save attempts via `EXTERNAL_RESOURCE_REFERENCE_SSRF_BLOCKED` event on rejection.
- **250.5.C.1** — Add a tenant-isolation pytest sweep at `hub/apps/assets/tests/security/test_external_resource_reference_idor.py` covering: cross-tenant read returns 404; cross-tenant download returns 404; cross-tenant list does not include other-tenant's references; UUID enumeration cannot leak existence.

Both sub-tasks belong to Phase 250's HIGH-priority security band per the original plan's "G-S-flavoured" gaps.

## Closeout

Phase 250 tasks.md marks 250.5.B and 250.5.C as: "Verify `ExternalResourceReference` SSRF + IDOR per [audit-reports/gap-14-external-resource-ssrf-idor-2026-05-03.md](../audit-reports/gap-14-external-resource-ssrf-idor-2026-05-03.md); remediate via 250.5.B.1 + 250.5.C.1 sub-tasks scheduled for Phase 250.5 HIGH band."
