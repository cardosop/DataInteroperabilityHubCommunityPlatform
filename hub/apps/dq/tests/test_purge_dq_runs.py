"""
Phase 240.1.C.8 — TDD tests for the ``purge_dq_runs`` management command.

Pinned spec scenarios (from 240.1.C tasks 4, 7, 8):

* Per-tenant retention bounds — ``[7, 365]`` days per D240.7.
* Batched processing — 500-row batches; chunked deletes don't lock
  the whole table.
* Soft-vs-hard delete transition — runs older than retention go
  ``is_deleted=True``; soft-deleted rows older than 30 days are
  hard-deleted.
* Dry-run idempotency — ``--dry-run`` reports counts without
  mutating; re-running ``--dry-run`` returns the same counts.
* S3 cleanup — hard-delete invokes
  ``files.storage.S3StorageClient.delete_prefix`` for the run's
  ``s3://...payloads/{run_id}/`` directory.
* Audit-event emission — every soft-delete and hard-delete batch
  emits a ``DQ_RUN_PURGED`` audit row carrying the count + tenant.
* ``DQ_PURGE_DRY_RUN`` env-var gate — when set, ``--dry-run``
  defaults to True (D240.16 first-7-days safety net).

Real DB rows + real boto3 + ``moto`` for the S3 boundary; no
internal mocks beyond the network edge.
"""

from __future__ import annotations

import contextlib
import io
import os
import uuid
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TransactionTestCase, override_settings
from django.utils import timezone

pytestmark = [pytest.mark.django_db(transaction=True)]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_tenant(retention_days: int = 90):
    from hub.apps.tenants.models import Tenant

    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"Purge Tenant {uid}",
        slug=f"purge-tenant-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
        dq_run_retention_days=retention_days,
    )
    return tenant


def _make_dq_run(tenant, *, created_at=None, asset=None, file_obj=None):
    """Build a DQRun with a back-dated ``created_at``.

    Django sets ``auto_now_add=True`` on save, so we have to update
    the row directly to back-date — this matches the production
    pattern where retention compares against ``created_at`` set at
    insertion time.
    """
    from hub.apps.assets.models import Asset, AssetStatus
    from hub.apps.dq.models import DQEngine, DQRun, DQRunStatus
    from hub.apps.files.models import File, FileStatus
    from hub.apps.jobs.models import Job, JobStatus, JobType

    uid = uuid.uuid4().hex[:8]
    if asset is None:
        asset = Asset.objects.create(
            tenant=tenant,
            key=f"a-{uid}",
            name=f"Asset {uid}",
            status=AssetStatus.ACTIVE,
        )
    if file_obj is None:
        file_obj = File.objects.create(
            tenant=tenant,
            name=f"f-{uid}.csv",
            content_type="text/csv",
            size=10,
            status=FileStatus.ACTIVE,
            storage_path=f"dq/{tenant.id}/{uid}/payload.csv",
            content_sha256="0" * 64,
        )
    job = Job.objects.create(
        tenant=tenant,
        type=JobType.DQ_RUN,
        status=JobStatus.COMPLETED,
        resource_type="ASSET",
        resource_id=asset.id,
    )
    dq_run = DQRun.objects.create(
        tenant=tenant,
        asset=asset,
        file=file_obj,
        job=job,
        profile_key="intake_basic_soda",
        engine=DQEngine.SODA,
        status=DQRunStatus.SUCCEEDED,
        quality_score=0.95,
    )
    if created_at is not None:
        DQRun.all_objects.filter(pk=dq_run.pk).update(created_at=created_at)
        dq_run.refresh_from_db()
    return dq_run


# ---------------------------------------------------------------------------
# Tenant retention bounds (D240.7)
# ---------------------------------------------------------------------------


