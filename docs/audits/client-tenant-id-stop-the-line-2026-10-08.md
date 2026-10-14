# Client-Tenant-ID Stop-the-Line Audit — 2026-10-08 (W1.8 / G2)

Stop-the-line check for the W1 root-cause class: any pilot-facing surface
still TRUSTING a client-supplied tenant ID for scoping. Tenant scope must
come from `get_request_tenant_id(request)` (authenticated identity /
request context) — never from `request.data`, `request.query_params`, or
their serializer equivalents.

**Method.** Two layers:

1. **The blocking gate** — `scripts/lint_no_client_tenant_id.py` (CI job
   `lint-no-client-tenant-id` in `.github/workflows/ci.yml`, exit 1 on any
   unallowlisted hit). Patterns: `request.data.get("tenant_id")`,
   `request.query_params.get("tenant_id")`, and the `validated_data`
   envelope (get + subscript). Allowlist entries require a written reason
   and must fall in one of three sanctioned categories: cross-tenant
   rejection guard (defence-in-depth), pre-auth SSO flow, explicit tenant
   switch.
2. **The beyond-lint sweep** — the envelope shapes the lint does NOT
   pattern-match were swept by hand: subscript reads, raw
   `request.GET/POST`, GraphQL resolver args, websocket payloads,
   writable serializer `tenant_id` fields, URL-path `tenant_id` kwargs,
   `X-Tenant-Id` consumers, and frontend request bodies.

**Sweep result: 15 allowlisted sites (every one with a written reason), 0
open trust gaps.** Disposition:

| Surface | Disposition |
|---|---|
| `lint/no-client-tenant-id-allowlist.yml` (15 entries) | All entries re-verified this pass. **3 fixed**: the `switch_tenant` anchor drifted 2070 → 2105 when W1.6 inserted the impersonation block above it (re-anchored, reason notes the drift); the W1.6 impersonation-block audit-detail read (line 2087) added with reason — the value is read ONLY to record the blocked attempt (403 `IMPERSONATION_TENANT_SWITCH_BLOCKED` + audit row); the two W1.1 register-guard entries (1520/1521) were provisional "in-flight" text — W1.1 has landed, reasons rewritten to the shipped state (audit-detail-only, never scope). |
| `request.data[...]` / `request.query_params[...]` subscript reads | None outside tests. |
| `request.GET.get("tenant_id")` / `request.POST.get("tenant_id")` | None outside tests. |
| GraphQL resolver `tenant_id` args (strawberry + graphene schemas) | None — the schemas take no tenant argument; resolvers scope via `info.context` / the authenticated user. |
| WebSocket / channels payload `tenant_id` reads | None. |
| Writable serializer `tenant_id` fields | None — every `tenant_id = serializers.*` site is `read_only=True`, a `SerializerMethodField`, or a RESPONSE serializer (`TenantCostBreakdownSerializer` cost aggregation, `RegisterResponseSerializer`, `CurrentUserSerializer`). |
| URL-path `tenant_id` kwargs (`tenants/views.py` config viewset) | Validated against identity — platform admin → any tenant; TENANT_ADMIN → own-tenant equality only (`get_tenant`). Path params are not scope-trusted. |
| `X-Tenant-Id` consumers outside the middleware | Only the worker internal-auth paths (`scheduled_export`/`scheduled_ingestion` `internal_auth.py`) — the sanctioned worker flow (env-var key bound; separate R2-S7 lane). The middleware validates UUID format → membership → tenant existence before the header is trusted. |
| Frontend request bodies carrying `tenant_id` | Only `tenantSwitchService.ts` (`POST /auth/switch-tenant/`) — the explicit-switch flow, server-validated against `UserTenantMembershipService`. The register form's `tenant_id` (a real W1.1 consequence found by the W1.5 E2E) was removed client-side. `useActiveTenantId` reads a LOCAL payload only. |
| CLI surfaces | The CLI resolves tenants through the authenticated API surface (membership-validated); no trusted-client-tenant path. |

**Pins:** `scripts/tests/test_lint_no_client_tenant_id.py` **6/6** — the
envelope patterns flip RED (data / validated-data get / validated-data
subscript), an allowlisted site passes, a DRIFTED anchor flips RED (the
exact failure class W1.6 introduced — caught by the gate before this audit
ran), and the REAL tree is green. All pins run the real lint against real
fixture trees (no mocks).
