"""
Phase 260.1.A.7–A.8 — file hard-purge command, retention eligibility, tenant grace.

Uses real Redis (distributed lock), DB, and optional S3/MinIO. Skips purge tests
when Redis is unreachable (same pattern as idempotency tests).
"""

from __future__ import annotations

import os
import uuid
from datetime import timedelta
from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.utils import timezone
from hypothesis import given, settings
from hypothesis import strategies as st

from hub.apps.api.middleware.idempotency_utils import get_redis_client
from hub.apps.audit.models import AuditEvent
from hub.apps.files.file_retention import file_is_purge_eligible
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.tests.test_base import FilesTestBase

pytestmark = pytest.mark.django_db(transaction=True)


from hub.apps.files.tests.test_base import redis_or_skip as _redis_or_skip


class TenantFileGraceBoundsTests(FilesTestBase):
    """260.1.A.2 — tenant.file_soft_delete_grace_days validators."""

    @pytest.mark.integration
    def test_grace_below_minimum_rejected(self):
        self.tenant.file_soft_delete_grace_days = 6
        with self.assertRaises(ValidationError):
            self.tenant.full_clean()

    @pytest.mark.integration
    def test_grace_above_maximum_rejected(self):
        self.tenant.file_soft_delete_grace_days = 366
        with self.assertRaises(ValidationError):
            self.tenant.full_clean()