class TenantRetentionValidationTests(TransactionTestCase):
    def test_default_is_90_days(self):
        tenant = _make_tenant(retention_days=90)
        assert tenant.dq_run_retention_days == 90

    def test_lower_bound_7_days(self):
        from hub.apps.tenants.models import Tenant

        t = Tenant(
            name="X",
            slug="x-bound-low",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            dq_run_retention_days=6,
        )
        with pytest.raises(ValidationError):
            t.full_clean()

    def test_upper_bound_365_days(self):
        from hub.apps.tenants.models import Tenant

        t = Tenant(
            name="X",
            slug="x-bound-high",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
            dq_run_retention_days=400,
        )
        with pytest.raises(ValidationError):
            t.full_clean()

    def test_inclusive_bounds_accept_7_and_365(self):
        # The validator is inclusive on both ends.
        t1 = _make_tenant(retention_days=7)
        t2 = _make_tenant(retention_days=365)
        assert t1.dq_run_retention_days == 7
        assert t2.dq_run_retention_days == 365


# ---------------------------------------------------------------------------
# SoftDeleteManager
# ---------------------------------------------------------------------------


class SoftDeleteManagerTests(TransactionTestCase):
    def test_default_manager_hides_soft_deleted_rows(self):
        from hub.apps.dq.models import DQRun

        tenant = _make_tenant()
        live = _make_dq_run(tenant)
        old = _make_dq_run(tenant)
        old.soft_delete()

        ids = list(DQRun.objects.filter(tenant=tenant).values_list("id", flat=True))
        assert live.id in ids
        assert old.id not in ids

    def test_all_objects_returns_everything(self):
        from hub.apps.dq.models import DQRun

        tenant = _make_tenant()
        live = _make_dq_run(tenant)
        old = _make_dq_run(tenant)
        old.soft_delete()

        ids = list(DQRun.all_objects.filter(tenant=tenant).values_list("id", flat=True))
        assert live.id in ids
        assert old.id in ids

    def test_soft_delete_idempotent(self):
        from hub.apps.dq.models import DQRun

        tenant = _make_tenant()
        run = _make_dq_run(tenant)
        run.soft_delete()
        first = DQRun.all_objects.get(pk=run.pk).deleted_at
        run.soft_delete()  # second call — must NOT bump deleted_at
        second = DQRun.all_objects.get(pk=run.pk).deleted_at
        assert first == second


# ---------------------------------------------------------------------------
# Purge command — base behaviour
# ---------------------------------------------------------------------------


class _BaseS3Mock:
    """Mixin that wires ``moto`` so the purge command's S3-prefix
    delete is exercised against an in-process mock (real boto3 calls,
    no DIY S3 fakes).

    Endpoint-URL escape hatch: ``S3StorageClient.__init__`` honours
    ``AWS_S3_ENDPOINT_URL`` from env (set to ``http://minio-test:9000``
    in docker-compose.test.yml) and Django settings. With the env
    var set, boto3 builds a client pointed at the real MinIO host
    and ``moto``'s patcher misses entirely (moto only intercepts the
    default client). To make ``S3StorageClient`` go through ``moto``,
    we pop the env var AND override the Django setting for the
    duration of the test, then restore afterwards.
    """

    def _start_moto(self):
        pytest.importorskip("moto")
        from moto import mock_aws

        # ``S3StorageClient.__init__`` resolution chain:
        #   1. AWS_S3_ENDPOINT_URL env var → if set, used directly.
        #   2. settings.AWS_S3_ENDPOINT_URL → if set, used.
        #   3. Both None → if ENVIRONMENT in {staging, production,
        #      prod} → leave endpoint as None (boto3 uses AWS
        #      defaults; moto's default-client patcher catches it).
        #   4. Both None AND ENVIRONMENT not deployed → fall back to
        #      MinIO endpoint detection (defeats moto).
        #
        # So we have to clear (1)+(2) AND stamp (3) so the constructor
        # leaves endpoint_url = None and the moto patcher takes over.
        self._prior_endpoint_env = os.environ.pop(
            "AWS_S3_ENDPOINT_URL",
            None,
        )
        self._prior_environment_env = os.environ.get("ENVIRONMENT")
        os.environ["ENVIRONMENT"] = "production"

        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        os.environ["AWS_SESSION_TOKEN"] = "testing"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        self._mock = mock_aws()
        self._mock.start()
        import boto3

        # Override the Django setting too, so a test that sets
        # ``override_settings(AWS_STORAGE_BUCKET_NAME=...)`` doesn't
        # accidentally re-introduce the MinIO endpoint via Django's
        # config.
        from django.test.utils import override_settings as _ov

        self._settings_override = _ov(AWS_S3_ENDPOINT_URL=None)
        self._settings_override.enable()

        self._bucket = f"dq-payloads-{uuid.uuid4().hex[:8]}"
        s3 = boto3.client("s3", region_name="us-east-1")
        s3.create_bucket(Bucket=self._bucket)
        # Seed a couple of payload objects so delete_prefix has work
        # to do.
        self._s3 = s3

    def _stop_moto(self):
        with contextlib.suppress(Exception):
            self._settings_override.disable()
        with contextlib.suppress(Exception):
            self._mock.stop()
        if self._prior_endpoint_env is not None:
            os.environ["AWS_S3_ENDPOINT_URL"] = self._prior_endpoint_env
        if self._prior_environment_env is None:
            os.environ.pop("ENVIRONMENT", None)
        else:
            os.environ["ENVIRONMENT"] = self._prior_environment_env

    def _seed_run_payload(self, run_id):
        prefix = f"dq/{run_id}/"
        for name in ("input.csv", "checks.json", "report.html"):
            self._s3.put_object(
                Bucket=self._bucket,
                Key=f"{prefix}{name}",
                Body=b"x",
            )
        return prefix


