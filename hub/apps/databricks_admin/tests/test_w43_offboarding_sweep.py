"""
W4.3 / E2 — delta-share estate offboarding sweep pins.

The ``DeltaShareRecipient`` / ``DeltaShareToken`` / ``DeltaShareSnapshot``
rows carry ``on_delete=PROTECT`` against ``tenants.Tenant`` — pre-fix they
doomed every hard-delete sweep for a tenant that had ever used Delta
Sharing (the sweep skipped with ``cascade_failed`` forever).

The provider-boundary contract forbids ``tenants`` from importing
``databricks_admin`` estate models, so the sweep pre-step runs through
the registry inversion: ``databricks_admin/apps.py::ready()`` registers
``sweep_delta_share_estate`` into the provider-agnostic offboarding
registry (``hub.apps.tenants.offboarding``), and the sweep invokes the
registered sweepers inside ``tenant_context(tenant_id)``.

These pins prove, without mocks:

1.  Registration — the app ``ready()`` hook is wired into the registry.
2.  End-to-end — a tenant with a full delta-share estate (recipient +
    token + snapshot) hard-deletes through the real sweep; the estate
    rows are gone and the ``TENANT_HARD_DELETED`` audit itemizes them.
3.  RLS honesty — on the delta-share tables the policy is strict (no
    enable-GUC gate) AND ``FORCE ROW LEVEL SECURITY`` is set, so an
    unarmed connection sees ZERO rows: the sweeper MUST run inside
    ``tenant_context`` or its DELETE is a silent no-op. Pinned through
    the real ``hub_rls_probe`` role (the role the 1.12 RLS suites use):
    without a tenant context the probe sees 0 rows; with the tenant
    context armed the probe sees exactly the tenant's rows.
"""

from __future__ import annotations

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db import connection

from hub.apps.audit import event_types as _audit_et
from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant, TenantStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tenant() -> Tenant:
    uid = uuid.uuid4().hex[:8]
    return Tenant.objects.create(name=f"Tenant {uid}", slug=f"ds-tenant-{uid}")


def _make_admin(tenant: Tenant) -> User:
    uid = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        email=f"ds-{uid}@example.com", password="testpass123", tenant=tenant
    )


def _seed_delta_share_estate(tenant: Tenant, admin: User):
    """One recipient + one real token (production issue() path) + one snapshot.

    The share/schema/table names are unique per call — the snapshot grain
    ``(share_name, schema_name, table_name, version)`` is globally unique,
    so leaked rows from failed-teardown runs must not collide.
    """
    from hub.apps.databricks_admin.models import (
        DeltaShareRecipient,
        DeltaShareSnapshot,
        DeltaShareToken,
    )

    suffix = uuid.uuid4().hex[:8]
    recipient = DeltaShareRecipient.objects.create(
        tenant=tenant,
        name=f"recipient-{suffix}",
        created_by=admin,
    )
    token, _plaintext = DeltaShareToken.issue(
        recipient=recipient,
        tenant=tenant,
        share_name=f"share-{suffix}",
        schema_name="schema",
        table_name="table",
    )
    snapshot = DeltaShareSnapshot.objects.create(
        tenant=tenant,
        share_name=f"share-{suffix}",
        schema_name="schema",
        table_name="table",
        version=1,
        files=[],
        expires_at=timezone.now() + timedelta(days=1),
    )
    return recipient, token, snapshot


def _backdate_grace(tenant: Tenant) -> None:
    past = timezone.now() - timedelta(days=91)
    Tenant.all_objects.filter(pk=tenant.pk).update(
        scheduled_for_deletion_at=past,
        deleted_at=past,
        status=TenantStatus.DELETED,
    )


# ---------------------------------------------------------------------------
# Pins
# ---------------------------------------------------------------------------


class TestDeltaShareOffboardingRegistration:
    def test_offboarding_sweeper_registered_by_app_ready(self):
        """``databricks_admin/apps.py::ready()`` registers the sweeper into
        the provider-agnostic registry — the inversion that keeps the
        control-plane provider boundary intact."""
        from hub.apps.tenants.offboarding import get_registered_tenant_offboard_sweepers

        registered = get_registered_tenant_offboard_sweepers()
        assert (
            "databricks_delta_share" in registered
        ), "databricks_admin must register its offboarding sweeper in ready()"


