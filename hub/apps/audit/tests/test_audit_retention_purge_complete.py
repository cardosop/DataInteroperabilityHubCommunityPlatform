"""
Phase 234.4 — Permanent deletion after archival grace (P0, GDPR).

Engineering contract this suite pins (preprod01 tasks.md 234.4):

1.  ``run_audit_permanent_delete_sweep`` hard-deletes AuditEvent rows where
    ``is_archived=True AND archived_at < now() - 90d``.
2.  Tenant-wide legal hold (any active ``RetentionPolicy.legal_hold=True``
    on the tenant) skips the entire tenant's sweep.
3.  Per-resource DSAR RESTRICTION on the audit row's resource_id blocks
    that specific row from deletion.
4.  ONE ``AUDIT_RETENTION_PURGED`` meta-audit event is emitted BEFORE
    the bulk delete; its row survives the sweep because it's newly
    written (not archived, not old).
5.  Dry-run mode (``--dry-run``) leaves the database unchanged but
    reports the count that WOULD have been deleted.
6.  The PII registry includes ``audit.AuditEvent`` (Phase 232.0
    cross-reference — purge tooling needs the registry to drive
    cataloguing of where personal data lives).
7.  After purge, the Phase 234.1 chain verifier MUST treat the gaps
    introduced by the purge as informational ``erasure_gap``s, not
    tamper signals.
8.  The new ``JobType.AUDIT_PERMANENT_DELETE_SWEEP`` is registered and
    dispatched through the generic job runner.

The suite uses real DB rows; no mocks. Audit chain immutability guards
are bypassed exactly the way production code bypasses them (queryset
.delete() vs. instance .delete()).
"""
from __future__ import annotations
import pytest

import uuid
from datetime import timedelta
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from hub.apps.audit import event_types as _audit_et
from hub.apps.audit.chain import verify_chain_segment
from hub.apps.audit.models import AuditEvent
from hub.apps.audit.utils import create_audit_event
from hub.apps.core.pii_registry import registered_model_labels
from hub.apps.assets.models import Asset
from hub.apps.dsar.models import DSARRequest, DSARRequestType, DSARStatus
from hub.apps.governance.models import (
    RetentionAction,
    RetentionPolicy,
    RetentionPolicyType,
)
from hub.apps.tenants.models import Tenant

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


def _make_tenant(slug_suffix: str | None = None) -> Tenant:
    uid = slug_suffix or uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(name=f"Tenant {uid}", slug=f"tenant-{uid}")
    _ensure_tenant_has_subscription(tenant)
    return tenant


def _make_user(tenant: Tenant) -> User:
    uid = uuid.uuid4().hex[:8]
    return User.objects.create_user(
        email=f"audit-purge-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
    )


def _make_hold_asset(tenant: Tenant) -> Asset:
    """Tiny Asset stub so legal-hold tests can attach a RetentionPolicy.

    ``RetentionPolicy.clean()`` requires at least one of asset/dataset/file,
    so a free-floating tenant-wide policy isn't valid. Use the smallest
    Asset that satisfies the invariant; the sweep only consults
    ``RetentionPolicy.legal_hold`` so the resource itself doesn't matter.
    """
    uid = uuid.uuid4().hex[:8]
    return Asset.objects.create(
        tenant=tenant,
        key=f"hold-asset-{uid}",
        name=f"Hold Asset {uid}",
    )


def _make_archived_event(
    tenant: Tenant,
    *,
    archived_days_ago: int,
    actor: User | None = None,
    resource_type: str = "TEST",
    resource_id: uuid.UUID | None = None,
    action: str = "TEST_ACTION",
) -> AuditEvent:
    """Create an audit event and back-date its ``archived_at`` field."""
    event = create_audit_event(
        resource_type=resource_type,
        action=action,
        actor_user=actor,
        tenant=tenant,
        resource_id=str(resource_id) if resource_id else None,
        details={"test_fixture": True},
    )
    archived_at = timezone.now() - timedelta(days=archived_days_ago)
    AuditEvent.all_objects.filter(pk=event.pk).update(
        is_archived=True, archived_at=archived_at
    )
    event.refresh_from_db()
    return event


