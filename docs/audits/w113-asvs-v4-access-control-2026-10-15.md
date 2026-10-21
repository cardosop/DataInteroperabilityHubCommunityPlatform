# W11.3 — ASVS V4 Access-Control Regression Matrix — Claim→Verification Ledger

Generated: 2026-10-16 — task W11.3 of `openspec/changes/oss-release-remediation`.
Owns the vibe-code register rows **1 (BOLA/IDOR)**, **8 (scopes/roles as
decoration)**, **9 (defense-in-depth as prose)**.

## Scope rule (the denominator)

A *tenant-scoped route* is a runtime-resolved route whose view's model has a
`tenant` FK to `tenants.Tenant` AND whose effective permission surface is not
platform-admin-gated (platform admins cross tenants by design; pinned by
`tests/security/test_admin_user_edit_security.py` and
`tests/security/test_privilege_escalation.py`). Coverage = probed /
(probed + allowlisted) ≥ 95%.

## Coverage

- Tenant-scoped route keys: **588** (586 probed + 2 allowlisted) — **99.66%**
- Allowlisted (with written reasons in `lint/idor-coverage-allowlist.yml`):
  - `POST /api/v1/contracts/products/` — full ODPS product-creation workflow
    (external steps), no tenant-scoped FK surface in the payload.
  - `POST /api/v1/databricks/workspaces/` — SSRF host validation with live DNS
    resolution; no synthetic hostname can pass.
- Excluded from the denominator by the scope rule (listed in the matrix doc):
  19 platform-admin-gated (incl. 1 manual-gate route), 64 no-tenant-FK,
  257 unresolved function-view/GraphQL/SSE routes.

## Register-row evidence

### Row 1 — Broken object-level authorization / IDOR

The matrix probes **every tenant-scoped route key** with the strict contract:
cross-tenant retrieve/update/destroy → **404, never 403** (an existence leak);
cross-tenant list → 200 with the foreign row absent; create → the row lands in
the CALLER's tenant; payload references to another tenant's objects → 404
before execution.  Suite: `tests/security/test_w113_asvs_v4_access_control.py`
(836 tests, GREEN).  Manifest: `docs/api-audit/idor-probe-manifest.json`.
Matrix doc: `docs/security/adversarial-matrices/w113-access-control-matrix.md`.

**Real findings the matrix surfaced and root-fixed (never test-side weakened):**

