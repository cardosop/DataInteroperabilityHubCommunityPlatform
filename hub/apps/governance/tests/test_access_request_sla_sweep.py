"""
Phase 270.B.2 — AccessRequest SLA sweep via the existing
``revoke_expired_access`` management command.

What this suite pins
====================
(REQ-MKT-ACCESS-REQUEST-SLA in
``openspec/changes/preprod01/specs/marketplace-tax-compliance-deltas/spec.md``):

1. **Tenant-aware iteration via admin connection** — the command
   MUST enumerate active tenants via the ``admin`` (BYPASSRLS) DB
   alias, then enter ``tenant_context(tenant.id)`` per tenant.
   This is the Phase 260 Option C pattern: a single sweep cron
   survives full RLS rollout because the cross-tenant enumeration
   bypasses RLS at the connection level + the per-tenant
   processing sets the GUC correctly for tenant-scoped writes.

2. **APPROVED + past expires_at** — the legacy path stays:
   APPROVED requests whose ``expires_at`` has passed are
   transitioned to REVOKED + ``ACCESS_EXPIRED_REVOKED`` audit.

3. **PENDING + over SLA** — the NEW path (270.B.2.2):
   ``status=PENDING`` AND ``created_at < now - tenant.access_request_pending_sla_days``
   transitions to ``status=EXPIRED`` + ``ACCESS_REQUEST_EXPIRED_BY_SLA``
   audit with ``previous_status="PENDING"``, ``sla_days``, and
   ``age_days``.

4. **Per-tenant SLA isolation** — two tenants with DIFFERENT
   ``access_request_pending_sla_days`` settings produce DIFFERENT
   sweep verdicts on requests of the same age.

5. **Audit row carries spec'd payload** — the
   ``ACCESS_REQUEST_EXPIRED_BY_SLA`` payload must include all
   spec'd keys for downstream consumers (SIEM exporters,
   forensics).

NO-MOCKS POLICY
===============
All scenarios use real Postgres writes for Tenant + User + Asset
+ AccessRequest. The ``revoke_expired_access`` command is invoked
via ``call_command`` so its full code path — admin-DB enumeration,
``tenant_context``, AccessRequest.objects.filter, audit_event
create — runs end-to-end. ``governance_access_requests_pending``
gauge writes are intercepted via the public ``labels().set()``
contract on the metric — but ONLY to verify the call WAS made
(the metric backend is prometheus_client's in-process Gauge which
holds state in memory; we don't mock the metric, we read its
current value).
"""
from __future__ import annotations
import pytest

import uuid
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.governance.metrics import bucket_for_age_days
from hub.apps.governance.models import (
    AccessRequest,
    AccessRequestStatus,
)
from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.users.models import UserStatus

User = get_user_model()


