# KYC Provider Integration

Runbook for integrating an external KYC provider with the Hub so that tenant KYC status can be set to VERIFIED (or PENDING_REVIEW) in an auditable, idempotent way. Design: [openspec/changes/feat1/design.md](../../openspec/changes/feat1/design.md) D5. **No live provider implementation is included in this change** — this document describes the path for a future integration.

## Purpose

A KYC provider (e.g. identity verification service) must be able to notify the Hub when a tenant’s KYC status changes (e.g. submission received → PENDING_REVIEW, review passed → VERIFIED). The Hub must:

1. Accept updates in a **secure** way (authenticated webhook or admin API).
2. Update `Tenant.kyc_status` so that **audit** and **idempotency** are preserved.
3. Expose a **documented path** for the provider without implementing a live provider in the codebase.

## How KYC status is updated today

- **Admin / API:** Platform admins (or back-office) can set `kyc_status` via the tenant API: `PATCH /api/v1/tenants/{id}/` with `kyc_status` in the body. Requires platform-admin (or equivalent) permission. Uses `TenantService.update_tenant(tenant_id=..., kyc_status=...)`, which performs a single-instance save and therefore triggers the Tenant model’s `post_save` signal.
- **Audit:** Every change to `Tenant.kyc_status` (via single-instance save) is written to the audit log with action `KYC_STATUS_CHANGED` and details `previous_kyc_status`, `new_kyc_status`, `tenant_id`. Implemented in `hub/apps/tenants/signals.py`. See [D5 — KYC status and audit](../../openspec/changes/feat1/design.md) and feat1 task 2.3.
- **Bulk updates:** `Tenant.objects.filter(...).update(kyc_status=...)` does **not** fire model signals and is **not** audited. For provider-driven updates, use the tenant API or `TenantService.update_tenant()` so that every transition is audited.

## Recommended path for a KYC provider

### Option A: Secure webhook (future)

1. **Endpoint:** Add a dedicated webhook endpoint (e.g. `POST /api/v1/internal/kyc/webhook/` or under an existing internal API prefix) that:
   - Accepts only requests authenticated by a shared secret or provider-signed payload (e.g. HMAC, JWT).
   - Parses provider payload to obtain tenant identifier (e.g. tenant_id or external reference) and new status (VERIFIED, PENDING_REVIEW, or UNVERIFIED).
   - Resolves tenant (by id or by external id mapping), then calls `TenantService.update_tenant(tenant_id=..., kyc_status=...)`. Do **not** use `QuerySet.update()` so that the signal fires and audit is written.
2. **Idempotency:** If the provider sends the same status multiple times, calling `update_tenant(kyc_status=...)` with the same value is safe: the service only saves when the value actually changes, and the signal only emits an audit event when `previous_kyc_status != new_kyc_status`. Optionally accept an idempotency key (e.g. header or body field) and return 200 with the same response for duplicate keys to satisfy at-least-once delivery.
3. **Audit:** No extra work required; the existing Tenant signal creates `KYC_STATUS_CHANGED` for every real transition.

### Option B: Admin API (current)

Use the existing tenant update API with platform-admin credentials (or a dedicated service account):

- **PATCH** `/api/v1/tenants/{id}/` with body `{"kyc_status": "VERIFIED"}` (or `"PENDING_REVIEW"`, `"UNVERIFIED"`). The `{id}` is the Hub tenant UUID (see tenant list or detail API).
- The provider’s backend can call this API after verifying the tenant externally. If the provider uses an external identifier, the integration layer must resolve it to the Hub tenant UUID before calling. Secure the call with API key or OAuth for the admin identity.
- Idempotency: sending the same status again is a no-op (no change, no duplicate audit). For strict idempotency keys, the provider can track last-sent status and skip the call when unchanged.
- Audit: every real change is already audited via the Tenant signal.

## Idempotency and audit summary

| Aspect        | Behavior |
|---------------|----------|
| **Idempotency** | Setting `kyc_status` to the same value it already has does not change the row and does not create a new audit event. Safe to call repeatedly. |
| **Audit**       | Every *change* of `kyc_status` produces one `KYC_STATUS_CHANGED` audit event with previous and new value. Use the tenant API or `TenantService.update_tenant()` so the Tenant signal runs. |
| **Bulk update** | `Tenant.objects.filter(...).update(kyc_status=...)` is **not** audited. Do not use for provider-driven updates. |

## KYC status values

- **UNVERIFIED:** Default; tenant has not completed or passed KYC.
- **PENDING_REVIEW:** Tenant has submitted KYC information; review with the provider is pending (e.g. submission pending provider).
- **VERIFIED:** Tenant has been verified by the provider; allowed for marketplace orders/entitlements (unless allowlisted).

See design D5 and `hub/apps/tenants/models.KYCStatus`.

## What is not in scope (this change)

- No live KYC provider (no third-party API client or webhook handler) is implemented.
- No new HTTP endpoint is added; the documented path uses the existing tenant API or a future webhook design as above.
- No change to marketplace/order KYC checks (those remain VERIFIED + allowlist per feat1 2.4).

## Runbook index

See [RUNBOOKS.md](../RUNBOOKS.md) for the full list. For marketplace order/entitlement KYC enforcement, see [Marketplace orders and entitlements — KYC required](../RUNBOOKS.md#marketplace-orders-and-entitlements--kyc-required).
