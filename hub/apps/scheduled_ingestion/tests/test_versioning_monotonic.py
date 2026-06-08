"""
Phase 260.7.C — Scheduled-ingestion versioning invariants (closes Gap 17).

Pre-260.7.C, the scheduled-ingestion worker
(:func:`hub.apps.scheduled_ingestion.worker_services.process_file_for_run`)
created datasets correctly per-call (version=N+1, parent_version=prior),
and the central :class:`hub.apps.datasets.versioning.VersionHistoryManager`
flipped prior versions' ``is_current`` to ``False`` — but it did NOT stamp
``archived_at`` on those superseded rows. The 260.7.C.1 task spec called
out the expected behaviour as ``"flip is_current=False + archived_at=now()"``;
production was doing the first half only.

The gap is observable: querying ``Dataset.objects.filter(asset=A, archived_at__isnull=False)``
to enumerate "previous versions" of an asset would return EMPTY for any
asset that had been re-ingested via the scheduled-ingestion pipeline,
even though there ARE archived versions (with ``is_current=False``).
The same query against the standalone ``archive_version()`` method would
work correctly — that's the inconsistency 260.7.C closes.

This file pins three invariants, all driven through the production
:func:`process_file_for_run` entry point (no mocks of business logic;
only the ``S3StorageClient.save_file`` I/O boundary is stubbed, mirroring
the documented stub policy in ``test_worker_services_validation_parity.py``):

1. **Monotonic versions per asset (260.7.C.2)** — Hypothesis property:
   for any 1 ≤ N ≤ 5 sequential runs against the same scheduled
   ingestion, the resulting datasets have versions exactly ``[1..N]``,
   only the latest has ``is_current=True``, and all prior have
   ``is_current=False`` AND ``archived_at IS NOT NULL`` (the load-bearing
   archived_at invariant 260.7.C.1 introduced).

2. **Trigger-twice concrete (260.7.C.3)** — running two runs in
   sequence produces v1 (is_current=False, archived_at != None,
   parent_version=None) and v2 (version=2, is_current=True,
   parent_version=v1). This is the literal task spec.

3. **archived_at is stamped at the moment of supersession (260.7.C.1
   gap fix)** — the prior version's ``archived_at`` is set BY THE BULK
   UPDATE in ``VersionHistoryManager.create_version`` (not later, not
   by a post-save signal, not None until a separate cron runs). This
   pins the production-code fix at its surface contract.
"""
from __future__ import annotations
import pytest

import uuid
from typing import Tuple
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.datasets.models import Dataset
from hub.apps.datasets.versioning import VersionHistoryManager
from hub.apps.files.models import File, FileStatus, FileScanStatus
from hub.apps.scheduled_ingestion.models import (
    ScheduledIngestion,
    ScheduledIngestionRun,
    ScheduledIngestionRunStatus,
    ScheduleType,
    SourceType,
)
from hub.apps.scheduled_ingestion.worker_services import process_file_for_run
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


# ---------------------------------------------------------------------------
# Fixture helpers — same shape as
# ``test_worker_services_validation_parity.py``. Each test seeds its own
# tenant + user + scheduled_ingestion so the property test's per-example
# transaction isolation is preserved.
# ---------------------------------------------------------------------------


def _seed_tenant_user_si() -> Tuple[Tenant, User, ScheduledIngestion]:
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"VerMono-{uid}",
        slug=f"ver-mono-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    user = User.objects.create_user(
        email=f"u-{uid}@example.com",
        password="testpass123",
        tenant=tenant,
        status=UserStatus.ACTIVE,
    )
    si = ScheduledIngestion.objects.create(
        tenant=tenant,
        name=f"VerMono SI {uid}",
        source_type=SourceType.S3,
        source_config={"bucket": "test-bucket", "prefix": "data/"},
        schedule_type=ScheduleType.DAILY,
        schedule_config={"time": "00:00"},
        file_pattern=r".*\.csv",
        auto_create_asset=True,
        created_by=user,
    )
    return tenant, user, si