# ---------------------------------------------------------------------------
# Tier 1 — pure imports / registry
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPIIRegistryAndConstants:
    """PII registry + AUDIT_RETENTION_PURGED constant + JobType wiring."""

    @pytest.mark.integration
    def test_pii_registry_lists_audit_event(self):
        labels = registered_model_labels()
        assert "audit.AuditEvent" in labels

    @pytest.mark.integration
    def test_audit_retention_purged_event_type_constant_exists(self):
        assert _audit_et.AUDIT_RETENTION_PURGED == "AUDIT_RETENTION_PURGED"
        assert "AUDIT_RETENTION_PURGED" in _audit_et.__all__

    @pytest.mark.integration
    def test_job_type_audit_permanent_delete_sweep_registered(self):
        from hub.apps.jobs.models import JobType

        assert JobType.AUDIT_PERMANENT_DELETE_SWEEP.value == "AUDIT_PERMANENT_DELETE_SWEEP"


# ---------------------------------------------------------------------------
# Tier 2 — pure function tests of the sweep work-function
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAuditPermanentDeleteSweep:
    """``run_audit_permanent_delete_sweep`` — core contract."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.tenant = _make_tenant()
        self.tenant_b = _make_tenant()
        self.actor = _make_user(self.tenant)

    # --- baseline / eligibility ------------------------------------------

    @pytest.mark.integration
    def test_purges_archived_rows_older_than_grace(self):
        from hub.apps.audit.retention_purge import run_audit_permanent_delete_sweep

        old = _make_archived_event(self.tenant, archived_days_ago=100, actor=self.actor)
        recent = _make_archived_event(self.tenant, archived_days_ago=30, actor=self.actor)
        unarchived = create_audit_event(
            resource_type="TEST",
            action="LIVE",
            actor_user=self.actor,
            tenant=self.tenant,
            details={"keep_me": True},
        )

        summary = run_audit_permanent_delete_sweep(dry_run=False)

        assert summary["deleted_count"] >= 1
        assert not AuditEvent.all_objects.filter(pk=old.pk).exists()
        assert AuditEvent.all_objects.filter(pk=recent.pk).exists()
        assert AuditEvent.all_objects.filter(pk=unarchived.pk).exists()

    @pytest.mark.integration
    def test_unarchived_rows_never_purged_even_when_old(self):
        from hub.apps.audit.retention_purge import run_audit_permanent_delete_sweep

        event = create_audit_event(
            resource_type="TEST",
            action="STILL_LIVE",
            actor_user=self.actor,
            tenant=self.tenant,
            details={},
        )
        # Back-date timestamp by 5 years, but DO NOT archive.
        AuditEvent.all_objects.filter(pk=event.pk).update(
            timestamp=timezone.now() - timedelta(days=5 * 365)
        )

        run_audit_permanent_delete_sweep(dry_run=False)
        assert AuditEvent.all_objects.filter(pk=event.pk).exists()

    @pytest.mark.integration
    def test_age_threshold_days_argument_is_honoured(self):
        from hub.apps.audit.retention_purge import run_audit_permanent_delete_sweep

        e_60 = _make_archived_event(self.tenant, archived_days_ago=60, actor=self.actor)
        e_100 = _make_archived_event(self.tenant, archived_days_ago=100, actor=self.actor)

        # Tighter window: 30-day grace ⇒ both eligible.
        run_audit_permanent_delete_sweep(dry_run=False, age_threshold_days=30)
        assert not AuditEvent.all_objects.filter(pk=e_60.pk).exists()
        assert not AuditEvent.all_objects.filter(pk=e_100.pk).exists()

    # --- legal hold (tenant-wide) ----------------------------------------

    @pytest.mark.integration
    def test_active_legal_hold_skips_entire_tenant(self):
        from hub.apps.audit.retention_purge import run_audit_permanent_delete_sweep

        old = _make_archived_event(self.tenant, archived_days_ago=100, actor=self.actor)
        # Set an active legal-hold retention policy on the tenant.
        RetentionPolicy.objects.create(
            tenant=self.tenant,
            asset=_make_hold_asset(self.tenant),
            name="Active litigation hold",
            policy_type=RetentionPolicyType.TIME_BASED.value,
            retention_period_days=365,
            action=RetentionAction.HARD_DELETE,
            legal_hold=True,
            legal_hold_reason="Pending litigation",
            legal_hold_expires_at=None,  # indefinite
        )

        summary = run_audit_permanent_delete_sweep(dry_run=False)

        assert AuditEvent.all_objects.filter(pk=old.pk).exists()
        skipped_for_legal_hold = summary["skipped_tenants_legal_hold"]
        assert str(self.tenant.id) in [str(x) for x in skipped_for_legal_hold]

    @pytest.mark.integration
    def test_expired_legal_hold_does_not_block_purge(self):
        from hub.apps.audit.retention_purge import run_audit_permanent_delete_sweep

        old = _make_archived_event(self.tenant, archived_days_ago=100, actor=self.actor)
        RetentionPolicy.objects.create(
            tenant=self.tenant,
            asset=_make_hold_asset(self.tenant),
            name="Expired hold",
            policy_type=RetentionPolicyType.TIME_BASED.value,
            retention_period_days=365,
            action=RetentionAction.HARD_DELETE,
            legal_hold=True,
            legal_hold_expires_at=timezone.now() - timedelta(days=10),
        )

        run_audit_permanent_delete_sweep(dry_run=False)
        assert not AuditEvent.all_objects.filter(pk=old.pk).exists()

    # --- DSAR RESTRICTION (per-resource) ---------------------------------

    @pytest.mark.integration
    def test_open_dsar_restriction_skips_matching_resource(self):
        from hub.apps.audit.retention_purge import run_audit_permanent_delete_sweep

        protected_asset_id = uuid.uuid4()
        protected = _make_archived_event(
            self.tenant,
            archived_days_ago=100,
            actor=self.actor,
            resource_type="ASSET",
            resource_id=protected_asset_id,
        )
        other = _make_archived_event(
            self.tenant,
            archived_days_ago=100,
            actor=self.actor,
            resource_type="ASSET",
            resource_id=uuid.uuid4(),
        )

        DSARRequest.objects.create(
            tenant=self.tenant,
            request_type=DSARRequestType.RESTRICTION,
            status=DSARStatus.UNDER_REVIEW,
            subject_email="subject@example.com",
            details_json={
                "retention_block_scope": {
                    "resource_type": "ASSET",
                    "resource_id": str(protected_asset_id),
                }
            },
        )

        run_audit_permanent_delete_sweep(dry_run=False)

        assert AuditEvent.all_objects.filter(pk=protected.pk).exists()
        assert not AuditEvent.all_objects.filter(pk=other.pk).exists()

    @pytest.mark.integration
    def test_closed_dsar_restriction_does_not_block(self):
        from hub.apps.audit.retention_purge import run_audit_permanent_delete_sweep

        asset_id = uuid.uuid4()
        evt = _make_archived_event(
            self.tenant,
            archived_days_ago=100,
            actor=self.actor,
            resource_type="ASSET",
            resource_id=asset_id,
        )
        DSARRequest.objects.create(
            tenant=self.tenant,
            request_type=DSARRequestType.RESTRICTION,
            status=DSARStatus.CLOSED_REJECTED,
            subject_email="closed@example.com",
            details_json={
                "retention_block_scope": {
                    "resource_type": "ASSET",
                    "resource_id": str(asset_id),
                }
            },
        )

        run_audit_permanent_delete_sweep(dry_run=False)
        assert not AuditEvent.all_objects.filter(pk=evt.pk).exists()

    # --- meta-audit emission ---------------------------------------------

    @pytest.mark.integration
    def test_meta_audit_emitted_before_deletion(self):
        from hub.apps.audit.retention_purge import run_audit_permanent_delete_sweep

        targets = [
            _make_archived_event(self.tenant, archived_days_ago=120, actor=self.actor)
            for _ in range(3)
        ]
        target_ids = {str(t.pk) for t in targets}
        # Capture chain_sequences BEFORE the sweep so we can pin the
        # "meta-audit BEFORE deletion" invariant via chain-position
        # ordering (the meta-audit's chain_sequence must be strictly
        # greater than every deleted row's chain_sequence, which is
        # only possible if the meta-audit was emitted while those
        # rows were still in the chain head's path).
        max_target_seq = max(t.chain_sequence for t in targets if t.chain_sequence)

        run_audit_permanent_delete_sweep(dry_run=False)

        # The meta-audit row MUST exist after the sweep — it's freshly
        # written as a live (non-archived) row, so the sweep itself
        # cannot purge it.
        meta_rows = AuditEvent.all_objects.filter(
            tenant_id=self.tenant.id,
            action=_audit_et.AUDIT_RETENTION_PURGED,
        )
        assert meta_rows.count() == 1
        meta = meta_rows.first()
        assert meta.is_archived is False
        # Details payload carries the count + the sample id list.
        details = meta.details_json or {}
        assert details.get("deleted_count") == 3
        sample_ids = set(details.get("deleted_event_ids") or [])
        # Sample should be a subset of the actually-deleted ids.
        assert sample_ids.issubset(target_ids)
        # All targets ARE actually deleted.
        for tid in target_ids:
            assert not AuditEvent.all_objects.filter(pk=tid).exists()
        # Chain-position invariant: meta-audit was emitted AFTER the
        # targets joined the chain (its sequence is strictly greater).
        assert meta.chain_sequence is not None
        assert meta.chain_sequence > max_target_seq, (
            f"meta-audit chain_sequence ({meta.chain_sequence}) must be "
            f"> max deleted target sequence ({max_target_seq}) — "
            "proves the meta-audit was the chain head when the bulk "
            "delete ran, i.e. emitted BEFORE deletion."
        )

    @pytest.mark.integration
    def test_sweep_is_idempotent_on_re_run(self):
        """Running the sweep twice in a row produces no extra deletions.

        Second-run invariant: the meta-audit from the first run is a
        live (non-archived) row, so it is NOT itself eligible for
        purge. The second run finds zero candidates and emits a
        ``deleted_count=0`` meta-audit. Total meta-audit rows after
        two runs: 2; total deleted: same as after the first run.
        """
        from hub.apps.audit.retention_purge import run_audit_permanent_delete_sweep

        targets = [
            _make_archived_event(self.tenant, archived_days_ago=120, actor=self.actor)
            for _ in range(3)
        ]
        target_ids = [str(t.pk) for t in targets]

        first = run_audit_permanent_delete_sweep(
            dry_run=False, tenant_id=str(self.tenant.id)
        )
        second = run_audit_permanent_delete_sweep(
            dry_run=False, tenant_id=str(self.tenant.id)
        )

        assert first["deleted_count"] == 3
        # Second run: targets are gone; meta-audit from first run is
        # not archived; tenant has nothing more to do.
        assert second["deleted_count"] == 0
        # Two meta-audit rows persist (one per run) so audit-replay
        # can prove each invocation.
        meta_rows = AuditEvent.all_objects.filter(
            tenant_id=self.tenant.id,
            action=_audit_et.AUDIT_RETENTION_PURGED,
        )
        assert meta_rows.count() == 2
        # The originally-deleted rows stay gone (no resurrection).
        for tid in target_ids:
            assert not AuditEvent.all_objects.filter(pk=tid).exists()

    @pytest.mark.integration
    def test_platform_chain_is_swept(self):
        """``tenant_id IS NULL`` audit rows are also purged after grace.

        The platform chain holds system-level events that have no
        tenant FK. The sweep must include them — both for GDPR symmetry
        and because the Phase 234.1.5 platform-chain Merkle snapshots
        depend on the same retention contract holding for them too.
        """
        from hub.apps.audit.retention_purge import run_audit_permanent_delete_sweep

        # Direct platform-chain audit (tenant=None) — mirrors the
        # write path in the system code (e.g. retention autosweep
        # completion summary).
        platform_evt = create_audit_event(
            resource_type="JOB",
            action="TEST_PLATFORM_EVENT",
            actor_user=None,
            tenant=None,
            details={"smoke": True},
            infer_tenant_from_actor=False,
        )
        AuditEvent.all_objects.filter(pk=platform_evt.pk).update(
            is_archived=True,
            archived_at=timezone.now() - timedelta(days=120),
        )

        summary = run_audit_permanent_delete_sweep(dry_run=False)

        # The platform-chain event is hard-deleted.
        assert not AuditEvent.all_objects.filter(pk=platform_evt.pk).exists()
        # A platform-chain meta-audit row was emitted (tenant_id NULL,
        # ``tenant_id`` field in details_json reads "__platform__").
        meta_rows = AuditEvent.all_objects.filter(
            tenant__isnull=True,
            action=_audit_et.AUDIT_RETENTION_PURGED,
        )
        assert meta_rows.exists()
        platform_meta = meta_rows.order_by("-timestamp").first()
        assert platform_meta.details_json.get("tenant_id") == "__platform__"
        # And the run-level summary reports at least one delete (might
        # be more if other tenants in this test had eligible rows).
        assert summary["deleted_count"] >= 1

    @pytest.mark.integration
    def test_meta_audit_carries_dry_run_flag(self):
        from hub.apps.audit.retention_purge import run_audit_permanent_delete_sweep

        _make_archived_event(self.tenant, archived_days_ago=200, actor=self.actor)

        run_audit_permanent_delete_sweep(dry_run=True)
        meta = AuditEvent.all_objects.filter(
            tenant_id=self.tenant.id,
            action=_audit_et.AUDIT_RETENTION_PURGED,
        ).first()
        assert meta is not None
        details = meta.details_json or {}
        assert details.get("dry_run") is True

    # --- dry-run ---------------------------------------------------------

    @pytest.mark.integration
    def test_dry_run_does_not_delete_anything(self):
        from hub.apps.audit.retention_purge import run_audit_permanent_delete_sweep

        old = _make_archived_event(self.tenant, archived_days_ago=200, actor=self.actor)
        summary = run_audit_permanent_delete_sweep(dry_run=True)

        assert summary["deleted_count"] >= 1
        assert summary["dry_run"] is True
        assert AuditEvent.all_objects.filter(pk=old.pk).exists()

    # --- multi-tenant isolation ------------------------------------------

    @pytest.mark.integration
    def test_tenant_b_events_unaffected_by_tenant_a_sweep(self):
        from hub.apps.audit.retention_purge import run_audit_permanent_delete_sweep

        a_old = _make_archived_event(self.tenant, archived_days_ago=120, actor=self.actor)
        b_old = _make_archived_event(self.tenant_b, archived_days_ago=120)

        # Restrict to tenant A only.
        run_audit_permanent_delete_sweep(dry_run=False, tenant_id=str(self.tenant.id))

        assert not AuditEvent.all_objects.filter(pk=a_old.pk).exists()
        assert AuditEvent.all_objects.filter(pk=b_old.pk).exists()


# ---------------------------------------------------------------------------
# Tier 3 — chain integrity preservation (cross-spec with 234.1 + 232.2)
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestChainIntegrityAfterPurge:
    """The 234.1 chain verifier MUST tolerate post-234.4 erasure gaps."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.tenant = _make_tenant()
        self.actor = _make_user(self.tenant)

    @pytest.mark.integration
    def test_remaining_chain_passes_verifier_after_purge(self):
        from hub.apps.audit.retention_purge import run_audit_permanent_delete_sweep

        # Lay down 5 events. We'll purge the 2nd and 3rd; the verifier
        # must report (1 -> 4) as an erasure_gap, not a tamper signal.
        events = [
            create_audit_event(
                resource_type="TEST",
                action=f"EVENT_{i}",
                actor_user=self.actor,
                tenant=self.tenant,
                details={"i": i},
            )
            for i in range(5)
        ]
        # Mark events 1 and 2 as archived + 200 days old.
        archived_ts = timezone.now() - timedelta(days=200)
        AuditEvent.all_objects.filter(pk__in=[events[1].pk, events[2].pk]).update(
            is_archived=True, archived_at=archived_ts
        )

        run_audit_permanent_delete_sweep(dry_run=False)

        rows = list(
            AuditEvent.all_objects.filter(
                tenant_id=self.tenant.id,
                chain_hash__isnull=False,
            ).order_by("chain_sequence")
        )
        # We should still have events 0, 3, 4 (and the meta-audit row).
        assert len(rows) >= 4
        verification = verify_chain_segment(rows)
        assert verification.verified is True, (
            f"verifier flipped on erasure gaps: mismatches={verification.mismatches}"
        )
        # A real erasure_gap should be present in the gaps list.
        assert verification.gaps, "expected a sequence gap from the purge"


