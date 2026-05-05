"""
Phase 250.1.E.3 — tests for the orphan-DRAFT cleanup management command.

Contract under test
-------------------
The command at
``hub/apps/assets/management/commands/cleanup_orphan_drafts.py`` MUST:

* Be **idempotent**: re-running on the same DB state produces the same
  result with no side effects beyond an additional dry-run audit row.
* Process orphans in **batches of N rows** (default 500) — each batch
  is its own transaction, so a single sweep doesn't hold table locks
  for the whole tenant history.
* Default to **dry-run mode** for the first 7 days post-deploy via
  ``ASSET_ORPHAN_CLEANUP_DRY_RUN=true`` env var (mirrors D240.16).
  Pass ``--no-dry-run`` to override the env var.
* Emit one ``ASSET_ORPHAN_DRAFT_PURGED`` audit row **per batch**
  (NOT per row) with ``details_json={tenant_id, count, dry_run, batch,
  age_threshold_days, asset_ids}`` for SRE triage.
* Define orphan as ``Asset.status='DRAFT' AND created_at <
  now-age_threshold_days``. The age threshold is configurable via
  ``--age-threshold-days`` (default 30 per
  ``docs/runbooks/orphan-draft-cleanup.md``).
* Optional ``--tenant-id=<uuid>`` filter for one-off / smoke runs.
* Console output reports per-tenant counts + global total in
  human-readable form for the K8s CronJob log scraping.

TDD doctrine
------------
* Real Django ORM rows + real ``call_command(...)`` machinery — no
  mocks of business logic.
* Tests are written BEFORE the implementation per the TDD contract.
  They will RED until the command lands; once it lands they validate
  it satisfies every clause above.
* Test isolation via ``pytest.mark.django_db(transaction=True)`` — the
  command's per-batch transactions roll back per-test.
"""
from __future__ import annotations

import io
import os
import uuid
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant


pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _seed_tenant(*, slug_suffix: str | None = None) -> Tenant:
    uid = slug_suffix or uuid.uuid4().hex[:8]
    return Tenant.objects.create(
        name=f"OrphanCleanupTest-{uid}",
        slug=f"orphan-cleanup-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )


def _seed_user(tenant: Tenant) -> "User":
    return User.objects.create_user(
        email=f"u-{uuid.uuid4().hex[:8]}@example.com",
        password="testpass123",
        tenant=tenant,
    )


def _seed_orphan_draft(
    *,
    tenant: Tenant,
    user: "User",
    age_days: int,
    key: str | None = None,
) -> Asset:
    """Seed a DRAFT asset whose ``created_at`` is ``age_days`` in the past."""
    asset = Asset.objects.create(
        tenant=tenant,
        key=key or f"orphan-{uuid.uuid4().hex[:8]}",
        name="Orphan DRAFT",
        status=AssetStatus.DRAFT,
        created_by=user,
    )
    # auto_now_add=True forces created_at to now; back-date via update().
    Asset.objects.filter(pk=asset.pk).update(
        created_at=timezone.now() - timedelta(days=age_days),
    )
    asset.refresh_from_db()
    return asset


def _seed_active_asset(*, tenant: Tenant, user: "User", age_days: int = 60) -> Asset:
    """Seed an ACTIVE asset (NOT an orphan candidate regardless of age)."""
    asset = Asset.objects.create(
        tenant=tenant,
        key=f"active-{uuid.uuid4().hex[:8]}",
        name="Active Asset",
        status=AssetStatus.ACTIVE,
        created_by=user,
    )
    Asset.objects.filter(pk=asset.pk).update(
        created_at=timezone.now() - timedelta(days=age_days),
    )
    return asset


def _run_command(*args, expect_exit_zero: bool = True) -> str:
    """Invoke the command + return captured stdout. The command exits 0
    on success regardless of whether anything was purged (a no-op sweep
    is a normal occurrence). Tests that EXPECT a failure exit set
    ``expect_exit_zero=False``."""
    stdout = io.StringIO()
    if expect_exit_zero:
        call_command("cleanup_orphan_drafts", *args, stdout=stdout)
    else:
        with pytest.raises(SystemExit):
            call_command("cleanup_orphan_drafts", *args, stdout=stdout)
    return stdout.getvalue()


# ---------------------------------------------------------------------------
# 250.1.E.3.a — basic orphan discovery + hard-delete
# ---------------------------------------------------------------------------


class TestOrphanDiscovery:
    """The command MUST identify and delete orphan DRAFT assets."""

    def test_orphan_draft_older_than_threshold_is_deleted(self):
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        orphan = _seed_orphan_draft(tenant=tenant, user=user, age_days=45)

        _run_command("--no-dry-run")

        assert not Asset.objects.filter(pk=orphan.pk).exists(), (
            "Orphan DRAFT older than 30-day threshold MUST be hard-"
            "deleted in non-dry-run mode."
        )

    def test_recent_draft_is_NOT_deleted(self):
        """A DRAFT created 5 days ago is not yet orphan."""
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        recent = _seed_orphan_draft(tenant=tenant, user=user, age_days=5)

        _run_command("--no-dry-run")

        assert Asset.objects.filter(pk=recent.pk).exists(), (
            "Recent DRAFT (under threshold) MUST be preserved."
        )

    def test_active_asset_is_NEVER_deleted_regardless_of_age(self):
        """An ACTIVE asset is never an orphan, even if old."""
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        active = _seed_active_asset(tenant=tenant, user=user, age_days=365)

        _run_command("--no-dry-run")

        assert Asset.objects.filter(pk=active.pk).exists(), (
            "ACTIVE asset MUST never be deleted by orphan cleanup."
        )

    def test_custom_age_threshold(self):
        """``--age-threshold-days=10`` makes 15-day-old DRAFTs orphan."""
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        target = _seed_orphan_draft(tenant=tenant, user=user, age_days=15)
        spared = _seed_orphan_draft(tenant=tenant, user=user, age_days=5)

        _run_command("--no-dry-run", "--age-threshold-days=10")

        assert not Asset.objects.filter(pk=target.pk).exists()
        assert Asset.objects.filter(pk=spared.pk).exists()


# ---------------------------------------------------------------------------
# 250.1.E.3.b — dry-run idempotency + env-var safety net
# ---------------------------------------------------------------------------


class TestDryRunIdempotency:
    """Dry-run mode MUST NOT delete; re-running is idempotent."""

    def test_dry_run_does_not_delete(self):
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        orphan = _seed_orphan_draft(tenant=tenant, user=user, age_days=45)

        _run_command("--dry-run")

        assert Asset.objects.filter(pk=orphan.pk).exists(), (
            "Dry-run MUST preserve the orphan (no DB writes)."
        )

    def test_env_var_forces_dry_run(self):
        """``ASSET_ORPHAN_CLEANUP_DRY_RUN=true`` forces dry-run even
        without ``--dry-run`` on the CLI (D240.16 7-day safety net)."""
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        orphan = _seed_orphan_draft(tenant=tenant, user=user, age_days=45)

        with patch.dict(os.environ, {"ASSET_ORPHAN_CLEANUP_DRY_RUN": "true"}):
            _run_command()  # no --dry-run flag

        assert Asset.objects.filter(pk=orphan.pk).exists(), (
            "Env var ASSET_ORPHAN_CLEANUP_DRY_RUN=true MUST force "
            "dry-run regardless of CLI args."
        )

    def test_no_dry_run_overrides_env_var(self):
        """``--no-dry-run`` MUST override the env-var safety net so
        post-soak operators can deliberately enable hard-delete."""
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        orphan = _seed_orphan_draft(tenant=tenant, user=user, age_days=45)

        with patch.dict(os.environ, {"ASSET_ORPHAN_CLEANUP_DRY_RUN": "true"}):
            _run_command("--no-dry-run")

        assert not Asset.objects.filter(pk=orphan.pk).exists(), (
            "--no-dry-run MUST override the env-var safety net."
        )

    def test_dry_run_idempotent_re_invocation(self):
        """Re-running dry-run produces the same DB state. The audit
        trail accumulates one row per invocation (intentional — each
        invocation is a separate observation event)."""
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        _seed_orphan_draft(tenant=tenant, user=user, age_days=45)

        _run_command("--dry-run")
        asset_count_after_first = Asset.objects.filter(tenant=tenant).count()
        _run_command("--dry-run")
        asset_count_after_second = Asset.objects.filter(tenant=tenant).count()

        assert asset_count_after_first == asset_count_after_second
        # Audit rows accumulate across invocations.
        audit_count = AuditEvent.objects.filter(
            tenant=tenant,
            action=audit_event_types.ASSET_ORPHAN_DRAFT_PURGED,
        ).count()
        assert audit_count == 2, (
            "Each dry-run invocation MUST emit its own audit row."
        )


# ---------------------------------------------------------------------------
# 250.1.E.3.c — batched processing
# ---------------------------------------------------------------------------


class TestBatchedProcessing:
    """The command processes orphans in batches of ``--batch-size`` rows
    (default 500). Each batch is its own transaction so a sweep doesn't
    hold table locks for the whole tenant."""

    def test_batched_processing_emits_audit_per_batch(self):
        """3 orphans + batch_size=2 → 2 batches → 2 audit rows."""
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        for _ in range(3):
            _seed_orphan_draft(tenant=tenant, user=user, age_days=45)

        _run_command("--no-dry-run", "--batch-size=2")

        assert Asset.objects.filter(tenant=tenant).count() == 0
        audit_rows = AuditEvent.objects.filter(
            tenant=tenant,
            action=audit_event_types.ASSET_ORPHAN_DRAFT_PURGED,
        ).order_by("timestamp")
        assert audit_rows.count() == 2, (
            "3 orphans + batch_size=2 MUST emit 2 audit rows (batch 1 = 2 "
            f"orphans, batch 2 = 1 orphan); got {audit_rows.count()}."
        )
        # Batch counts: first batch = 2; second batch = 1.
        details_first = audit_rows[0].details_json or {}
        details_second = audit_rows[1].details_json or {}
        assert details_first.get("count") == 2
        assert details_second.get("count") == 1
        # Batch numbers are 1-indexed.
        assert details_first.get("batch") == 1
        assert details_second.get("batch") == 2
        # All batches in one cron-run carry the same correlation_id so
        # SRE can pivot from "last night's 04:00 sweep" to per-batch
        # detail without joining on timestamp windows.
        assert details_first.get("correlation_id"), (
            "audit row MUST include a correlation_id"
        )
        assert (
            details_first.get("correlation_id")
            == details_second.get("correlation_id")
        ), (
            "All batches from the same sweep MUST share one "
            "correlation_id."
        )

    def test_default_batch_size_is_500(self):
        """When ``--batch-size`` is omitted, default is 500."""
        # Smoke: seed 1 orphan; assert one batch with batch_size <= 500
        # (we can't easily seed 501 rows in a unit test, but the default
        # is documented in the audit details for SRE traceability).
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        _seed_orphan_draft(tenant=tenant, user=user, age_days=45)

        out = _run_command("--no-dry-run")
        # The output reports the batch size at start; assert 500 appears.
        assert "500" in out or "batch_size=500" in out.lower(), (
            f"Default batch size of 500 MUST be reported in the command "
            f"output; got: {out}"
        )


# ---------------------------------------------------------------------------
# 250.1.E.3.d — audit emission semantics
# ---------------------------------------------------------------------------


class TestAuditEmission:
    """Audit rows MUST carry the diagnostics SRE needs for triage."""

    def test_audit_details_json_shape(self):
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        for _ in range(3):
            _seed_orphan_draft(tenant=tenant, user=user, age_days=45)

        _run_command("--no-dry-run", "--age-threshold-days=30")

        audit_row = AuditEvent.objects.filter(
            tenant=tenant,
            action=audit_event_types.ASSET_ORPHAN_DRAFT_PURGED,
        ).first()
        assert audit_row is not None, "audit row MUST be emitted"
        details = audit_row.details_json or {}
        # Required keys per the contract.
        for required_key in (
            "tenant_id", "count", "dry_run", "batch",
            "age_threshold_days", "asset_ids", "correlation_id",
        ):
            assert required_key in details, (
                f"audit details_json MUST include {required_key!r}; "
                f"got keys {list(details.keys())}"
            )
        assert details["dry_run"] is False
        assert details["age_threshold_days"] == 30
        # asset_ids is a sample (first 10) — for batch of 3, it has all 3.
        assert isinstance(details["asset_ids"], list)
        assert 1 <= len(details["asset_ids"]) <= 10

    def test_audit_dry_run_flag_recorded(self):
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        _seed_orphan_draft(tenant=tenant, user=user, age_days=45)

        _run_command("--dry-run")

        audit_row = AuditEvent.objects.filter(
            tenant=tenant,
            action=audit_event_types.ASSET_ORPHAN_DRAFT_PURGED,
        ).first()
        assert audit_row is not None
        assert (audit_row.details_json or {}).get("dry_run") is True

    def test_zero_orphans_emits_no_audit_row(self):
        """A no-op sweep (zero orphans) MUST NOT clutter the audit
        trail. SRE wants the trail dense — every row meaningful."""
        tenant = _seed_tenant()
        user = _seed_user(tenant)
        # Seed only recent + active assets — no orphans.
        _seed_orphan_draft(tenant=tenant, user=user, age_days=5)
        _seed_active_asset(tenant=tenant, user=user, age_days=365)

        _run_command("--no-dry-run")

        audit_count = AuditEvent.objects.filter(
            tenant=tenant,
            action=audit_event_types.ASSET_ORPHAN_DRAFT_PURGED,
        ).count()
        assert audit_count == 0, (
            "Zero-orphan sweep MUST NOT emit audit rows; "
            f"got {audit_count}."
        )


# ---------------------------------------------------------------------------
# 250.1.E.3.e — tenant filter + multi-tenant isolation
# ---------------------------------------------------------------------------


class TestTenantFilter:
    """``--tenant-id=<uuid>`` MUST scope the sweep to a single tenant.
    Without the flag, every tenant is processed. Cross-tenant leakage
    is forbidden."""

    def test_tenant_filter_processes_only_named_tenant(self):
        tenant_a = _seed_tenant(slug_suffix="a")
        tenant_b = _seed_tenant(slug_suffix="b")
        user_a = _seed_user(tenant_a)
        user_b = _seed_user(tenant_b)
        orphan_a = _seed_orphan_draft(tenant=tenant_a, user=user_a, age_days=45)
        orphan_b = _seed_orphan_draft(tenant=tenant_b, user=user_b, age_days=45)

        _run_command("--no-dry-run", f"--tenant-id={tenant_a.id}")

        assert not Asset.objects.filter(pk=orphan_a.pk).exists()
        assert Asset.objects.filter(pk=orphan_b.pk).exists(), (
            "Tenant B's orphan MUST be untouched when --tenant-id "
            "targets tenant A."
        )

    def test_no_filter_processes_all_tenants(self):
        tenant_a = _seed_tenant(slug_suffix="a")
        tenant_b = _seed_tenant(slug_suffix="b")
        user_a = _seed_user(tenant_a)
        user_b = _seed_user(tenant_b)
        orphan_a = _seed_orphan_draft(tenant=tenant_a, user=user_a, age_days=45)
        orphan_b = _seed_orphan_draft(tenant=tenant_b, user=user_b, age_days=45)

        _run_command("--no-dry-run")

        assert not Asset.objects.filter(pk=orphan_a.pk).exists()
        assert not Asset.objects.filter(pk=orphan_b.pk).exists()
