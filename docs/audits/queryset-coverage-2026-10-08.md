# Queryset-Coverage Audit — 2026-10-08 (G3 / W1.4a)

Automated by `scripts/lint_queryset_coverage.py` (the G3 gate). Before RLS
arming (W1.20), every ViewSet over a tenant-scoped model must filter its
queryset by tenant EXPLICITLY — RLS would silently bless implicit scoping.

**Method.** The lint (1) inventories the tenant-scoped models via the
`lint_rls_policies.py` AST discovery (models with a tenant FK), (2)
AST-discovers `ModelViewSet`/`ReadOnlyModelViewSet`/`GenericViewSet`
subclasses across all 56 apps, (3) resolves each viewset's model via its
`queryset` attribute or its serializer's `Meta.model`, and (4) proves the
tenant filter through the viewset's own `get_queryset`/queryset, a repo
ancestor's, or a scoping helper's body (the marker set: `.filter(tenant…`,
`.filter(Q(tenant…`, `tenant_id=…`, `get_request_tenant_id`,
`request.tenant`, `user.tenant_id`). Allowlist exceptions live in
`lint/queryset-coverage-allowlist.yml` with a written reason per entry.

**Sweep result: 7 candidates investigated, 0 open gaps.** Disposition:

| Site | Disposition |
|---|---|
| `marketplace/order_views.py:54 OrderViewSet` | Proven scoped — `get_queryset` filters `Q(tenant=tenant) \| Q(listing__tenant=tenant)` (the provider-listing OR). Checker marker set extended with the `Q(tenant` form. |
| `integrations/views.py:266 MarketplaceConnectionViewSet` | Proven scoped — delegates to the `MarketplaceIntegrationMixin._resolve_queryset_tenant` helper. Checker extended to follow `self.<helper>(self.request, …)` bodies (the repo's mixin pattern). |
| `integrations/views.py:925 MarketplaceSyncJobViewSet` | Same helper proof as above. |
| `integrations/views.py:1365 MarketplaceMappingViewSet` | Same helper proof as above. |
| `billing/views.py:445 MLSubscriptionViewSet` | Proven scoped — a `GenericViewSet` whose actions resolve the tenant per-action via `get_request_tenant_id` (no list endpoint exists). Checker extended: per-action markers count for classes without list machinery. |
| `gdpr/views.py:31 DataExportJobViewSet` | **FIXED** — user-scoped only; user-scoping is tenant-scoping by proxy and not provable. Now filters `user=… AND tenant_id=get_request_tenant_id(request)`. |
| `gdpr/views.py:100 ErasureRequestViewSet` | **FIXED** — same class as above. |

**Allowlist:** zero entries — every viewset over a tenant-scoped model
carries a provable filter. The empty allowlist file ships with the schema
and the written-reason requirement so future exceptions stay audited.

**Pins:** `scripts/tests/test_lint_queryset_coverage.py` **5/5** — planted
unfiltered viewset → exit 1 (class named); filtered viewset, helper-scoped
viewset, and allowlisted class → clean; the REAL tree → clean. All pins run
the real lint against real fixture trees (no mocks).