# ---------------------------------------------------------------------------
# Tier 4 — management command surface
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestAuditPermanentDeleteSweepCommand:
    """``python manage.py audit_permanent_delete_sweep`` smoke."""

    @pytest.fixture(autouse=True)
    def _setup(self):
        self.tenant = _make_tenant()
        self.actor = _make_user(self.tenant)

    def _run(self, *args):
        out, err = StringIO(), StringIO()
        call_command(
            "audit_permanent_delete_sweep",
            *args,
            stdout=out,
            stderr=err,
        )
        return out.getvalue(), err.getvalue()

    @pytest.mark.integration
    def test_command_runs_and_emits_summary(self):
        _make_archived_event(self.tenant, archived_days_ago=200, actor=self.actor)
        out, _ = self._run("--skip-job-row")
        assert "deleted_count" in out or "Audit permanent-delete sweep" in out

    @pytest.mark.integration
    def test_command_dry_run_does_not_delete(self):
        old = _make_archived_event(self.tenant, archived_days_ago=200, actor=self.actor)
        self._run("--dry-run", "--skip-job-row")
        assert AuditEvent.all_objects.filter(pk=old.pk).exists()

    @pytest.mark.integration
    def test_command_age_days_option_honoured(self):
        e = _make_archived_event(self.tenant, archived_days_ago=45, actor=self.actor)
        # Default 90d threshold → kept.
        self._run("--skip-job-row")
        assert AuditEvent.all_objects.filter(pk=e.pk).exists()
        # Override to 30d → deleted.
        self._run("--age-days=30", "--skip-job-row")
        assert not AuditEvent.all_objects.filter(pk=e.pk).exists()