class TestDeltaShareOffboardingSweep:
    def test_hard_delete_completes_with_delta_share_estate_present(self):
        """The tenant hard-delete sweep completes with a full delta-share
        estate present; estate rows are gone and itemized in the audit."""
        from hub.apps.databricks_admin.models import (
            DeltaShareRecipient,
            DeltaShareSnapshot,
            DeltaShareToken,
        )
        from hub.apps.tenants.tenant_hard_delete_sweep import (
            run_tenant_hard_delete_sweep,
        )

        tenant = _make_tenant()
        admin = _make_admin(tenant)
        recipient, token, snapshot = _seed_delta_share_estate(tenant, admin)
        _backdate_grace(tenant)

        summary = run_tenant_hard_delete_sweep(dry_run=False)

        assert not Tenant.all_objects.filter(pk=tenant.pk).exists()
        assert not DeltaShareRecipient.objects.filter(pk=recipient.pk).exists()
        assert not DeltaShareToken.objects.filter(pk=token.pk).exists()
        assert not DeltaShareSnapshot.objects.filter(pk=snapshot.pk).exists()
        assert not any(
            str(tenant.pk) == r.get("tenant_id") and r.get("reason") == "cascade_failed"
            for r in summary.get("skipped", [])
        )
        audit = (
            AuditEvent.all_objects.filter(
                action=_audit_et.TENANT_HARD_DELETED,
                details_json__tenant_id=str(tenant.pk),
            )
            .order_by("-timestamp")
            .first()
        )
        assert audit is not None
        pre_sweep = (audit.details_json or {}).get("pre_sweep", {})
        delta_share = pre_sweep.get("databricks_delta_share", {})
        assert delta_share.get("recipients") == 1
        assert delta_share.get("snapshots") == 1
        # access_grants counts RESIDUAL token rows after the recipient
        # cascade — 0 on a consistent estate (the cascade removed the
        # issued token; the row itself is asserted gone above).
        assert delta_share.get("access_grants") == 0


class TestDeltaShareRlsHonesty:
    """The strict-policy + FORCE-RLS contract that makes tenant_context
    mandatory for the offboarding sweeper."""

    def _probe_role(self):
        from hub.apps.databricks_admin.tests.test_uc_rls_isolation import (
            _connection_bypasses_rls,
            _ensure_rls_probe_role,
        )

        if _connection_bypasses_rls():
            _ensure_rls_probe_role()
            return "hub_rls_probe"
        return None

    def _visible_count(self, probe, tenant_id, table) -> int:
        from django.db import connection

        with connection.cursor() as cursor:
            try:
                if probe:
                    cursor.execute(f"SET ROLE {probe}")
                cursor.execute(f"SELECT count(*) FROM {table}")
                return cursor.fetchone()[0]
            finally:
                if probe:
                    cursor.execute("RESET ROLE")

    def test_unarmed_connection_sees_zero_delta_share_rows(self):
        """Without a tenant context the strict policy hides every row —
        an unarmed sweeper DELETE would silently delete nothing and the
        PROTECT FK would still doom the tenant delete."""
        tenant = _make_tenant()
        admin = _make_admin(tenant)
        _seed_delta_share_estate(tenant, admin)

        probe = self._probe_role()
        assert (
            self._visible_count(probe, tenant.id, "databricks_delta_share_recipients")
            == 0
        )
        assert (
            self._visible_count(probe, tenant.id, "databricks_delta_share_tokens") == 0
        )
        assert (
            self._visible_count(probe, tenant.id, "databricks_delta_share_snapshots")
            == 0
        )

    def test_tenant_context_arms_the_policy_for_the_tenant(self):
        """Inside ``tenant_context(tenant_id)`` the strict policy shows
        exactly the tenant's rows — the contract the offboarding registry
        runner relies on when it wraps every sweeper. Run as the
        non-bypass probe role so the policy is REALLY enforced (the hub
        role on the test DB carries BYPASSRLS)."""
        from hub.apps.tenants.request_tenant import tenant_context

        tenant = _make_tenant()
        admin = _make_admin(tenant)
        _seed_delta_share_estate(tenant, admin)

        from django.db import transaction

        probe = self._probe_role()
        with connection.cursor() as cursor:
            try:
                if probe:
                    cursor.execute(f"SET ROLE {probe}")
                # tenant_context's set_config(..., true) is transaction-local
                # (RLS probe autocommit trap) — an explicit atomic block is
                # mandatory outside the framework's own transaction.
                with transaction.atomic():
                    with tenant_context(str(tenant.id)):
                        with connection.cursor() as inner:
                            inner.execute(
                                "SELECT count(*) FROM databricks_delta_share_recipients"
                            )
                            assert inner.fetchone()[0] == 1
                            inner.execute(
                                "SELECT count(*) FROM databricks_delta_share_snapshots"
                            )
                            assert inner.fetchone()[0] == 1
            finally:
                if probe:
                    cursor.execute("RESET ROLE")