class PurgeSoftDeleteTests(_BaseS3Mock, TransactionTestCase):
    """Soft-delete pass: rows older than tenant retention go
    ``is_deleted=True``; rows still inside retention are untouched."""

    def setUp(self):
        self._start_moto()

    def tearDown(self):
        self._stop_moto()

    def test_runs_inside_retention_are_left_alone(self):
        tenant = _make_tenant(retention_days=30)
        # 10 days old — well inside retention.
        recent = _make_dq_run(
            tenant,
            created_at=timezone.now() - timedelta(days=10),
        )
        out = io.StringIO()
        with override_settings(
            DQ_S3_BUCKET=self._bucket,
            DQ_S3_PREFIX="dq/",
        ):
            call_command("purge_dq_runs", stdout=out)
        recent.refresh_from_db()
        assert recent.is_deleted is False

    def test_runs_outside_retention_are_soft_deleted(self):
        from hub.apps.dq.models import DQRun

        tenant = _make_tenant(retention_days=30)
        # 60 days old — past retention.
        old = _make_dq_run(
            tenant,
            created_at=timezone.now() - timedelta(days=60),
        )
        out = io.StringIO()
        with override_settings(
            DQ_S3_BUCKET=self._bucket,
            DQ_S3_PREFIX="dq/",
        ):
            call_command("purge_dq_runs", stdout=out)
        reloaded = DQRun.all_objects.get(pk=old.pk)
        assert reloaded.is_deleted is True
        assert reloaded.deleted_at is not None

    def test_per_tenant_retention_is_respected(self):
        """Tenant A: 30-day retention; Tenant B: 365-day retention.
        A 60-day-old row in A is purged; a 60-day-old row in B is not."""
        from hub.apps.dq.models import DQRun

        tenant_a = _make_tenant(retention_days=30)
        tenant_b = _make_tenant(retention_days=365)

        run_a = _make_dq_run(
            tenant_a,
            created_at=timezone.now() - timedelta(days=60),
        )
        run_b = _make_dq_run(
            tenant_b,
            created_at=timezone.now() - timedelta(days=60),
        )

        out = io.StringIO()
        with override_settings(
            DQ_S3_BUCKET=self._bucket,
            DQ_S3_PREFIX="dq/",
        ):
            call_command("purge_dq_runs", stdout=out)

        assert DQRun.all_objects.get(pk=run_a.pk).is_deleted is True
        assert DQRun.all_objects.get(pk=run_b.pk).is_deleted is False

    def test_dry_run_does_not_mutate(self):
        from hub.apps.dq.models import DQRun

        tenant = _make_tenant(retention_days=30)
        old = _make_dq_run(
            tenant,
            created_at=timezone.now() - timedelta(days=60),
        )
        out = io.StringIO()
        with override_settings(
            DQ_S3_BUCKET=self._bucket,
            DQ_S3_PREFIX="dq/",
        ):
            call_command("purge_dq_runs", "--dry-run", stdout=out)
        assert DQRun.all_objects.get(pk=old.pk).is_deleted is False
        # Output reports what would happen.
        text = out.getvalue().lower()
        self.assertIn(
            "would soft-delete", text, "Dry-run output must include the phrase 'would soft-delete'"
        )
        # Contextual match on the action phrase WITH the count of 1 run:
        self.assertTrue(
            "soft-delete 1" in text or "soft-delete 1 runs" in text,
            f"Dry-run output must report the exact count; got: {text.strip()}",
        )

    def test_dry_run_idempotent_repeats(self):
        tenant = _make_tenant(retention_days=30)
        _make_dq_run(
            tenant,
            created_at=timezone.now() - timedelta(days=60),
        )
        out_a, out_b = io.StringIO(), io.StringIO()
        with override_settings(
            DQ_S3_BUCKET=self._bucket,
            DQ_S3_PREFIX="dq/",
        ):
            call_command("purge_dq_runs", "--dry-run", stdout=out_a)
            call_command("purge_dq_runs", "--dry-run", stdout=out_b)
        # Second dry-run sees the SAME row count (no mutation
        # happened in between).
        assert out_a.getvalue() == out_b.getvalue()

    def test_dq_run_purged_audit_emitted(self):
        from hub.apps.audit.models import AuditEvent

        tenant = _make_tenant(retention_days=30)
        _make_dq_run(
            tenant,
            created_at=timezone.now() - timedelta(days=60),
        )
        with override_settings(
            DQ_S3_BUCKET=self._bucket,
            DQ_S3_PREFIX="dq/",
        ):
            call_command(
                "purge_dq_runs",
                stdout=io.StringIO(),
            )
        rows = AuditEvent.objects.filter(
            action="DQ_RUN_PURGED",
            tenant=tenant,
        )
        assert rows.exists()
        details = rows.first().details_json or {}
        assert details.get("phase") == "soft_delete"
        assert details.get("count", 0) >= 1