class PurgeDeletedFilesCommandTests(FilesTestBase):
    """260.1.A.1 / A.7 — management command (lock + batches + audit)."""

    def setUp(self):
        super().setUp()
        _redis_or_skip()

    @pytest.mark.integration
    def test_dry_run_is_idempotent_for_counts(self):
        old = timezone.now() - timedelta(days=60)
        for _ in range(3):
            File.objects.create(
                tenant=self.tenant,
                name=f"gone-{uuid.uuid4().hex[:6]}.csv",
                content_type="text/csv",
                size=10,
                status=FileStatus.DELETING,
                scan_status=FileScanStatus.CLEAN,
                storage_path=f"{self.tenant.id}/purge-{uuid.uuid4().hex[:6]}.csv",
                deleted_at=old,
                created_by=self.user,
            )
        out1 = StringIO()
        out2 = StringIO()
        call_command(
            "purge_deleted_files",
            "--dry-run",
            "--tenant-id",
            str(self.tenant.id),
            stdout=out1,
        )
        call_command(
            "purge_deleted_files",
            "--dry-run",
            "--tenant-id",
            str(self.tenant.id),
            stdout=out2,
        )
        self.assertIn("would purge 3 file(s)", out1.getvalue())
        self.assertIn("would purge 3 file(s)", out2.getvalue())
        # ``FilesTestBase.setUp`` already owns one ACTIVE ``test.csv``
        # before this test seeds the 3 DELETING rows. The contract
        # the assertion is pinning is "dry-run touched zero rows" —
        # scope the count to the DELETING fixtures so the parent's
        # ACTIVE file doesn't drift the expected total.
        self.assertEqual(
            File.objects.filter(tenant=self.tenant, status=FileStatus.DELETING).count(),
            3,
        )

    @pytest.mark.integration
    def test_hard_purge_deletes_row_and_writes_file_purged_audit(self):
        from hub.apps.audit import event_types as audit_event_types

        self.tenant.file_soft_delete_grace_days = 7
        self.tenant.save(update_fields=["file_soft_delete_grace_days"])

        old = timezone.now() - timedelta(days=30)
        f = File.objects.create(
            tenant=self.tenant,
            name="hard-purge-me.csv",
            content_type="text/csv",
            size=42,
            status=FileStatus.DELETING,
            scan_status=FileScanStatus.CLEAN,
            content_sha256="a" * 64,
            storage_path=f"{self.tenant.id}/hard-purge-me.csv",
            deleted_at=old,
            created_by=self.user,
        )
        fid = f.id
        prev = os.environ.pop("FILE_PURGE_DRY_RUN_REQUIRED", None)
        try:
            out = StringIO()
            call_command(
                "purge_deleted_files",
                "--no-dry-run",
                "--tenant-id",
                str(self.tenant.id),
                stdout=out,
            )
        finally:
            if prev is not None:
                os.environ["FILE_PURGE_DRY_RUN_REQUIRED"] = prev

        self.assertIn("purged 1 file(s)", out.getvalue())
        self.assertFalse(File.objects.filter(pk=fid).exists())
        ev = AuditEvent.objects.filter(
            action=audit_event_types.FILE_PURGED,
            resource_id=str(fid),
        ).first()
        self.assertIsNotNone(ev)
        self.assertEqual(ev.details_json.get("name"), "hard-purge-me.csv")
        self.assertEqual(ev.details_json.get("size"), 42)
        self.assertEqual(ev.details_json.get("tenant_id"), str(self.tenant.id))
        self.assertIn("timestamp", ev.details_json)

    @pytest.mark.integration
    def test_env_file_purge_dry_run_required_forces_dry_run(self):
        old = timezone.now() - timedelta(days=60)
        File.objects.create(
            tenant=self.tenant,
            name="env-guard.csv",
            content_type="text/csv",
            size=1,
            status=FileStatus.DELETING,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/env-guard.csv",
            deleted_at=old,
            created_by=self.user,
        )
        os.environ["FILE_PURGE_DRY_RUN_REQUIRED"] = "true"
        try:
            out = StringIO()
            call_command(
                "purge_deleted_files",
                "--tenant-id",
                str(self.tenant.id),
                stdout=out,
            )
            self.assertIn("would purge", out.getvalue())
            self.assertEqual(File.objects.filter(name="env-guard.csv").count(), 1)
        finally:
            del os.environ["FILE_PURGE_DRY_RUN_REQUIRED"]

    @pytest.mark.integration
    def test_purge_processes_more_than_one_batch_per_tenant(self):
        """260.1.A.7 — batched inner loop drains all eligible rows in one run."""
        old = timezone.now() - timedelta(days=60)
        for i in range(6):
            File.objects.create(
                tenant=self.tenant,
                name=f"batch-{i}.csv",
                content_type="text/csv",
                size=1,
                status=FileStatus.DELETING,
                scan_status=FileScanStatus.CLEAN,
                storage_path=f"{self.tenant.id}/batch-{i}.csv",
                deleted_at=old,
                created_by=self.user,
            )
        prev = os.environ.pop("FILE_PURGE_DRY_RUN_REQUIRED", None)
        try:
            out = StringIO()
            call_command(
                "purge_deleted_files",
                "--no-dry-run",
                "--tenant-id",
                str(self.tenant.id),
                "--batch-size",
                "2",
                stdout=out,
            )
        finally:
            if prev is not None:
                os.environ["FILE_PURGE_DRY_RUN_REQUIRED"] = prev

        self.assertIn("purged 6 file(s)", out.getvalue())
        self.assertEqual(
            File.objects.filter(tenant=self.tenant, status=FileStatus.DELETING).count(),
            0,
        )

    @pytest.mark.integration
    def test_hard_purge_removes_object_from_storage_when_available(self):
        """260.1.A.7 — hard purge calls storage delete (real MinIO/S3 when up)."""
        from django.core.files.base import ContentFile

        from hub.apps.files.storage import S3StorageClient

        try:
            storage = S3StorageClient()
            storage._ensure_bucket_exists()
        except Exception as exc:  # pragma: no cover
            import unittest

            raise unittest.SkipTest(f"Storage not available: {exc}") from exc

        file_id = uuid.uuid4()
        body = b"purge-storage-test"
        storage_path = storage.save_file(
            tenant_id=str(self.tenant.id),
            file_id=str(file_id),
            file_content=ContentFile(body),
            file_name="stored-then-purge.csv",
        )
        self.assertTrue(storage.file_exists(storage_path))

        old = timezone.now() - timedelta(days=60)
        f = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="stored-then-purge.csv",
            content_type="text/csv",
            size=len(body),
            status=FileStatus.DELETING,
            scan_status=FileScanStatus.CLEAN,
            storage_path=storage_path,
            deleted_at=old,
            created_by=self.user,
        )
        fid = f.id
        prev = os.environ.pop("FILE_PURGE_DRY_RUN_REQUIRED", None)
        try:
            out = StringIO()
            call_command(
                "purge_deleted_files",
                "--no-dry-run",
                "--tenant-id",
                str(self.tenant.id),
                stdout=out,
            )
        finally:
            if prev is not None:
                os.environ["FILE_PURGE_DRY_RUN_REQUIRED"] = prev

        self.assertIn("purged 1 file(s)", out.getvalue())
        self.assertFalse(File.objects.filter(pk=fid).exists())
        self.assertFalse(storage.file_exists(storage_path))

    @pytest.mark.integration
    def test_service_soft_delete_then_purge_hard_delete(self):
        """260.1.A.7 — ACTIVE → delete_file (DELETING); backdated grace; purge removes row."""
        file_id = uuid.uuid4()
        f = File.objects.create(
            id=file_id,
            tenant=self.tenant,
            name="lifecycle.csv",
            content_type="text/csv",
            size=100,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/{file_id}/lifecycle.csv",
            created_by=self.user,
        )
        self.service.delete_file(
            file_id=str(f.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        f.refresh_from_db()
        self.assertEqual(f.status, FileStatus.DELETING)
        self.assertIsNotNone(f.deleted_at)

        File.objects.filter(pk=f.pk).update(deleted_at=timezone.now() - timedelta(days=60))

        prev = os.environ.pop("FILE_PURGE_DRY_RUN_REQUIRED", None)
        try:
            out = StringIO()
            call_command(
                "purge_deleted_files",
                "--no-dry-run",
                "--tenant-id",
                str(self.tenant.id),
                stdout=out,
            )
        finally:
            if prev is not None:
                os.environ["FILE_PURGE_DRY_RUN_REQUIRED"] = prev

        self.assertIn("purged 1 file(s)", out.getvalue())
        self.assertFalse(File.objects.filter(pk=file_id).exists())


@pytest.mark.django_db
@settings(max_examples=60)
@given(
    grace=st.integers(min_value=7, max_value=365),
    days_since_delete=st.integers(min_value=0, max_value=2000),
)
@pytest.mark.integration
def test_hypothesis_eligibility_matches_age_against_grace_deleting(
    grace,
    days_since_delete,
):
    """Phase 260.1.A.8 — property: eligible iff age >= grace for DELETING."""
    now = timezone.now()
    deleted_at = now - timedelta(days=days_since_delete)
    expected = days_since_delete >= grace
    assert (
        file_is_purge_eligible(
            status=FileStatus.DELETING,
            deleted_at=deleted_at,
            grace_days=grace,
            now=now,
        )
        is expected
    )


@pytest.mark.django_db
@settings(max_examples=30)
@given(
    grace=st.integers(min_value=7, max_value=365),
    days_since_delete=st.integers(min_value=100, max_value=2000),
)
@pytest.mark.integration
def test_hypothesis_active_status_never_eligible(grace, days_since_delete):
    now = timezone.now()
    deleted_at = now - timedelta(days=days_since_delete)
    assert not file_is_purge_eligible(
        status=FileStatus.ACTIVE,
        deleted_at=deleted_at,
        grace_days=grace,
        now=now,
    )
