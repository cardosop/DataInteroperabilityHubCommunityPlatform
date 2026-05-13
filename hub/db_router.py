"""
Primary / Read-Replica Database Router (Phase 17.2)

Routes read queries for high-traffic, read-heavy app labels to the AWS RDS
Multi-AZ replica endpoint (``"replica"`` database alias) when it is configured
in settings.DATABASES.  All writes always target the primary (``"default"``).

Read-replica app labels
-----------------------
``assets``       — asset catalogue, the single heaviest read workload
``contracts``    — data contract listings and search
``marketplace``  — marketplace product listings (read-heavy browse/search)
``search``       — full-text / vector search index queries

Design constraints
------------------
* ``db_for_write`` always returns ``"default"`` so that writes never silently
  go to a replica (which would fail with a PostgreSQL read-only error).
* ``allow_migrate`` returns ``True`` only for ``"default"``; replicas are
  managed by PostgreSQL streaming replication, not by ``manage.py migrate``.
* When the ``"replica"`` alias is absent from ``settings.DATABASES`` (i.e.
  ``DATABASE_REPLICA_URL`` is not set), every method returns ``None`` so that
  Django falls back to its default single-database behaviour.  This makes the
  router a no-op in local development and CI without a replica configured.
* ``allow_relation`` permits relations between objects from any database pair
  so that cross-app FKs (e.g. Asset → Tenant) continue to work regardless of
  which database alias resolved each object.

Interaction with BaaSDBRouter
------------------------------
``DATABASE_ROUTERS`` is a list; routers are consulted in order.  The
``PrimaryReplicaRouter`` must be listed *after* ``BaaSDBRouter`` so that
BaaS models are handled first and replica routing is only applied to
non-BaaS models.

Usage — annotating views (documentation of intent)
---------------------------------------------------
Read-only CBVs can make the routing explicit::

    class AssetListView(generics.ListAPIView):
        queryset = Asset.objects.using("replica")

Write views should use ``@transaction.atomic`` (which forces ``"default"``
via ``ATOMIC_REQUESTS`` / ``using="default"`` coercion)::

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        ...
"""
from __future__ import annotations

import os

from django.conf import settings

# App labels whose *read* queries are routed to the replica.
# Writes for these apps still go to the primary ("default").
_READ_REPLICA_APPS: frozenset[str] = frozenset(
    [
        "assets",       # Asset catalogue
        "contracts",    # Data contracts
        "marketplace",  # Marketplace listings
        "search",       # Full-text / vector search
    ]
)


def _replica_configured() -> bool:
    """Return True when the 'replica' DB alias is present in DATABASES."""
    return "replica" in getattr(settings, "DATABASES", {})


def _command_admin_mode_enabled() -> bool:
    raw = os.getenv("HUB_USE_ADMIN_DB_FOR_COMMANDS", "")
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _command_admin_alias() -> str:
    return os.getenv("HUB_COMMAND_DB_ALIAS", "admin").strip() or "admin"


class ManagementCommandAdminRouter:
    """
    Route ORM operations to admin alias during management command mode.

    Activated by manage.py via ``HUB_USE_ADMIN_DB_FOR_COMMANDS=1``.

    Phase 277.B.084 — emits ``BYPASSRLS_ADMIN_DB_USED`` audit event on
    first activation so the audit trail records every management command
    that uses the elevated-privilege BYPASSRLS connection.
    """

    _audit_emitted: bool = False  # once per process lifetime

    @staticmethod
    def _resolved_alias() -> str | None:
        if not _command_admin_mode_enabled():
            return None
        alias = _command_admin_alias()
        if alias not in getattr(settings, "DATABASES", {}):
            return None
        return alias

    def _maybe_emit_audit(self):
        if self._audit_emitted:
            return
        self._audit_emitted = True
        try:
            from hub.apps.audit.event_types import BYPASSRLS_ADMIN_DB_USED
            from hub.apps.audit.utils import create_audit_event
            create_audit_event(
                resource_type="DATABASE",
                action=BYPASSRLS_ADMIN_DB_USED,
                actor_user=None,
                tenant=None,
                resource_id="management_command_admin_router",
                result="SUCCESS",
                details={
                    "reason": "Management command execution — BYPASSRLS via admin DB alias",
                },
            )
        except Exception:
            pass  # audit DB may not be available yet

    def db_for_read(self, model, **hints):
        alias = self._resolved_alias()
        if alias:
            self._maybe_emit_audit()
        return alias

    def db_for_write(self, model, **hints):
        alias = self._resolved_alias()
        if alias:
            self._maybe_emit_audit()
        return alias

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return None


class PrimaryReplicaRouter:
    """
    Route reads for read-heavy apps to the replica; all writes to primary.

    When ``DATABASE_REPLICA_URL`` is not set the router is a transparent
    no-op — all methods return ``None`` so Django uses its default routing.
    """


class ReadReplicaRouter:
    """Route reads to replica when configured, writes to primary."""

    def db_for_read(self, model, **hints):
        """Return 'replica' for read-heavy apps when configured."""
        if not _replica_configured():
            return None
        if model._meta.app_label in _READ_REPLICA_APPS:
            return "replica"
        return None

    def db_for_write(self, model, **hints):
        """Always write to the primary database."""
        if model._meta.app_label in _READ_REPLICA_APPS:
            return "default"
        return None

    def allow_relation(self, obj1, obj2, **hints):
        """
        Allow relations between objects from any combination of databases.

        Cross-app FKs (e.g. Asset.tenant) may span replica ↔ default; Django
        checks this when constructing SELECT JOINs.  Returning True prevents
        spurious "Cross-database relations are not permitted" errors.
        """
        allowed_dbs = {"default", "replica"}
        db_set = {
            obj1._state.db or "default",
            obj2._state.db or "default",
        }
        if db_set <= allowed_dbs:
            return True
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Only migrate on the primary.  Replicas are kept in sync via
        PostgreSQL streaming replication — never via Django migrations.
        """
        if db == "replica":
            return False
        # Let other routers decide for non-replica databases.
        return None