def _seed_run(si: ScheduledIngestion) -> ScheduledIngestionRun:
    return ScheduledIngestionRun.objects.create(
        scheduled_ingestion=si,
        status=ScheduledIngestionRunStatus.RUNNING,
    )


def _stub_s3_save_file():
    """Stub the S3 storage boundary — the only mock in this suite.

    Mirrors the documented stub policy in
    ``test_worker_services_validation_parity.py:139-151``: the worker's
    ``S3StorageClient.save_file`` writes to S3 / MinIO, which is a true
    I/O boundary (not business logic). Every other side-effect — DB
    writes, business-rules evaluation, signal dispatch (including the
    ``pre_delete`` retire-on-purge handler), audit emission, and the
    versioning bulk-update under test — runs against the real machinery.
    """
    return patch(
        "hub.apps.files.storage.S3StorageClient.save_file",
        return_value="test/storage/path",
    )


def _run_one_ingestion(
    si: ScheduledIngestion,
    user: User,
    csv_content: bytes,
    file_path: str,
) -> str:
    """Drive one scheduled-ingestion run end-to-end and return the
    created dataset id. Each call seeds its own ScheduledIngestionRun
    so the workflow's run-attribution is realistic.
    """
    run = _seed_run(si)
    result = process_file_for_run(
        run_id=str(run.id),
        file_path=file_path,
        file_content=csv_content,
        tenant_id=str(si.tenant_id),
        user_id=str(user.id),
    )
    assert "dataset_id" in result, (
        f"process_file_for_run must return dataset_id; got keys={list(result)!r}"
    )
    return str(result["dataset_id"])


# ---------------------------------------------------------------------------
# 260.7.C.3 — Concrete trigger-twice test (the literal task spec)
# ---------------------------------------------------------------------------


@override_settings(CLAMAV_ENABLED=False)
class TriggerScheduleRunTwiceTest(TestCase):
    """260.7.C.3 — concrete chain: two runs → v1 archived, v2 current."""

    @pytest.mark.integration
    def test_trigger_schedule_run_twice_increments_version_and_archives_prior(self):
        """Two sequential runs → v1.is_current=False + archived_at + v2.version=2 + is_current=True.

        Linear journey across the seam between worker_services and
        VersionHistoryManager. Pins the EXACT contract from the
        260.7.C.1 task spec.
        """
        tenant, user, si = _seed_tenant_user_si()

        with _stub_s3_save_file():
            ds1_id = _run_one_ingestion(
                si, user,
                csv_content=b"id,name\n1,alpha\n2,beta\n",
                file_path="data/run-1.csv",
            )
            ds2_id = _run_one_ingestion(
                si, user,
                csv_content=b"id,name\n3,gamma\n4,delta\n",
                file_path="data/run-2.csv",
            )

        # --- Pin the asset binding: both datasets must hang off the
        # SAME asset (the auto-created one); else the version
        # counter wouldn't share a sequence and the unique
        # constraint ``unique_dataset_version_per_asset`` wouldn't
        # apply to the chain at all. This catches a regression
        # where the worker re-creates the asset per run instead of
        # idempotent-fetch.
        ds1 = Dataset.objects.get(id=ds1_id)
        ds2 = Dataset.objects.get(id=ds2_id)
        self.assertIsNotNone(ds1.asset)
        self.assertIsNotNone(ds2.asset)
        self.assertEqual(ds1.asset_id, ds2.asset_id)

        # --- 260.7.C.1 monotonic version contract.
        self.assertEqual(ds1.version, 1, "first run must produce version=1")
        self.assertEqual(ds2.version, 2, "second run must produce version=N+1=2")

        # --- 260.7.C.1 is_current flip (the half that already worked).
        self.assertFalse(
            ds1.is_current,
            "prior version must be flipped to is_current=False on supersession",
        )
        self.assertTrue(
            ds2.is_current,
            "new version must be is_current=True",
        )

        # --- 260.7.C.1 archived_at stamping (the half that 260.7.C
        # adds — it was a gap in the bulk-update path).
        self.assertIsNotNone(
            ds1.archived_at,
            "prior version MUST have archived_at stamped at supersession "
            "(was a gap pre-260.7.C — bulk update only flipped is_current)",
        )
        self.assertIsNone(
            ds2.archived_at,
            "current version must NOT have archived_at set",
        )

        # --- Version-tree integrity: v2.parent_version → v1.
        self.assertIsNone(ds1.parent_version)
        self.assertEqual(ds2.parent_version_id, ds1.id)

    @pytest.mark.integration
    def test_only_one_is_current_after_two_runs(self):
        """Hard invariant: per (tenant, asset), exactly one row has is_current=True.

        Pins the database-level invariant the bulk-update enforces.
        A regression that omits the bulk update entirely would have
        TWO is_current=True rows — caught here.
        """
        tenant, user, si = _seed_tenant_user_si()

        with _stub_s3_save_file():
            ds1_id = _run_one_ingestion(
                si, user, b"a,b\n1,2\n", "data/r1.csv",
            )
            ds2_id = _run_one_ingestion(
                si, user, b"a,b\n3,4\n", "data/r2.csv",
            )

        asset_id = Dataset.objects.get(id=ds1_id).asset_id
        current_count = Dataset.objects.filter(
            tenant=tenant, asset_id=asset_id, is_current=True,
        ).count()
        self.assertEqual(
            current_count, 1,
            f"exactly one Dataset per (tenant, asset) must have is_current=True; got {current_count}",
        )


