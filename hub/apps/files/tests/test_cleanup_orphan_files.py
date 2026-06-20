"""
Phase 260.1.E — one-time / scheduled orphan-file cleanup (pre-260 refcount gap).

Real DB, Redis lock, FileService soft-delete (no mocks). Orphan = no in-tenant
row in Dataset, ComplianceRun, DQRun, RetentionPolicy, or AccessRequest pointing
at the file; status not DELETING/DELETED; created_at past --min-age-days.
"""

from __future__ import annotations

import os
import uuid
from datetime import timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.utils import timezone

from hub.apps.api.middleware.idempotency_utils import get_redis_client
from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.tests.test_base import FilesTestBase
from hub.apps.governance.models import RetentionPolicy, RetentionPolicyType

pytestmark = pytest.mark.django_db(transaction=True)


from hub.apps.files.tests.test_base import redis_or_skip as _redis_or_skip


class CleanupOrphanFilesCommandTests(FilesTestBase):
    def setUp(self):
        super().setUp()
        _redis_or_skip()

    def _old_orphan(self, *, name: str | None = None) -> File:
        fn = name or f"orphan-{uuid.uuid4().hex[:8]}.csv"
        fid = uuid.uuid4()
        f = File.objects.create(
            id=fid,
            tenant=self.tenant,
            name=fn,
            content_type="text/csv",
            size=10,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/{fid}/{fn}",
            created_by=self.user,
        )
        old = timezone.now() - timedelta(days=60)
        File.objects.filter(pk=f.pk).update(created_at=old)
        f.refresh_from_db()
        return f

    @pytest.mark.integration
    def test_soft_deletes_orphan_past_min_age(self):
        f = self._old_orphan()
        out = StringIO()
        call_command(
            "cleanup_orphan_files",
            "--no-dry-run",
            "--tenant-id",
            str(self.tenant.id),
            "--min-age-days",
            "7",
            stdout=out,
        )
        # Phase 260.1.C: delete_file soft-deletes → DELETING (not DELETED).
        # Hard-delete runs later via purge_deleted_files cron after grace window.
        f.refresh_from_db()
        self.assertEqual(f.status, FileStatus.DELETING)
        self.assertIsNotNone(f.deleted_at)

    @pytest.mark.integration
    def test_skips_when_dataset_references_file(self):
        f = self._old_orphan()
        Dataset.objects.create(
            tenant=self.tenant,
            file=f,
            format="CSV",
            schema_json={},
            sample_data_json=[],
            row_count=0,
            created_by=self.user,
        )
        call_command(
            "cleanup_orphan_files",
            "--no-dry-run",
            "--tenant-id",
            str(self.tenant.id),
            "--min-age-days",
            "7",
            stdout=StringIO(),
        )
        f.refresh_from_db()
        self.assertEqual(f.status, FileStatus.ACTIVE)

    @pytest.mark.integration
    def test_respects_min_age(self):
        f = self._old_orphan()
        File.objects.filter(pk=f.pk).update(created_at=timezone.now() - timedelta(days=3))
        call_command(
            "cleanup_orphan_files",
            "--no-dry-run",
            "--tenant-id",
            str(self.tenant.id),
            "--min-age-days",
            "30",
            stdout=StringIO(),
        )
        f.refresh_from_db()
        self.assertEqual(f.status, FileStatus.ACTIVE)

    @pytest.mark.integration
    def test_env_dry_run_requires_no_mutation(self):
        f = self._old_orphan()
        os.environ["FILE_ORPHAN_CLEANUP_DRY_RUN"] = "1"
        try:
            call_command(
                "cleanup_orphan_files",
                "--tenant-id",
                str(self.tenant.id),
                "--min-age-days",
                "7",
                stdout=StringIO(),
            )
        finally:
            del os.environ["FILE_ORPHAN_CLEANUP_DRY_RUN"]
        f.refresh_from_db()
        self.assertEqual(f.status, FileStatus.ACTIVE)

    @pytest.mark.integration
    def test_override_env_with_no_dry_run(self):
        f = self._old_orphan()
        os.environ["FILE_ORPHAN_CLEANUP_DRY_RUN"] = "1"
        try:
            call_command(
                "cleanup_orphan_files",
                "--no-dry-run",
                "--tenant-id",
                str(self.tenant.id),
                "--min-age-days",
                "7",
                stdout=StringIO(),
            )
        finally:
            del os.environ["FILE_ORPHAN_CLEANUP_DRY_RUN"]
        f.refresh_from_db()
        self.assertEqual(f.status, FileStatus.DELETING)

    @pytest.mark.integration
    def test_emits_audit_per_batch(self):
        self._old_orphan(name="o1.csv")
        self._old_orphan(name="o2.csv")
        self._old_orphan(name="o3.csv")
        prior = AuditEvent.objects.filter(
            action=audit_event_types.FILE_ORPHAN_CLEANUP_COMPLETED,
            tenant=self.tenant,
        ).count()
        call_command(
            "cleanup_orphan_files",
            "--dry-run",
            "--tenant-id",
            str(self.tenant.id),
            "--min-age-days",
            "7",
            "--batch-size",
            "2",
            stdout=StringIO(),
        )
        after = AuditEvent.objects.filter(
            action=audit_event_types.FILE_ORPHAN_CLEANUP_COMPLETED,
            tenant=self.tenant,
        ).count()
        self.assertEqual(after - prior, 2)

    @pytest.mark.integration
    def test_no_dry_run_overrides_cli_dry_run(self):
        """Explicit --no-dry-run must win over --dry-run (destructive soak exit)."""
        f = self._old_orphan()
        call_command(
            "cleanup_orphan_files",
            "--dry-run",
            "--no-dry-run",
            "--tenant-id",
            str(self.tenant.id),
            "--min-age-days",
            "7",
            stdout=StringIO(),
        )
        f.refresh_from_db()
        self.assertEqual(f.status, FileStatus.DELETING)

    @pytest.mark.integration
    def test_skips_when_retention_policy_references_file(self):
        f = self._old_orphan()
        RetentionPolicy.objects.create(
            tenant=self.tenant,
            name="keep-file-policy",
            policy_type=RetentionPolicyType.EVENT_BASED,
            event_trigger="contract_expired",
            file=f,
            created_by=self.user,
        )
        call_command(
            "cleanup_orphan_files",
            "--no-dry-run",
            "--tenant-id",
            str(self.tenant.id),
            "--min-age-days",
            "7",
            stdout=StringIO(),
        )
        f.refresh_from_db()
        self.assertEqual(f.status, FileStatus.ACTIVE)

    @pytest.mark.integration
    def test_non_dry_run_multibatch_drains_all_orphans(self):
        o1 = self._old_orphan(name="m1.csv")
        o2 = self._old_orphan(name="m2.csv")
        o3 = self._old_orphan(name="m3.csv")
        call_command(
            "cleanup_orphan_files",
            "--no-dry-run",
            "--tenant-id",
            str(self.tenant.id),
            "--min-age-days",
            "7",
            "--batch-size",
            "2",
            stdout=StringIO(),
        )
        for o in (o1, o2, o3):
            o.refresh_from_db()
            self.assertEqual(o.status, FileStatus.DELETING, msg=f"{o.name}")