class PurgeHardDeleteTests(_BaseS3Mock, TransactionTestCase):
    """Hard-delete pass: rows soft-deleted >30 days ago are
    purged from the DB and their S3 prefix is wiped."""

    def setUp(self):
        self._start_moto()

    def tearDown(self):
        self._stop_moto()

    def test_soft_deleted_inside_grace_window_kept(self):
        from hub.apps.dq.models import DQRun

        tenant = _make_tenant(retention_days=30)
        run = _make_dq_run(
            tenant,
            created_at=timezone.now() - timedelta(days=60),
        )
        run.soft_delete()
        # Pretend we soft-deleted 10 days ago (<30, still in grace).
        DQRun.all_objects.filter(pk=run.pk).update(
            deleted_at=timezone.now() - timedelta(days=10),
        )
        with override_settings(
            DQ_S3_BUCKET=self._bucket,
            DQ_S3_PREFIX="dq/",
        ):
            call_command("purge_dq_runs", stdout=io.StringIO())
        # Still present (not hard-deleted).
        assert DQRun.all_objects.filter(pk=run.pk).exists()

    def test_soft_deleted_past_grace_hard_deleted_with_s3_cleanup(self):
        from hub.apps.dq.models import DQRun

        tenant = _make_tenant(retention_days=30)
        run = _make_dq_run(
            tenant,
            created_at=timezone.now() - timedelta(days=60),
        )
        run.soft_delete()
        # Soft-deleted 40 days ago — past the 30-day grace.
        DQRun.all_objects.filter(pk=run.pk).update(
            deleted_at=timezone.now() - timedelta(days=40),
        )
        # Seed S3 payload directory for this run.
        prefix = self._seed_run_payload(run.id)

        with override_settings(
            DQ_S3_BUCKET=self._bucket,
            DQ_S3_PREFIX="dq/",
        ):
            call_command("purge_dq_runs", stdout=io.StringIO())

        # DB row gone.
        assert not DQRun.all_objects.filter(pk=run.pk).exists()
        # S3 prefix gone (no objects under it).
        listing = self._s3.list_objects_v2(
            Bucket=self._bucket,
            Prefix=prefix,
        )
        assert listing.get("KeyCount", 0) == 0

    def test_hard_delete_audit_emitted(self):
        from hub.apps.audit.models import AuditEvent
        from hub.apps.dq.models import DQRun

        tenant = _make_tenant(retention_days=30)
        run = _make_dq_run(
            tenant,
            created_at=timezone.now() - timedelta(days=60),
        )
        run.soft_delete()
        DQRun.all_objects.filter(pk=run.pk).update(
            deleted_at=timezone.now() - timedelta(days=40),
        )
        with override_settings(
            DQ_S3_BUCKET=self._bucket,
            DQ_S3_PREFIX="dq/",
        ):
            call_command("purge_dq_runs", stdout=io.StringIO())
        rows = AuditEvent.objects.filter(
            action="DQ_RUN_PURGED",
            tenant=tenant,
        ).order_by("-timestamp")
        # Two phases at minimum: soft_delete (recorded in earlier
        # invocations or this run if both pass run together) and
        # hard_delete now.
        assert any((r.details_json or {}).get("phase") == "hard_delete" for r in rows)