# ---------------------------------------------------------------------------
# 260.7.C.2 — Property test: monotonic versions per asset, archived_at
# invariants hold for arbitrary N.
# ---------------------------------------------------------------------------


def _seed_asset(tenant: Tenant, user: User) -> Asset:
    """Create one Asset for the unit-level supersession tests."""
    fid = uuid.uuid4().hex[:8]
    return Asset.objects.create(
        tenant=tenant,
        key=f"vm-asset-{fid}",
        name=f"VM Asset {fid}",
        status=AssetStatus.ACTIVE,
        created_by=user,
    )


def _seed_dataset_for_asset(
    tenant: Tenant,
    user: User,
    asset: Asset,
    *,
    version: int,
    file_name: str,
) -> Dataset:
    """Create a Dataset (and its backing File) attached to an existing
    asset. Used by the unit-level pin to chain v1 → v2 against the
    SAME asset (the unique constraint ``unique_dataset_version_per_asset``
    requires distinct versions per asset; the helper takes ``version``
    explicitly so the caller can sequence them).
    """
    fid = uuid.uuid4().hex[:8]
    file = File.objects.create(
        tenant=tenant,
        name=file_name,
        content_type="text/csv",
        size=128,
        status=FileStatus.ACTIVE,
        scan_status=FileScanStatus.CLEAN,
        storage_path=f"{tenant.id}/{fid}/{file_name}",
        created_by=user,
    )
    return Dataset.objects.create(
        tenant=tenant,
        asset=asset,
        file=file,
        schema_json={"fields": [{"name": "id", "type": "integer"}]},
        sample_data_json=[{"id": version}],
        row_count=1,
        format="CSV",
        version=version,
        created_by=user,
    )


# ---------------------------------------------------------------------------
# R1 audit GAP-D — Unit-level pin: ``VersionHistoryManager.create_version``'s
# bulk-update stamps ``archived_at`` on superseded rows.
#
# The two tests above drive the contract through the WORKER pipeline
# (S3 stub, real DB). This test isolates the bulk-update contract at
# the manager layer — same fix surface, lighter setup, faster
# regression-locality. A future refactor of ``worker_services`` (or
# the introduction of a parallel call site for ``create_version``)
# would exercise the manager but not the worker; this test catches
# that without depending on the worker pipeline at all.
# ---------------------------------------------------------------------------