| # | Route | Pre-fix behavior | Root fix |
|---|---|---|---|
| 1 | `DELETE /api/v1/virtualization/datasets/{id}/` + 6 sibling virtualization actions | cross-tenant → **403** (existence leak) via `get_dataset_for_cross_tenant_check` / hardcoded `PermissionDenied` | shared helper + all call sites now raise `NotFound` (404); `hub/apps/virtualization/cross_tenant_helpers.py`, `views.py` |
| 2 | `GET/PATCH /api/v1/tenants/{tenant_id}/config/` | TENANT_ADMIN probing another tenant → **403** | cross-tenant branch now `NotFound("Tenant not found")` with the `TENANT_NOT_FOUND` code; role-less 403 kept (documented); `hub/apps/tenants/views.py` `get_tenant` |
| 3 | `POST /api/v1/dsar/requests/` | `linked_user` from another tenant → **201** (accepted cross-tenant user reference) | `perform_create` rejects with `NotFound("Linked user not found.")`; `hub/apps/dsar/views.py` |
| 4 | `POST /api/v1/governance/access/certifications/` + `initiate-review` | cross-tenant certified `user` → **201**; service lookup `User.objects.get(id=…)` unscoped | tenant-scoped user lookup + `NotFoundError` → DRF 404; `hub/apps/governance/access_certification.py`, `views.py` |
| 5 | `POST /api/v1/datasets/{id}/refresh-from-file/` | serializer validation BEFORE `get_object()` → cross-tenant probe leaked a **400** | reordered: object resolution first (404), validation after; `hub/apps/datasets/views.py` |
| 6 | `POST /api/v1/governance/access-requests/{id}/revoke/` | body validation before `get_object()` → cross-tenant **400** | reordered (404 first); `hub/apps/governance/access_request_views.py` |
| 7 | `POST /api/v1/transformation/wrangling/` | cross-tenant asset → **500** (`NOT_FOUND` in a 500 envelope); invalid operation → **500** | `NotFoundError` → 404, `TransformationValidationError` → 400; `hub/apps/transformation/views.py` |
| 8 | `POST /api/v1/scheduled-ingestions/{id}/dlq/{dlq_item_id}/{retry,resolve}/` | `pk` kwarg vs `lookup_field="id"` → **TypeError 500 on every call**; DLQ item lookup unscoped (any tenant could retry another tenant's item) | signatures aligned to `id`; ingestion resolved via the scoped queryset (404); manager lookups tenant-scoped; `hub/apps/scheduled_ingestion/views.py`, `dead_letter_queue.py` |
| 9 | `POST /api/v1/ml/inference/ab-tests/` PATCH/PUT | response-only serializer's `update()` unimplemented → **500 on the happy path** | `http_method_names` restricted to the supported surface (create/list/retrieve/destroy); `hub/apps/ml/views.py` |
| 10 | `POST /api/v1/webhooks/webhooks/` | `validated_data["event_types"]` direct index → **KeyError 500** on the no-event-types path | `.get("event_types", [])`; `hub/apps/webhooks/views.py` |
| 11 | `POST /api/v1/compliance/runs/{id}/cancel/` | run without a linked Job → **AttributeError 500** | `job is None` guard → structured 400 `JOB_NOT_CANCELLABLE`; `hub/apps/compliance/views.py` |

Pinned contract corrections (tests that blessed the leaky 403 were updated to
the strict 404): `hub/apps/tenants/tests/test_tenant_config_views.py` (3 tests).

### Row 8 — Scopes/roles as decoration

- The probe suite grants **every write-capable tenant role** to both probe
  users (AUDITOR deliberately excluded — the ONE restrictive read-only role;
  its denial semantics are pinned by the dq/files/compliance auditor suites) —
  so a scope/role gate can never mask the IDOR outcome: the assertion is the
  tenant boundary itself.
- The create probes assert **the created row lands in the CALLER's tenant**
  (register-row-8 contract) for every create route.
- `ENFORCE_JWT_SCOPES` default True (W7.5); scope mappings pinned by
  `hub/apps/auth/tests/test_w112_asvs_auth_adversarial.py` and
  `tests/security/test_api_key_scopes.py`.

### Row 9 — Defense-in-depth as prose, not runtime

The probes run against the REAL stack: real DB with the RLS request-path
arming middleware (`TenantScopingMiddleware`), real role grants, real
permission classes, real business-rule chains.  App-level queryset scoping is
additionally pinned by `scripts/lint_queryset_coverage.py` (G3/W1.4a — 7
candidates, 0 open gaps).  The runtime layered contract (rows 1+9 together)
is what the matrix regression-blocks: a new tenant-scoped route without a
probe fails the in-suite coverage gate and `manage.py check_idor_coverage`
(GATE-63, wired into `_reusable.lint.yml`).

## The verification loop

1. `python manage.py generate_idor_probes` — re-enumerates the live urlconf,
   validates synthesis of every tenant-scoped model in rolled-back
   transactions, writes the manifest + matrix doc (byte-stable when clean).
2. `python manage.py check_idor_coverage` — drift both directions, dead
   allowlist entries, ≥95% (GATE-63 in CI).
3. `pytest tests/security/test_w113_asvs_v4_access_control.py` — the 836-test
   matrix itself, including the in-suite coverage gate.
4. `pytest scripts/tests/test_w113_idor_matrix_veracity.py` — the static
   veracity pin (12 tests), wired into the GATE-29 pin list, registered in
   the falsifiability harness (`gate-w113-idor-matrix-veracity`).

## Known environment notes

- `hub/apps/dsar/tests/` public-flow tests (5) fail pre-existing this session
  (verified failing WITHOUT the W11.3 change — unrelated, tenant_slug
  validation in the public submission flow).
- `hub/apps/ml/tests/…test_model_api_gateway_deployment` — the known G12
  in-flight settings regression (bisected in the W12.9 triage, out of scope).
- `hub/apps/webhooks/tests/test_delivery_validators_integration.py` retry-
  accounting test (attempt_number) — verified failing with the W11.3
  webhooks fix REVERTED (pre-existing; unrelated to the event_types fix).
  The webhooks suite also mid-run-dies around 50% in this environment
  (process killed, no junit written) — pre-existing runner behavior.
- The full security sweep (`tests/security/` + dq/files security dirs, the
  CI job's exact set) ran to 78% with ZERO failures before the container
  runner died mid-run (12 GB cgroup ceiling on the shared dev container —
  environmental; the CI job runs on a fresh runner).  The W11.3 suite
  itself completes fully (836 tests, ~90s).
- Host-side verification (p313-pg / 54329) is NOT available in this
  environment: the `p313-postgres` container has been down for 2 months.
- The suite raises the probe tenants' job-queue ceilings and plan counters —
  quota enforcement itself is pinned by the billing/jobs suites.