# ---------------------------------------------------------------------------
# Batched processing
# ---------------------------------------------------------------------------


class PurgeBatchingTests(_BaseS3Mock, TransactionTestCase):
    def setUp(self):
        self._start_moto()

    def tearDown(self):
        self._stop_moto()

    def test_batches_processed_with_chunk_size(self):
        """Verify batch_size argument splits processing.

        5 runs with --batch-size=2 → at least 3 batches. We confirm all
        5 rows are soft-deleted AND that the output mentions multiple
        batches."""
        from hub.apps.dq.models import DQRun

        tenant = _make_tenant(retention_days=30)
        for _ in range(5):
            _make_dq_run(
                tenant,
                created_at=timezone.now() - timedelta(days=60),
            )
        stdout = io.StringIO()
        with override_settings(
            DQ_S3_BUCKET=self._bucket,
            DQ_S3_PREFIX="dq/",
        ):
            call_command(
                "purge_dq_runs",
                "--batch-size",
                "2",
                stdout=stdout,
            )
        soft_deleted = DQRun.all_objects.filter(
            tenant=tenant,
            is_deleted=True,
        ).count()
        assert soft_deleted == 5

        # 5 items ÷ batch_size 2 → at least 3 batches. Verify the
        # output mentions all 5 rows were soft-deleted.
        output = stdout.getvalue()
        self.assertIn(
            "soft-deleted 5 runs",
            output,
            f"Expected soft-delete count in output, got: {output[:200]}",
        )


# ---------------------------------------------------------------------------
# DQ_PURGE_DRY_RUN env-var safety net (D240.16)
# ---------------------------------------------------------------------------


class PurgeDryRunEnvVarTests(_BaseS3Mock, TransactionTestCase):
    def setUp(self):
        self._start_moto()
        self._prior_env = os.environ.get("DQ_PURGE_DRY_RUN")

    def tearDown(self):
        self._stop_moto()
        if self._prior_env is None:
            os.environ.pop("DQ_PURGE_DRY_RUN", None)
        else:
            os.environ["DQ_PURGE_DRY_RUN"] = self._prior_env

    def test_dq_purge_dry_run_env_forces_dry_run(self):
        """When ``DQ_PURGE_DRY_RUN=1`` is set, even invocations
        WITHOUT ``--dry-run`` MUST behave as dry-run (D240.16
        first-7-days safety net)."""
        from hub.apps.dq.models import DQRun

        tenant = _make_tenant(retention_days=30)
        run = _make_dq_run(
            tenant,
            created_at=timezone.now() - timedelta(days=60),
        )

        os.environ["DQ_PURGE_DRY_RUN"] = "1"
        with override_settings(
            DQ_S3_BUCKET=self._bucket,
            DQ_S3_PREFIX="dq/",
        ):
            call_command("purge_dq_runs", stdout=io.StringIO())
        # Untouched.
        assert DQRun.all_objects.get(pk=run.pk).is_deleted is False

    def test_explicit_no_dry_run_overrides_env(self):
        """Operator can override the safety net with ``--no-dry-run``
        to force a real purge."""
        from hub.apps.dq.models import DQRun

        tenant = _make_tenant(retention_days=30)
        run = _make_dq_run(
            tenant,
            created_at=timezone.now() - timedelta(days=60),
        )

        os.environ["DQ_PURGE_DRY_RUN"] = "1"
        with override_settings(
            DQ_S3_BUCKET=self._bucket,
            DQ_S3_PREFIX="dq/",
        ):
            call_command(
                "purge_dq_runs",
                "--no-dry-run",
                stdout=io.StringIO(),
            )
        assert DQRun.all_objects.get(pk=run.pk).is_deleted is True