class VersionHistoryManagerArchivedAtUnitTest(TestCase):
    """260.7.C R1 — direct pin of the bulk-update archived_at contract."""

    @classmethod
    def setUpTestData(cls):
        # One tenant + one user shared across tests in this class —
        # each test seeds its OWN asset/dataset trio via the helper
        # so cross-test isolation is preserved through unique
        # asset_key + file_name.
        uid = uuid.uuid4().hex[:8]
        cls.tenant = Tenant.objects.create(
            name=f"VHM-Unit-{uid}",
            slug=f"vhm-unit-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        cls.user = User.objects.create_user(
            email=f"vhm-{uid}@example.com",
            password="testpass123",
            tenant=cls.tenant,
            status=UserStatus.ACTIVE,
        )

    @pytest.mark.integration
    def test_create_version_supersession_stamps_archived_at(self):
        """create_version(child, ..., is_current=True) stamps archived_at on parent.

        The literal contract from the 260.7.C.1 spec: when a new
        version supersedes a prior one (via the bulk update inside
        create_version), the prior MUST have ``archived_at`` set
        AND ``is_current=False`` — both observables, not just one.
        """
        before_call = timezone.now()
        asset = _seed_asset(self.tenant, self.user)
        parent = _seed_dataset_for_asset(
            self.tenant, self.user, asset, version=1, file_name="parent.csv",
        )
        VersionHistoryManager.create_version(parent, is_current=True)

        # Sanity: parent currently has archived_at NULL (the bulk
        # update at this point has nothing to flip — parent is the
        # only is_current=True row, and the .exclude(id=parent.id)
        # excludes itself).
        parent.refresh_from_db()
        self.assertTrue(parent.is_current)
        self.assertIsNone(
            parent.archived_at,
            "first version's archived_at must remain NULL (no prior to archive)",
        )

        # Create a SECOND version against the SAME asset. The bulk
        # update inside create_version MUST flip parent.is_current=False
        # AND stamp parent.archived_at = now(). This is the gap
        # 260.7.C.1 fixed.
        child = _seed_dataset_for_asset(
            self.tenant, self.user, asset, version=2, file_name="child.csv",
        )

        VersionHistoryManager.create_version(
            child, parent_version=parent, is_current=True,
        )

        parent.refresh_from_db()
        child.refresh_from_db()

        # Pin the is_current half (was already correct pre-260.7.C).
        self.assertFalse(
            parent.is_current,
            "supersession: prior version's is_current MUST be False",
        )
        self.assertTrue(
            child.is_current,
            "supersession: new version's is_current MUST be True",
        )

        # Pin the archived_at half (was the gap 260.7.C.1 closed).
        self.assertIsNotNone(
            parent.archived_at,
            "260.7.C.1 contract: prior version's archived_at MUST be stamped "
            "by the bulk update — was NULL pre-fix",
        )
        # Sanity bound: archived_at is recent (within the test window).
        self.assertGreaterEqual(parent.archived_at, before_call)
        self.assertLessEqual(parent.archived_at, timezone.now())

        # The new version MUST NOT have archived_at set — only
        # superseded versions do.
        self.assertIsNone(
            child.archived_at,
            "current version must NOT have archived_at set",
        )

    @pytest.mark.integration
    def test_create_version_with_is_current_false_does_not_touch_others(self):
        """create_version(..., is_current=False) skips the bulk update entirely.

        Pre-existing path; pin that the 260.7.C.1 fix did NOT
        accidentally trigger the bulk update on the is_current=False
        path (which would flip-and-archive an existing current version
        AND leave NO is_current=True row in the DB).
        """
        asset = _seed_asset(self.tenant, self.user)
        v1 = _seed_dataset_for_asset(
            self.tenant, self.user, asset, version=1, file_name="solo.csv",
        )
        VersionHistoryManager.create_version(v1, is_current=True)

        # Now create v2 with is_current=False. The bulk update is
        # gated on ``if is_current and dataset.asset:`` — must skip.
        v2 = _seed_dataset_for_asset(
            self.tenant, self.user, asset, version=2, file_name="not-current.csv",
        )

        VersionHistoryManager.create_version(
            v2, parent_version=v1, is_current=False,
        )

        v1.refresh_from_db()
        v2.refresh_from_db()

        # v1 untouched: still is_current, no archived_at stamp.
        self.assertTrue(
            v1.is_current,
            "is_current=False on new version must NOT flip the existing current",
        )
        self.assertIsNone(
            v1.archived_at,
            "is_current=False path must NOT stamp archived_at on others",
        )
        # v2 written with is_current=False as requested.
        self.assertFalse(v2.is_current)


