"""
Phase 260.1.D — abandoned multipart sweep (management command).

Uses live Redis for the cluster lock (same expectation as purge tests), DB, and optional
real S3/MinIO multipart APIs (no mocks).
"""

from __future__ import annotations
import pytest
import pytest

import uuid
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError

from hub.apps.api.middleware.idempotency_utils import get_redis_client
from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.storage import S3StorageClient
from hub.apps.files.tests.test_base import FilesTestBase


pytestmark = pytest.mark.django_db(transaction=True)


def _redis_or_skip() -> None:
    try:
        get_redis_client().ping()
    except Exception as exc:  # pragma: no cover — environment-dependent
        import unittest

        raise unittest.SkipTest(f"Redis required: {exc}") from exc


def _multipart_live(storage: S3StorageClient, *, key: str, upload_id: str) -> bool:
    return any(
        rec["key"] == key and rec["upload_id"] == upload_id
        for rec in storage.iter_multipart_uploads()
    )


class CleanupAbandonedMultipartUploadsTests(FilesTestBase):
    """260.1.D — real multipart + Redis + destructive command."""

    def setUp(self):
        super().setUp()
        _redis_or_skip()
        self.storage_available = False
        try:
            self.storage = S3StorageClient()
            self.storage._ensure_bucket_exists()
            self.storage_available = True
        except Exception:
            self.storage_available = False

    @pytest.mark.integration
    def test_dry_run_leaves_uploading_row_and_keeps_pending_multipart(self):
        """Dry-run observes stale rows without touching S3 or File status."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        fid = uuid.uuid4()
        path = f"{self.tenant.id}/{fid}/dry.csv"

        fo = File.objects.create(
            id=fid,
            tenant=self.tenant,
            name="dry.csv",
            content_type="text/csv",
            size=200 * 1024 * 1024,
            scan_status=FileScanStatus.PENDING_SCAN,
            storage_path=path,
            status=FileStatus.UPLOADING,
            created_by=self.user,
            metadata_json={},
        )

        uid = self.storage.initiate_multipart_upload(key=path, content_type="text/csv")
        fo.metadata_json["multipart_upload_id"] = uid
        fo.save(update_fields=["metadata_json"])

        stdout = StringIO()
        call_command(
            "cleanup_abandoned_multipart_uploads",
            dry_run=True,
            min_age_hours=0,
            tenant_id=str(self.tenant.id),
            stdout=stdout,
        )

        fo.refresh_from_db()
        self.assertEqual(fo.status, FileStatus.UPLOADING)
        self.assertTrue(_multipart_live(self.storage, key=path, upload_id=uid))
        self.assertFalse(
            AuditEvent.objects.filter(
                action=audit_event_types.FILE_MULTIPART_ABANDONED,
                resource_id=str(fo.pk),
            ).exists(),
        )

        self.storage.abort_multipart_upload(key=path, upload_id=uid)

    @pytest.mark.integration
    def test_negative_min_age_hours_rejected(self):
        """Invalid CLI args fail fast before Redis/storage work."""
        from io import StringIO

        with self.assertRaises(CommandError):
            call_command(
                "cleanup_abandoned_multipart_uploads",
                min_age_hours=-1,
                stderr=StringIO(),
            )

    @pytest.mark.integration
    def test_cleanup_aborts_stale_multipart_flips_uploading_audit(self):
        """Non–dry-run: abort S3 session, correlate File.UPLOADING, emit audit."""
        if not self.storage_available:
            self.skipTest("S3/MinIO storage not available")

        fid = uuid.uuid4()
        path = f"{self.tenant.id}/{fid}/stale.csv"

        fo = File.objects.create(
            id=fid,
            tenant=self.tenant,
            name="stale.csv",
            content_type="text/csv",
            size=200 * 1024 * 1024,
            scan_status=FileScanStatus.PENDING_SCAN,
            storage_path=path,
            status=FileStatus.UPLOADING,
            created_by=self.user,
            metadata_json={},
        )

        uid = self.storage.initiate_multipart_upload(key=path, content_type="text/csv")
        fo.metadata_json["multipart_upload_id"] = uid
        fo.save(update_fields=["metadata_json"])

        self.assertTrue(_multipart_live(self.storage, key=path, upload_id=uid))

        call_command(
            "cleanup_abandoned_multipart_uploads",
            dry_run=False,
            min_age_hours=0,
            tenant_id=str(self.tenant.id),
        )

        fo.refresh_from_db()
        self.assertEqual(fo.status, FileStatus.DELETED)
        self.assertIsNotNone(fo.deleted_at)
        qs = AuditEvent.objects.filter(
            action=audit_event_types.FILE_MULTIPART_ABANDONED,
            resource_id=str(fo.pk),
        )
        self.assertEqual(qs.count(), 1)

        payload = qs.get().details_json
        self.assertEqual(payload["upload_id"], uid)
        self.assertEqual(payload["storage_path"], path)
        self.assertEqual(payload["abandon_source"], "s3_list_before_cutoff")

        self.assertFalse(_multipart_live(self.storage, key=path, upload_id=uid))
