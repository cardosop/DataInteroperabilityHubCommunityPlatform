"""
Phase 260.1.G.1 / G.2 — GDPR file hard-delete management commands.

Uses real Redis, PostgreSQL, S3 client (best-effort delete), and ORM. No mocks.
"""
from __future__ import annotations
import pytest

import uuid
from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError

from hub.apps.api.middleware.idempotency_utils import get_redis_client
from hub.apps.audit.models import AuditEvent
from hub.apps.audit.utils import create_audit_event
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.tests.test_base import FilesTestBase
from hub.apps.gdpr.audit_erasure import GDPR_AUDIT_USER_ID_REDACTED

pytestmark = pytest.mark.django_db(transaction=True)


def _redis_or_skip() -> None:
    try:
        get_redis_client().ping()
    except Exception as exc:  # pragma: no cover
        import unittest

        raise unittest.SkipTest(f"Redis required: {exc}") from exc


class GdprDeleteFilesCommandsTests(FilesTestBase):
    def setUp(self):
        super().setUp()
        _redis_or_skip()

    @pytest.mark.integration
    def test_delete_files_for_user_purges_and_scrubs_audit_actor(self):
        fid = uuid.uuid4()
        user_file = File.objects.create(
            id=fid,
            tenant=self.tenant,
            name="gdpr-user-file.csv",
            content_type="text/csv",
            size=12,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/{fid}/gdpr-user-file.csv",
            created_by=self.user,
        )
        rid = uuid.uuid4()
        create_audit_event(
            resource_type="FILE",
            action="FILE_UPLOADED",
            actor_user=self.user,
            tenant=self.tenant,
            resource_id=rid,
            details={
                "actor_user_id": str(self.user.id),
                "user_email": self.user.email,
            },
        )

        call_command(
            "delete_files_for_user",
            "--user-id",
            str(self.user.id),
            stdout=StringIO(),
        )

        self.assertFalse(File.objects.filter(pk=user_file.pk).exists())
        ev = AuditEvent.all_objects.filter(resource_id=rid).first()
        self.assertIsNotNone(ev)
        self.assertIsNone(ev.actor_user_id)
        self.assertEqual(ev.details_json.get("actor_user_id"), GDPR_AUDIT_USER_ID_REDACTED)
        self.assertEqual(ev.details_json.get("user_email"), "deleted@deleted.local")

    @pytest.mark.integration
    def test_delete_files_for_user_dry_run_does_not_delete(self):
        fid = uuid.uuid4()
        user_file = File.objects.create(
            id=fid,
            tenant=self.tenant,
            name="stay.csv",
            content_type="text/csv",
            size=1,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/{fid}/stay.csv",
            created_by=self.user,
        )
        call_command(
            "delete_files_for_user",
            "--user-id",
            str(self.user.id),
            "--dry-run",
            stdout=StringIO(),
        )
        self.assertTrue(File.objects.filter(pk=user_file.pk).exists())

    @pytest.mark.integration
    def test_delete_files_for_user_rejects_bad_uuid(self):
        with self.assertRaises(CommandError):
            call_command(
                "delete_files_for_user",
                "--user-id",
                "not-a-uuid",
                stdout=StringIO(),
            )

    @pytest.mark.integration
    def test_delete_files_for_tenant_removes_all_tenant_files(self):
        fid = uuid.uuid4()
        f = File.objects.create(
            id=fid,
            tenant=self.tenant,
            name="tenant-wide.csv",
            content_type="text/csv",
            size=2,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/{fid}/tenant-wide.csv",
            created_by=self.user,
        )
        call_command(
            "delete_files_for_tenant",
            "--tenant-id",
            str(self.tenant.id),
            stdout=StringIO(),
        )
        self.assertFalse(File.objects.filter(pk=f.pk).exists())
