"""
Phase 230.14.1 (D230.15) — Tenant-scoped manager primitives.

Provides ``TenantScopedManager`` that an app's model can opt into to
get a default ``.for_tenant(tenant)`` queryset helper PLUS a guard
against cross-tenant fingerprint leaks via the standard ``.get(...)``
path.

This module is INTENTIONALLY additive — it does NOT replace each
model's existing manager; it's set as a SECONDARY manager so call
sites that have explicit tenant filtering (the majority of the
existing code) keep working unchanged. The primary use case is
NEW models added in Phase 230 (semantic, LDN, ontology) which can
adopt the helper to keep tenant scoping centralised rather than
each model duplicating the ``.filter(tenant=...)`` pattern.

Usage:

    class MyModel(models.Model):
        tenant = models.ForeignKey("tenants.Tenant", ...)
        ...

        # Default manager unchanged.
        objects = models.Manager()
        # New tenant-scoped helper.
        scoped = TenantScopedManager()

    MyModel.scoped.for_tenant(tenant).filter(...)

The manager DOES NOT auto-filter by tenant on every query — that
would silently break legacy code paths that intentionally span
tenants (platform admin views, GDPR purge cascades, audit-archive
sweeps). It provides a single canonical helper that audit-traceable
tenant-scoped reads can use, plus a ``.get_for_tenant(tenant, **kw)``
shortcut that raises ``DoesNotExist`` if the row exists but belongs
to a different tenant.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db import models

if TYPE_CHECKING:
    from hub.apps.tenants.models import Tenant


class TenantScopedQuerySet(models.QuerySet):
    """QuerySet exposing the ``.for_tenant`` helper."""

    def for_tenant(self, tenant) -> "TenantScopedQuerySet":
        """Filter to rows belonging to ``tenant``.

        Accepts either a Tenant instance or a tenant id (uuid /
        string / int) — the FK column accepts the same shapes
        Django normally accepts. Passing ``None`` returns an empty
        queryset (defensive: a missing tenant is NEVER "all rows").
        """
        if tenant is None:
            return self.none()
        if hasattr(tenant, "pk"):
            return self.filter(tenant=tenant)
        return self.filter(tenant_id=tenant)


class TenantScopedManager(models.Manager.from_queryset(TenantScopedQuerySet)):  # type: ignore[misc]
    """Manager that exposes ``.for_tenant`` + ``.get_for_tenant``.

    Models opt in by setting ``scoped = TenantScopedManager()``
    alongside their existing default manager. The pattern is
    additive — no migration required.
    """

    def for_tenant(self, tenant) -> TenantScopedQuerySet:
        return self.get_queryset().for_tenant(tenant)

    def get_for_tenant(self, tenant, **kwargs: Any):
        """Tenant-scoped ``.get``. Raises ``DoesNotExist`` if the
        matching row exists but belongs to a different tenant —
        defence-in-depth against cross-tenant fingerprint via
        guess-the-UUID. Without this, a developer who writes
        ``Model.objects.get(pk=user_supplied_uuid)`` could leak
        the existence of cross-tenant rows by error-message timing.
        """
        return self.for_tenant(tenant).get(**kwargs)


__all__ = ["TenantScopedManager", "TenantScopedQuerySet"]
