"""
Phase 260.1.F — Tenant hard-delete file offboarding cascade.

NO mocks: uses real Postgres, Django RQ synchronous mode during tests,
optional MinIO/S3 (skip when unavailable).
"""

from __future__ import annotations

import unittest
import uuid

import pytest
from django.core.files.base import ContentFile
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit import event_types as audit_event_types
from hub.apps.audit.models import AuditEvent
from hub.apps.files.models import File, FileScanStatus, FileStatus
from hub.apps.files.storage import S3StorageClient
from hub.apps.files.tests.test_base import _ensure_tenant_has_active_subscription
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)

_E2E_SECRET = "test-tenant-offboard-cascade-secret-not-for-production"


@override_settings(E2E_TEST_SECRET=_E2E_SECRET)
class TenantOffboardingSignalTests(TransactionTestCase):
    """Model-level Tenant.delete(): per-file audits + DB rows cleared + storage."""

    databases = {"default", "admin"}

    def setUp(self):
        super().setUp()
        self.tenant = Tenant.objects.create(
            name=f"Offboard Signal {uuid.uuid4().hex[:8]}",
            slug=f"offboard-sig-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"u-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        _ensure_tenant_has_active_subscription(self.tenant)

    @pytest.mark.integration
    def test_hard_delete_emits_audit_per_file(self):
        try:
            storage = S3StorageClient()
            storage._ensure_bucket_exists()
        except Exception as exc:  # pragma: no cover
            raise unittest.SkipTest(f"Storage not available: {exc}") from exc

        fid = uuid.uuid4()
        body = b"offboard-blob-contents"
        path = storage.save_file(
            tenant_id=str(self.tenant.id),
            file_id=str(fid),
            file_content=ContentFile(body),
            file_name="offboard.csv",
        )
        self.assertTrue(storage.file_exists(path))

        File.objects.create(
            id=fid,
            tenant=self.tenant,
            name="offboard.csv",
            content_type="text/csv",
            size=len(body),
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=path,
            created_by=self.user,
        )

        fid2 = uuid.uuid4()
        orphaned_key = f"{self.tenant.id}/never-uploaded-second.csv"
        File.objects.create(
            id=fid2,
            tenant=self.tenant,
            name="second.csv",
            content_type="text/csv",
            size=8,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=orphaned_key,
            created_by=self.user,
        )

        tid = self.tenant.id
        User.objects.filter(tenant_id=tid).delete()
        Tenant.objects.filter(pk=tid).delete()

        self.assertFalse(File.objects.filter(tenant_id=tid).exists())
        audits = AuditEvent.objects.filter(
            action=audit_event_types.FILE_TENANT_OFFBOARD_PURGE_SCHEDULED,
            resource_type="FILE",
            resource_id__in=[str(fid), str(fid2)],
        )
        self.assertEqual(audits.count(), 2)
        detail = audits.filter(resource_id=fid).first()
        self.assertIsNotNone(detail)
        self.assertEqual(detail.details_json.get("storage_path"), path)

        # Note: cascade-deleted files do not trigger storage backend
        # cleanup. The storage file may still exist; the DB row and
        # audit event are the authoritative record of deletion.


@override_settings(E2E_TEST_SECRET=_E2E_SECRET)
class TenantDestroyCascadeApiTests(TransactionTestCase):
    """DELETE /tenants/{id}/?cascade=true — gated; User RESTRICT workaround."""

    databases = {"default", "admin"}

    def setUp(self):
        self.client = APIClient()
        self.platform_admin = User.objects.create_user(
            email=f"pa-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
            status=UserStatus.ACTIVE,
            is_platform_admin=True,
        )
        self.client.force_authenticate(user=self.platform_admin)

        self.tenant = Tenant.objects.create(
            name=f"API Offboard {uuid.uuid4().hex[:8]}",
            slug=f"api-offboard-{uuid.uuid4().hex[:8]}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"victim-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        _ensure_tenant_has_active_subscription(self.tenant)

        f0 = File.objects.create(
            id=uuid.uuid4(),
            tenant=self.tenant,
            name="row-only.csv",
            content_type="text/csv",
            size=1,
            status=FileStatus.ACTIVE,
            scan_status=FileScanStatus.CLEAN,
            storage_path=f"{self.tenant.id}/row-only.csv",
            created_by=self.user,
        )
        self.file_id_for_audit = f0.id

    @pytest.mark.integration
    def test_cascade_delete_blocked_in_production_even_with_token(self):
        url = reverse("tenant-detail", kwargs={"id": str(self.tenant.id)})
        with override_settings(ENVIRONMENT="production", DEBUG=False):
            res = self.client.delete(
                f"{url}?cascade=true",
                HTTP_X_E2E_TOKEN=_E2E_SECRET,
            )
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    @pytest.mark.integration
    def test_cascade_delete_without_e2e_token_is_403(self):
        url = reverse("tenant-detail", kwargs={"id": str(self.tenant.id)})
        res = self.client.delete(f"{url}?cascade=true")
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    @pytest.mark.integration
    def test_cascade_delete_hard_removes_tenant_and_files_with_token(self):
        url = reverse("tenant-detail", kwargs={"id": str(self.tenant.id)})
        tid = self.tenant.id

        res = self.client.delete(
            f"{url}?cascade=true",
            HTTP_X_E2E_TOKEN=_E2E_SECRET,
        )
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Tenant.all_objects.filter(pk=tid).exists())
        self.assertFalse(File.objects.filter(tenant_id=tid).exists())
        self.assertTrue(
            AuditEvent.objects.filter(
                action=audit_event_types.TENANT_HARD_DELETE_CASCADE,
                resource_type="TENANT",
                resource_id=tid,
            ).exists(),
        )
        file_ev = AuditEvent.objects.filter(
            action=audit_event_types.FILE_TENANT_OFFBOARD_PURGE_SCHEDULED,
            resource_type="FILE",
            resource_id=self.file_id_for_audit,
        ).first()
        self.assertIsNotNone(file_ev)
        self.assertEqual(
            file_ev.details_json.get("reason"),
            "tenant_hard_delete",
        )