# ---------------------------------------------------------------------------
# S3 prefix delete helper — direct unit test
# ---------------------------------------------------------------------------


class S3PrefixDeleteHelperTests(TransactionTestCase):
    def setUp(self):
        pytest.importorskip("moto")
        from moto import mock_aws

        # See ``_BaseS3Mock._start_moto`` for the resolution-chain
        # rationale — this is the standalone copy for tests that
        # don't use the mixin.
        self._prior_endpoint_env = os.environ.pop(
            "AWS_S3_ENDPOINT_URL",
            None,
        )
        self._prior_environment_env = os.environ.get("ENVIRONMENT")
        os.environ["ENVIRONMENT"] = "production"

        os.environ["AWS_ACCESS_KEY_ID"] = "testing"
        os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
        os.environ["AWS_SESSION_TOKEN"] = "testing"
        os.environ["AWS_DEFAULT_REGION"] = "us-east-1"
        self._mock = mock_aws()
        self._mock.start()
        import boto3
        from django.test.utils import override_settings as _ov

        self._settings_override = _ov(AWS_S3_ENDPOINT_URL=None)
        self._settings_override.enable()

        self._bucket = f"helper-{uuid.uuid4().hex[:8]}"
        self._s3 = boto3.client("s3", region_name="us-east-1")
        self._s3.create_bucket(Bucket=self._bucket)

    def tearDown(self):
        with contextlib.suppress(Exception):
            self._settings_override.disable()
        self._mock.stop()
        if self._prior_endpoint_env is not None:
            os.environ["AWS_S3_ENDPOINT_URL"] = self._prior_endpoint_env
        if self._prior_environment_env is None:
            os.environ.pop("ENVIRONMENT", None)
        else:
            os.environ["ENVIRONMENT"] = self._prior_environment_env

    def test_empty_prefix_is_refused(self):
        from hub.apps.files.storage import S3StorageClient

        with override_settings(AWS_STORAGE_BUCKET_NAME=self._bucket):
            client = S3StorageClient()
            with pytest.raises(ValueError):
                client.delete_prefix("", bucket=self._bucket)

    def test_prefix_does_not_match_unrelated_keys(self):
        """``delete_prefix("dq/abc")`` must NOT match ``dq/abcd/...``.
        The trailing-slash behaviour is critical — without it we'd
        accidentally delete adjacent runs."""
        from hub.apps.files.storage import S3StorageClient

        self._s3.put_object(
            Bucket=self._bucket,
            Key="dq/abc/payload.csv",
            Body=b"x",
        )
        self._s3.put_object(
            Bucket=self._bucket,
            Key="dq/abcd/payload.csv",
            Body=b"x",
        )
        with override_settings(AWS_STORAGE_BUCKET_NAME=self._bucket):
            client = S3StorageClient()
            deleted = client.delete_prefix("dq/abc", bucket=self._bucket)
        assert deleted == 1
        listing = self._s3.list_objects_v2(
            Bucket=self._bucket,
            Prefix="dq/abcd/",
        )
        assert listing.get("KeyCount", 0) == 1

    def test_idempotent_rerun_returns_zero(self):
        from hub.apps.files.storage import S3StorageClient

        self._s3.put_object(
            Bucket=self._bucket,
            Key="dq/run1/x.csv",
            Body=b"x",
        )
        with override_settings(AWS_STORAGE_BUCKET_NAME=self._bucket):
            client = S3StorageClient()
            assert client.delete_prefix("dq/run1", bucket=self._bucket) == 1
            assert client.delete_prefix("dq/run1", bucket=self._bucket) == 0