@pytest.mark.django_db(transaction=True)
@settings(
    max_examples=4,
    deadline=None,
    # Each example seeds its own tenant + user + scheduled_ingestion —
    # the per-test transaction isolation Hypothesis relies on is
    # provided by ``transaction=True``. Suppress the function-scoped
    # fixture warning because we deliberately want fresh DB state per
    # example (see test body for tenant seeding).
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(n=st.integers(min_value=1, max_value=5))
@pytest.mark.integration
def test_property_versions_monotonic_per_asset(n):
    """Property: for any 1≤N≤5 sequential runs, version=k iff k-th run.

    Three composite invariants verified:

    * ``Dataset.objects.filter(asset=A).order_by("version")`` returns
      datasets with versions ``[1, 2, ..., N]`` (no gaps, no duplicates).
    * Exactly ONE row has ``is_current=True`` — the highest version.
    * All N-1 prior rows have ``is_current=False`` AND
      ``archived_at IS NOT NULL`` (the 260.7.C archived_at invariant).

    A regression that breaks any of the three (e.g. version skips,
    multiple is_current rows, or missing archived_at on prior versions)
    fails this property at one of the N=1..5 examples.
    """
    with override_settings(CLAMAV_ENABLED=False):
        tenant, user, si = _seed_tenant_user_si()

        ds_ids = []
        with _stub_s3_save_file():
            for k in range(1, n + 1):
                ds_id = _run_one_ingestion(
                    si, user,
                    csv_content=f"id,name\n{k},row{k}\n".encode(),
                    file_path=f"data/run-{k}.csv",
                )
                ds_ids.append(ds_id)

        first_ds = Dataset.objects.get(id=ds_ids[0])
        asset_id = first_ds.asset_id
        assert asset_id is not None, "auto-create-asset must seed the asset on run 1"

        ordered = list(
            Dataset.objects.filter(tenant=tenant, asset_id=asset_id)
            .order_by("version")
            .values_list("id", "version", "is_current", "archived_at")
        )

        # Invariant 1: version sequence is exactly [1..n] with no gaps.
        versions = [row[1] for row in ordered]
        assert versions == list(range(1, n + 1)), (
            f"versions for N={n} must be {list(range(1, n+1))!r}, got {versions!r}"
        )

        # Invariant 2: exactly one is_current=True, and it's the LAST.
        currents = [row for row in ordered if row[2]]
        assert len(currents) == 1, (
            f"N={n}: exactly one Dataset must be is_current=True; got {len(currents)}"
        )
        assert currents[0][1] == n, (
            f"N={n}: the is_current row must be version={n}; got version={currents[0][1]}"
        )

        # Invariant 3: every prior version (1..n-1) has archived_at NOT NULL.
        priors = [row for row in ordered if not row[2]]
        assert len(priors) == n - 1, (
            f"N={n}: {n-1} prior versions expected, got {len(priors)}"
        )
        for prior_id, prior_version, _, prior_archived_at in priors:
            assert prior_archived_at is not None, (
                f"N={n}: prior version {prior_version} (id={prior_id}) "
                f"MUST have archived_at stamped (260.7.C invariant)"
            )