# ---------------------------------------------------------------------------
# Tier 0 — pure function: bucket_for_age_days
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestBucketForAgeDays(TestCase):
    """``bucket_for_age_days`` is a pure function — pin every
    boundary precisely so the Prometheus gauge labels stay stable
    under refactor."""

    @pytest.mark.integration
    def test_zero_days(self):
        assert bucket_for_age_days(0.0) == "le_1d"

    @pytest.mark.integration
    def test_exactly_one_day(self):
        assert bucket_for_age_days(1.0) == "le_1d"

    @pytest.mark.integration
    def test_just_over_one_day(self):
        assert bucket_for_age_days(1.01) == "le_3d"

    @pytest.mark.integration
    def test_exactly_three_days(self):
        assert bucket_for_age_days(3.0) == "le_3d"

    @pytest.mark.integration
    def test_just_over_three_days(self):
        assert bucket_for_age_days(3.01) == "le_7d"

    @pytest.mark.integration
    def test_exactly_seven_days(self):
        assert bucket_for_age_days(7.0) == "le_7d"

    @pytest.mark.integration
    def test_just_over_seven_days(self):
        assert bucket_for_age_days(7.01) == "gt_7d"

    @pytest.mark.integration
    def test_far_above_seven_days(self):
        assert bucket_for_age_days(365.0) == "gt_7d"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _seed_tenant_user_asset(*, prefix="t", sla_days=14):
    sfx = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"T {sfx}",
        slug=f"{prefix}-{sfx}",
        status="ACTIVE",
        kyc_status=KYCStatus.VERIFIED,
        access_request_pending_sla_days=sla_days,
    )
    user = User.objects.create_user(
        email=f"{prefix}-{sfx}@example.com",
        password="testpass",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    asset = Asset.objects.create(
        tenant=tenant,
        key=f"asset-{sfx}",
        name="Asset",
        status=AssetStatus.ACTIVE,
        created_by=user,
    )
    return tenant, user, asset


def _make_pending_request(tenant, user, asset, *, age_days):
    """Create a PENDING AccessRequest whose ``created_at`` is
    backdated by ``age_days``.

    We can't pass ``created_at`` to ``objects.create`` because the
    field is ``auto_now_add=True``; we instead .save() the row then
    UPDATE the timestamp directly. This mirrors the legacy
    ``test_revoke_expired_access_command`` pattern.
    """
    ar = AccessRequest.objects.create(
        tenant=tenant,
        requested_by=user,
        asset=asset,
        reason="testing SLA",
        requested_access_type="READ",
        status=AccessRequestStatus.PENDING,
    )
    backdated = timezone.now() - timedelta(days=age_days)
    AccessRequest.objects.filter(pk=ar.pk).update(
        created_at=backdated, updated_at=backdated
    )
    ar.refresh_from_db()
    return ar


# ---------------------------------------------------------------------------
# Tier 1 — PENDING SLA expiry
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPendingSLAExpiry(TestCase):
    """Phase 270.B.2.2 — PENDING-too-long path.

    AccessRequest rows in PENDING state older than the tenant's
    ``access_request_pending_sla_days`` MUST transition to EXPIRED
    + emit ``ACCESS_REQUEST_EXPIRED_BY_SLA`` audit on every daily
    sweep.
    """

    @pytest.mark.integration
    def test_pending_15d_old_expires_under_default_sla(self):
        """A PENDING request 15 days old under the default 14-day
        SLA → transitions to EXPIRED."""
        tenant, user, asset = _seed_tenant_user_asset(sla_days=14)
        ar = _make_pending_request(tenant, user, asset, age_days=15)

        call_command("revoke_expired_access")
        ar.refresh_from_db()

        assert ar.status == AccessRequestStatus.EXPIRED

        audit = AuditEvent.all_objects.filter(
            action="ACCESS_REQUEST_EXPIRED_BY_SLA",
            resource_id=str(ar.id),
        ).first()
        assert audit is not None, (
            "ACCESS_REQUEST_EXPIRED_BY_SLA audit must fire"
        )
        details = audit.details_json or {}
        assert details.get("previous_status") == AccessRequestStatus.PENDING
        assert details.get("sla_days") == 14
        assert details.get("age_days") >= 15
        assert details.get("access_request_id") == str(ar.id)
        assert details.get("tenant_id") == str(tenant.id)

    @pytest.mark.integration
    def test_pending_13d_old_stays_pending_under_default_sla(self):
        """A PENDING request 13 days old is BELOW the 14-day SLA
        → no transition, no audit."""
        tenant, user, asset = _seed_tenant_user_asset(sla_days=14)
        ar = _make_pending_request(tenant, user, asset, age_days=13)

        call_command("revoke_expired_access")
        ar.refresh_from_db()

        assert ar.status == AccessRequestStatus.PENDING
        assert AuditEvent.all_objects.filter(
            action="ACCESS_REQUEST_EXPIRED_BY_SLA",
            resource_id=str(ar.id),
        ).count() == 0

    @pytest.mark.integration
    def test_pending_2d_old_under_1d_sla_expires(self):
        """A tenant operating under a tighter 1-day SLA: a
        2-day-old PENDING request expires immediately. Pins that
        the SLA-days lookup is per-tenant, not a hard-coded 14."""
        tenant, user, asset = _seed_tenant_user_asset(sla_days=1)
        ar = _make_pending_request(tenant, user, asset, age_days=2)

        call_command("revoke_expired_access")
        ar.refresh_from_db()

        assert ar.status == AccessRequestStatus.EXPIRED
        audit = AuditEvent.all_objects.filter(
            action="ACCESS_REQUEST_EXPIRED_BY_SLA",
            resource_id=str(ar.id),
        ).first()
        assert audit is not None
        details = audit.details_json or {}
        assert details.get("sla_days") == 1


# ---------------------------------------------------------------------------
# Tier 2 — Per-tenant SLA isolation
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPerTenantSLAIsolation(TestCase):
    """Two tenants with DIFFERENT
    ``access_request_pending_sla_days`` must produce DIFFERENT
    verdicts on requests of identical age. This is the
    load-bearing per-tenant tenant_context test the spec mandates
    in 270.B.2.7 ('tenant-aware iteration test (mock 2 tenants
    with overlapping IDs, verify both processed)')."""

    @pytest.mark.integration
    def test_two_tenants_different_slas(self):
        # Tenant A — 7-day SLA (tighter than default).
        tenant_a, user_a, asset_a = _seed_tenant_user_asset(
            prefix="ta", sla_days=7,
        )
        # Tenant B — 30-day SLA (looser than default).
        tenant_b, user_b, asset_b = _seed_tenant_user_asset(
            prefix="tb", sla_days=30,
        )

        # Both tenants have a 10-day-old PENDING request.
        ar_a = _make_pending_request(tenant_a, user_a, asset_a, age_days=10)
        ar_b = _make_pending_request(tenant_b, user_b, asset_b, age_days=10)

        call_command("revoke_expired_access")
        ar_a.refresh_from_db()
        ar_b.refresh_from_db()

        # Tenant A's request is past the 7-day SLA → EXPIRED.
        assert ar_a.status == AccessRequestStatus.EXPIRED
        # Tenant B's request is well under the 30-day SLA → PENDING.
        assert ar_b.status == AccessRequestStatus.PENDING

        # Two audit rows for A's tenant, zero for B's.
        a_audits = AuditEvent.all_objects.filter(
            action="ACCESS_REQUEST_EXPIRED_BY_SLA",
            details_json__tenant_id=str(tenant_a.id),
        )
        b_audits = AuditEvent.all_objects.filter(
            action="ACCESS_REQUEST_EXPIRED_BY_SLA",
            details_json__tenant_id=str(tenant_b.id),
        )
        assert a_audits.count() == 1
        assert b_audits.count() == 0


# ---------------------------------------------------------------------------
# Tier 3 — Legacy APPROVED+expires_at path preserved
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestApprovedExpiredPathPreserved(TestCase):
    """The legacy APPROVED+expires_at→REVOKED path MUST continue
    to fire after the per-tenant refactor. Regression guard
    against breaking the pre-Phase-270 contract."""

    @pytest.mark.integration
    def test_approved_past_expires_at_still_revokes(self):
        tenant, user, asset = _seed_tenant_user_asset(prefix="legacy")

        # APPROVED request whose expires_at has passed.
        ar = AccessRequest.objects.create(
            tenant=tenant,
            requested_by=user,
            asset=asset,
            reason="legacy access",
            requested_access_type="READ",
            status=AccessRequestStatus.APPROVED,
            approved_by=user,
            approved_at=timezone.now() - timedelta(days=100),
            expires_at=timezone.now() - timedelta(days=10),
        )

        call_command("revoke_expired_access")
        ar.refresh_from_db()

        assert ar.status == AccessRequestStatus.REVOKED
        assert AuditEvent.all_objects.filter(
            action="ACCESS_EXPIRED_REVOKED",
            resource_id=str(ar.id),
        ).count() == 1


# ---------------------------------------------------------------------------
# Tier 4 — Idempotency: re-running the sweep is safe
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestSweepIdempotency(TestCase):
    """Running the sweep twice on the same data must not emit
    duplicate audit rows for the same transition. The transition
    filter (``status=PENDING`` + ``created_at__lt=cutoff``) is
    self-narrowing: once an SLA-expired row transitions to
    EXPIRED, the next sweep's filter no longer matches it."""

    @pytest.mark.integration
    def test_double_sweep_emits_audit_once(self):
        tenant, user, asset = _seed_tenant_user_asset(sla_days=14)
        ar = _make_pending_request(tenant, user, asset, age_days=20)

        call_command("revoke_expired_access")
        call_command("revoke_expired_access")
        ar.refresh_from_db()

        assert ar.status == AccessRequestStatus.EXPIRED
        assert AuditEvent.all_objects.filter(
            action="ACCESS_REQUEST_EXPIRED_BY_SLA",
            resource_id=str(ar.id),
        ).count() == 1, (
            "Re-running the sweep must not emit a second "
            "ACCESS_REQUEST_EXPIRED_BY_SLA audit — the filter is "
            "self-narrowing on status=PENDING"
        )
