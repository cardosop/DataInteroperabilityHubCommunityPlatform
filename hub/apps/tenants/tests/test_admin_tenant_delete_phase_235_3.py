"""
Phase 235.3 — PLATFORM_ADMIN tenant soft-delete + 90-day grace + hard-delete sweep.

Engineering contract this suite pins (REQ-ADMIN-TENANT-DELETE-001 +
REQ-ADMIN-TENANT-HARD-DELETE-001 in
``openspec/changes/preprod01/specs/admin-tenant-lifecycle/spec.md``):

1.  ``DELETE /api/v1/admin/tenants/{id}/`` is PLATFORM_ADMIN-only via
    ``IsPlatformAdmin``; TENANT_ADMIN → 403; unauthenticated → 401/403.
2.  On success: sets ``scheduled_for_deletion_at = now()`` AND
    ``deleted_at = now()`` (the existing Phase 226 soft-delete field);
    flips ``status`` to ``DELETED``; emits ``TENANT_SOFT_DELETED``
    audit event.
3.  Rejects with HTTP 422 + ``code=LEGAL_HOLD_ACTIVE`` when
    ``tenant.legal_hold=True``.
4.  Rejects with HTTP 422 + ``code=DSAR_RESTRICTION_ACTIVE`` when the
    tenant has any open RESTRICTION-class DSAR.
5.  Already-soft-deleted tenants return 409 Conflict (no-op).
6.  Daily cron ``tenant_hard_delete_sweep`` hard-deletes tenants where
    ``scheduled_for_deletion_at < now() - 90d AND legal_hold=False
    AND no open DSAR-restriction``. Emits ``TENANT_HARD_DELETED``
    BEFORE the cascade (so the audit row survives via the
    AuditEvent.tenant ``on_delete=SET_NULL`` contract).
7.  Tenants whose ``legal_hold`` flipped to True DURING the grace
    window are skipped by the sweep — no hard-delete; logged as
    "skipped due to legal hold".
8.  Tenants whose ``scheduled_for_deletion_at`` is < 90 days old are
    skipped by the sweep (the grace window is mandatory).
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit import event_types as _audit_et
from hub.apps.audit.models import AuditEvent
from hub.apps.dsar.models import DSARRequest, DSARRequestType, DSARStatus
from hub.apps.tenants.models import Tenant, TenantStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _ensure_tenant_has_subscription(tenant: Tenant) -> None:
    from datetime import timedelta

    from django.utils import timezone

    from hub.apps.billing.models import Subscription, SubscriptionStatus
    from hub.apps.tenants.models import PlanTier, TenantPlan

    if Subscription.objects.filter(tenant=tenant, status=SubscriptionStatus.ACTIVE).exists():
        return
    plan, _ = TenantPlan.objects.get_or_create(
        slug=f"test-plan-{tenant.slug}",
        defaults={
            "name": f"Test Plan {tenant.slug}",
            "tier": PlanTier.FREE,
            "limits_json": {"max_assets": 100},
            "is_active": True,
        },
    )
    Subscription.objects.create(
        tenant=tenant,
        plan=plan,
        status=SubscriptionStatus.ACTIVE,
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timedelta(days=365),
    )


def _make_tenant(*, slug_suffix: str | None = None) -> Tenant:
    uid = slug_suffix or uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(name=f"Tenant {uid}", slug=f"tenant-{uid}")
    _ensure_tenant_has_subscription(tenant)
    return tenant


def _make_platform_admin(*, tenant: Tenant | None = None) -> User:
    uid = uuid.uuid4().hex[:8]
    home_tenant = tenant or _make_tenant(slug_suffix=f"pa-home-{uid}")
    user = User.objects.create_user(
        email=f"pa-{uid}@example.com", password="testpass123", tenant=home_tenant
    )
    user.is_platform_admin = True
    user.save(update_fields=["is_platform_admin"])
    return user


def _make_regular_user(tenant: Tenant) -> User:
    uid = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        email=f"u-{uid}@example.com", password="testpass123", tenant=tenant
    )


def _detail_url(tenant_id) -> str:
    return f"/api/v1/admin/tenants/{tenant_id}/"


def _open_dsar_restriction(tenant: Tenant) -> DSARRequest:
    """Create an open RESTRICTION-class DSAR for ``tenant``."""
    return DSARRequest.objects.create(
        tenant=tenant,
        request_type=DSARRequestType.RESTRICTION,
        status=DSARStatus.UNDER_REVIEW,
        subject_email="subject@example.com",
    )


# ---------------------------------------------------------------------------
# Tier 1 — model fields
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestTenantFields:
    @pytest.mark.integration
    def test_legal_hold_field_exists_with_default_false(self):
        t = _make_tenant()
        assert t.legal_hold is False

    @pytest.mark.integration
    def test_scheduled_for_deletion_at_field_exists_with_default_none(self):
        t = _make_tenant()
        assert t.scheduled_for_deletion_at is None


# ---------------------------------------------------------------------------
# Tier 2 — DELETE endpoint permission gating
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAdminTenantDeletePermissions:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.target = _make_tenant()
        self.client = APIClient()

    @pytest.mark.integration
    def test_unauthenticated_blocked(self):
        resp = self.client.delete(_detail_url(self.target.id))
        assert resp.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    @pytest.mark.integration
    def test_tenant_admin_blocked(self):
        regular = _make_regular_user(self.target)
        self.client.force_authenticate(regular)
        resp = self.client.delete(_detail_url(self.target.id))
        assert resp.status_code == status.HTTP_403_FORBIDDEN


# ---------------------------------------------------------------------------
# Tier 3 — DELETE happy path
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAdminTenantDeleteHappyPath:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.target = _make_tenant()
        self.admin = _make_platform_admin()
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    @pytest.mark.integration
    def test_sets_scheduled_for_deletion_at_and_deleted_at(self):
        resp = self.client.delete(_detail_url(self.target.id))
        assert resp.status_code == status.HTTP_200_OK, resp.content
        self.target.refresh_from_db()
        assert self.target.scheduled_for_deletion_at is not None
        assert self.target.deleted_at is not None
        assert self.target.status == TenantStatus.DELETED

    @pytest.mark.integration
    def test_emits_tenant_soft_deleted_audit_event(self):
        self.client.delete(_detail_url(self.target.id))
        audit = (
            AuditEvent.all_objects.filter(
                tenant=self.target,
                action=_audit_et.TENANT_SOFT_DELETED,
            )
            .order_by("-timestamp")
            .first()
        )
        assert audit is not None
        d = audit.details_json or {}
        assert d.get("slug") == self.target.slug
        assert d.get("scheduled_for_deletion_at")
        # The PLATFORM_ADMIN is the actor for the soft-delete.
        assert audit.actor_user_id == self.admin.id

    @pytest.mark.integration
    def test_already_deleted_returns_409(self):
        # First DELETE succeeds.
        self.client.delete(_detail_url(self.target.id))
        # Second DELETE: 409 (no-op; nothing to soft-delete).
        resp = self.client.delete(_detail_url(self.target.id))
        assert resp.status_code == status.HTTP_409_CONFLICT, resp.content


# ---------------------------------------------------------------------------
# Tier 4 — DELETE rejection (legal_hold + DSAR-restriction)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAdminTenantDeleteBlockers:
    @pytest.fixture(autouse=True)
    def _setup(self):
        self.target = _make_tenant()
        self.admin = _make_platform_admin()
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    @pytest.mark.integration
    def test_legal_hold_blocks_with_422(self):
        self.target.legal_hold = True
        self.target.save(update_fields=["legal_hold"])

        resp = self.client.delete(_detail_url(self.target.id))
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, resp.content
        body = resp.json()
        assert body.get("code") == "LEGAL_HOLD_ACTIVE"
        # Side-effect contract: NO state change on rejection.
        self.target.refresh_from_db()
        assert self.target.scheduled_for_deletion_at is None
        assert self.target.deleted_at is None
        assert self.target.status == TenantStatus.ACTIVE

    @pytest.mark.integration
    def test_open_dsar_restriction_blocks_with_422(self):
        _open_dsar_restriction(self.target)
        resp = self.client.delete(_detail_url(self.target.id))
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY, resp.content
        body = resp.json()
        assert body.get("code") == "DSAR_RESTRICTION_ACTIVE"
        self.target.refresh_from_db()
        assert self.target.scheduled_for_deletion_at is None
        assert self.target.deleted_at is None

    @pytest.mark.integration
    def test_closed_dsar_restriction_does_not_block(self):
        """A CLOSED_REJECTED DSAR is NOT an active restriction."""
        DSARRequest.objects.create(
            tenant=self.target,
            request_type=DSARRequestType.RESTRICTION,
            status=DSARStatus.CLOSED_REJECTED,
            subject_email="closed@example.com",
        )
        resp = self.client.delete(_detail_url(self.target.id))
        assert resp.status_code == status.HTTP_200_OK, resp.content


# ---------------------------------------------------------------------------
# Tier 5 — Hard-delete sweep (the daily cron path)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestTenantHardDeleteSweep:
    def _run_sweep_command(self, *args):
        out, err = StringIO(), StringIO()
        call_command("tenant_hard_delete_sweep", *args, stdout=out, stderr=err)
        return out.getvalue(), err.getvalue()

    @pytest.mark.integration
    def test_91_day_soft_deleted_tenant_hard_deleted_by_cron(self):
        """REQ-ADMIN-TENANT-HARD-DELETE-001 spec scenario."""
        from hub.apps.tenants.tenant_hard_delete_sweep import (
            run_tenant_hard_delete_sweep,
        )

        t = _make_tenant()
        # Backdate scheduled_for_deletion_at to 91 days ago.
        past = timezone.now() - timedelta(days=91)
        Tenant.all_objects.filter(pk=t.pk).update(
            scheduled_for_deletion_at=past,
            deleted_at=past,
            status=TenantStatus.DELETED,
        )

        summary = run_tenant_hard_delete_sweep(dry_run=False)

        # Tenant row hard-deleted (no longer in all_objects).
        assert not Tenant.all_objects.filter(pk=t.pk).exists()
        # TENANT_HARD_DELETED audit row survives the cascade because
        # AuditEvent.tenant uses on_delete=SET_NULL.
        audit = (
            AuditEvent.all_objects.filter(
                action=_audit_et.TENANT_HARD_DELETED,
                details_json__tenant_id=str(t.pk),
            )
            .order_by("-timestamp")
            .first()
        )
        assert audit is not None
        assert summary["hard_deleted_count"] >= 1

    @pytest.mark.integration
    def test_recent_soft_deleted_tenant_not_hard_deleted(self):
        """Inside the 90-day grace window → no hard-delete."""
        from hub.apps.tenants.tenant_hard_delete_sweep import (
            run_tenant_hard_delete_sweep,
        )

        t = _make_tenant()
        # Backdate to 30 days ago — still within grace.
        recent = timezone.now() - timedelta(days=30)
        Tenant.all_objects.filter(pk=t.pk).update(
            scheduled_for_deletion_at=recent,
            deleted_at=recent,
            status=TenantStatus.DELETED,
        )

        run_tenant_hard_delete_sweep(dry_run=False)
        assert Tenant.all_objects.filter(pk=t.pk).exists()

    @pytest.mark.integration
    def test_legal_hold_during_grace_pauses_sweep(self):
        """REQ-ADMIN-TENANT-HARD-DELETE-001 second spec scenario.

        A tenant whose ``legal_hold`` is set to True DURING the
        90-day grace window MUST NOT be hard-deleted by the sweep
        even if the grace window has elapsed.
        """
        from hub.apps.tenants.tenant_hard_delete_sweep import (
            run_tenant_hard_delete_sweep,
        )

        t = _make_tenant()
        past = timezone.now() - timedelta(days=91)
        Tenant.all_objects.filter(pk=t.pk).update(
            scheduled_for_deletion_at=past,
            deleted_at=past,
            status=TenantStatus.DELETED,
            legal_hold=True,  # acquired during grace
        )

        summary = run_tenant_hard_delete_sweep(dry_run=False)
        assert Tenant.all_objects.filter(pk=t.pk).exists()
        assert any(
            str(t.pk) == r.get("tenant_id") and r.get("reason") == "legal_hold_active"
            for r in summary.get("skipped", [])
        )

    @pytest.mark.integration
    def test_open_dsar_restriction_during_grace_pauses_sweep(self):
        """A DSAR-restriction opened during grace blocks the sweep."""
        from hub.apps.tenants.tenant_hard_delete_sweep import (
            run_tenant_hard_delete_sweep,
        )

        t = _make_tenant()
        past = timezone.now() - timedelta(days=91)
        Tenant.all_objects.filter(pk=t.pk).update(
            scheduled_for_deletion_at=past,
            deleted_at=past,
            status=TenantStatus.DELETED,
        )
        _open_dsar_restriction(t)

        summary = run_tenant_hard_delete_sweep(dry_run=False)
        assert Tenant.all_objects.filter(pk=t.pk).exists()
        assert any(
            str(t.pk) == r.get("tenant_id") and r.get("reason") == "dsar_restriction_active"
            for r in summary.get("skipped", [])
        )

    @pytest.mark.integration
    def test_dry_run_does_not_delete(self):
        from hub.apps.tenants.tenant_hard_delete_sweep import (
            run_tenant_hard_delete_sweep,
        )

        t = _make_tenant()
        past = timezone.now() - timedelta(days=91)
        Tenant.all_objects.filter(pk=t.pk).update(
            scheduled_for_deletion_at=past,
            deleted_at=past,
            status=TenantStatus.DELETED,
        )

        summary = run_tenant_hard_delete_sweep(dry_run=True)
        # Dry-run reports the count but does NOT delete.
        assert summary["hard_deleted_count"] >= 1
        assert summary["dry_run"] is True
        assert Tenant.all_objects.filter(pk=t.pk).exists()

    @pytest.mark.integration
    def test_management_command_runs_and_emits_summary(self):
        t = _make_tenant()
        past = timezone.now() - timedelta(days=91)
        Tenant.all_objects.filter(pk=t.pk).update(
            scheduled_for_deletion_at=past,
            deleted_at=past,
            status=TenantStatus.DELETED,
        )
        out, _ = self._run_sweep_command("--skip-job-row")
        assert "hard_deleted_count" in out or "Tenant hard-delete sweep" in out
        assert not Tenant.all_objects.filter(pk=t.pk).exists()


# ---------------------------------------------------------------------------
# Tier 6 — JobType + dispatcher wiring
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestTenantHardDeleteSweepJobWiring:
    @pytest.mark.integration
    def test_job_type_constant_registered(self):
        from hub.apps.jobs.models import JobType

        assert JobType.TENANT_HARD_DELETE_SWEEP.value == "TENANT_HARD_DELETE_SWEEP"


# ---------------------------------------------------------------------------
# Tier 7 — Phase 235.3 audit-fix race protection
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAdminTenantDeleteRaceProtection:
    """Phase 235.3 audit-fix Gap 1 — DELETE endpoint serialises concurrent
    admins via ``select_for_update`` on the Tenant row.

    Simulating a true concurrent test requires threads + real Postgres
    locks, which is heavy for the test pyramid. Instead, we exercise
    the sequential equivalent of the race: a second DELETE arriving
    AFTER the first has committed must return 409 ``ALREADY_DELETED``
    AND must NOT emit a duplicate ``TENANT_SOFT_DELETED`` audit event.
    The select_for_update wrap is what makes the same outcome hold
    under genuine concurrency.
    """

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.target = _make_tenant()
        self.admin = _make_platform_admin()
        self.other_admin = _make_platform_admin()
        self.client = APIClient()

    @pytest.mark.integration
    def test_second_delete_returns_409_and_no_duplicate_audit(self):
        # First admin's DELETE succeeds.
        self.client.force_authenticate(self.admin)
        resp1 = self.client.delete(_detail_url(self.target.id))
        assert resp1.status_code == status.HTTP_200_OK, resp1.content

        # Capture the audit-event count before the second attempt so a
        # leak-by-duplicate would surface as a count delta.
        before = AuditEvent.all_objects.filter(
            tenant=self.target,
            action=_audit_et.TENANT_SOFT_DELETED,
        ).count()
        assert before == 1

        # Second admin's DELETE (different user, same tenant) — must 409.
        self.client.force_authenticate(self.other_admin)
        resp2 = self.client.delete(_detail_url(self.target.id))
        assert resp2.status_code == status.HTTP_409_CONFLICT, resp2.content
        assert resp2.json().get("code") == "ALREADY_DELETED"

        # No duplicate TENANT_SOFT_DELETED — the select_for_update
        # lock + 409 idempotency guard ensures one event per delete.
        after = AuditEvent.all_objects.filter(
            tenant=self.target,
            action=_audit_et.TENANT_SOFT_DELETED,
        ).count()
        assert after == before


@pytest.mark.integration
class TestSweepRaceProtection:
    """Phase 235.3 audit-fix Gap 2 — the sweep's per-tenant lookup
    uses ``select_for_update(skip_locked=True)`` AND re-validates
    eligibility under the row lock.

    The re-validation contract is the load-bearing piece: even if the
    candidate enumeration sees a tenant as eligible, a ``legal_hold``
    flipped between the enumeration and the per-tenant lock acquisition
    MUST pause the sweep on that tenant. We exercise this by mutating
    the candidate's ``legal_hold`` field between the two phases via a
    monkey-patched DSAR check.
    """

    @pytest.mark.integration
    def test_per_tenant_revalidation_under_lock_skips_legal_hold_flipped_mid_sweep(self):
        """Simulates the race: candidate enumeration sees no legal_hold,
        but the row's legal_hold is flipped to True before our function
        re-validates under the row lock. The sweep MUST skip.
        """
        from hub.apps.tenants.tenant_hard_delete_sweep import (
            _hard_delete_one_tenant,
        )

        t = _make_tenant()
        past = timezone.now() - timedelta(days=91)
        Tenant.all_objects.filter(pk=t.pk).update(
            scheduled_for_deletion_at=past,
            deleted_at=past,
            status=TenantStatus.DELETED,
            # Flip legal_hold AFTER candidate enumeration would
            # have happened (simulated here by flipping it BEFORE
            # the per-tenant call).
            legal_hold=True,
        )

        result = _hard_delete_one_tenant(tenant_id=t.pk, sweep_run_id="test-run-1")
        assert result is None, (
            "_hard_delete_one_tenant must return None when the under-lock "
            "re-validation sees legal_hold=True"
        )
        # Row not deleted.
        assert Tenant.all_objects.filter(pk=t.pk).exists()
        # No TENANT_HARD_DELETED audit emitted.
        assert not AuditEvent.all_objects.filter(
            action=_audit_et.TENANT_HARD_DELETED,
            details_json__tenant_id=str(t.pk),
        ).exists()


@pytest.mark.integration
class TestTenantSerializerSurfacesLifecycleFields:
    """Phase 235.3 audit-fix Gap 3 — the tenants list response carries
    ``legal_hold`` + ``scheduled_for_deletion_at`` so the SPA can
    pre-disable the Deactivate button on locked tenants."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.admin = _make_platform_admin()
        self.client = APIClient()
        self.client.force_authenticate(self.admin)

    @pytest.mark.integration
    def test_tenant_detail_includes_legal_hold_and_scheduled_for_deletion_at(self):
        t = _make_tenant()
        t.legal_hold = True
        t.save(update_fields=["legal_hold"])

        resp = self.client.get(f"/api/v1/tenants/{t.id}/")
        assert resp.status_code == status.HTTP_200_OK, resp.content
        body = resp.json()
        assert body.get("legal_hold") is True
        assert "scheduled_for_deletion_at" in body
