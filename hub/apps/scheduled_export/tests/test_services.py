"""
Unit tests for ScheduledExportService.

Covers process_export_item, create/update/delete_scheduled_export,
create_export_run, update_export_run with success, failure, edge cases,
and error handling. No mocks - real DB and services.
"""

import uuid

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.audit.models import AuditEvent
from hub.apps.core.services.base import NotFoundError, ValidationError
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.scheduled_export.models import (
    DestinationType,
    ScheduledExport,
    ScheduledExportRunStatus,
    ScheduledExportStatus,
)
from hub.apps.scheduled_export.services import ScheduledExportService
from hub.apps.tenants.models import KYCStatus, PlanTier, Tenant, TenantPlan, TenantStatus
from hub.apps.users.models import User, UserStatus

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.timeout(600),
]


def _create_plan_with_export_limits(name=None, slug=None):
    """Create a tenant plan with scheduled export limits for tests. Use unique name/slug to avoid UniqueViolation with --reuse-db."""
    unique = uuid.uuid4().hex[:8]
    plan_name = name or f"Test Export Plan {unique}"
    plan_slug = slug or f"test-export-plan-{unique}"
    return TenantPlan.objects.create(
        name=plan_name,
        slug=plan_slug,
        tier=PlanTier.FREE,
        limits_json={
            "max_scheduled_exports": 20,
            "max_export_runs_per_month": 100,
        },
        is_active=True,
    )


class ScheduledExportServiceCRUDTest(TestCase):
    """Tests for create_scheduled_export, update_scheduled_export, delete_scheduled_export."""

    def setUp(self):
        unique_id = uuid.uuid4().hex[:8]
        self.plan = _create_plan_with_export_limits()
        self.tenant = Tenant.objects.create(
            name=f"Services CRUD Tenant {unique_id}",
            slug=f"services-crud-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
            plan=self.plan,
        )
        self.user = User.objects.create_user(
            email=f"services-crud-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{unique_id}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        self.service = ScheduledExportService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_create_scheduled_export_success(self):
        """Service create_scheduled_export returns created export and emits audit."""
        export = self.service.create_scheduled_export(
            tenant=self.tenant,
            created_by=self.user,
            name="Daily Export",
            destination_type=DestinationType.S3,
            destination_config={"bucket": "test-bucket", "prefix": "exports/"},
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"asset_ids": [str(self.asset.id)]},
        )
        self.assertEqual(export.name, "Daily Export")
        self.assertEqual(export.status, ScheduledExportStatus.ACTIVE)
        self.assertIsNotNone(export.next_run_at)
        self.assertEqual(
            AuditEvent.objects.filter(
                resource_type="SCHEDULED_EXPORT", action="CREATED", resource_id=str(export.id)
            ).count(),
            1,
        )

    def test_create_scheduled_export_validation_error_business_rules(self):
        """Service create_scheduled_export raises ValidationError when business rules fail."""
        with self.assertRaises(ValidationError) as cm:
            self.service.create_scheduled_export(
                tenant=self.tenant,
                created_by=self.user,
                name="Bad Export",
                destination_type=DestinationType.S3,
                destination_config={},  # Missing bucket
                schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
                source_scope={"asset_ids": [str(self.asset.id)]},
            )
        self.assertEqual(cm.exception.code, "BUSINESS_RULES_VALIDATION")

    def test_update_scheduled_export_success(self):
        """Service update_scheduled_export updates fields and emits audit."""
        export = self.service.create_scheduled_export(
            tenant=self.tenant,
            created_by=self.user,
            name="Original",
            destination_type=DestinationType.S3,
            destination_config={"bucket": "b1"},
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"asset_ids": [str(self.asset.id)]},
        )
        updated = self.service.update_scheduled_export(
            scheduled_export_id=str(export.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Updated Name",
            status=ScheduledExportStatus.PAUSED,
        )
        self.assertEqual(updated.name, "Updated Name")
        self.assertEqual(updated.status, ScheduledExportStatus.PAUSED)
        self.assertEqual(
            AuditEvent.objects.filter(
                resource_type="SCHEDULED_EXPORT", action="UPDATED", resource_id=str(export.id)
            ).count(),
            1,
        )

    def test_update_scheduled_export_not_found(self):
        """Service update_scheduled_export raises NotFoundError for non-existent id."""
        fake_id = str(uuid.uuid4())
        with self.assertRaises(NotFoundError):
            self.service.update_scheduled_export(
                scheduled_export_id=fake_id,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Any",
            )

    def test_update_scheduled_export_tenant_required(self):
        """Service update_scheduled_export raises ValidationError when tenant_id is missing."""
        export = self.service.create_scheduled_export(
            tenant=self.tenant,
            created_by=self.user,
            name="Export",
            destination_type=DestinationType.S3,
            destination_config={"bucket": "b1"},
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"asset_ids": [str(self.asset.id)]},
        )
        service_no_tenant = ScheduledExportService(user_id=str(self.user.id))
        with self.assertRaises(ValidationError) as cm:
            service_no_tenant.update_scheduled_export(
                scheduled_export_id=str(export.id),
                name="Updated",
            )
        self.assertEqual(cm.exception.code, "TENANT_REQUIRED")

    def test_delete_scheduled_export_success(self):
        """Service delete_scheduled_export removes export and emits audit."""
        export = self.service.create_scheduled_export(
            tenant=self.tenant,
            created_by=self.user,
            name="To Delete",
            destination_type=DestinationType.S3,
            destination_config={"bucket": "b1"},
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"asset_ids": [str(self.asset.id)]},
        )
        self.service.delete_scheduled_export(
            scheduled_export_id=str(export.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        self.assertFalse(ScheduledExport.objects.filter(id=export.id).exists())
        self.assertEqual(
            AuditEvent.objects.filter(
                resource_type="SCHEDULED_EXPORT", action="DELETED", resource_id=str(export.id)
            ).count(),
            1,
        )

    def test_delete_scheduled_export_not_found(self):
        """Service delete_scheduled_export raises NotFoundError for non-existent id."""
        with self.assertRaises(NotFoundError):
            self.service.delete_scheduled_export(
                scheduled_export_id=str(uuid.uuid4()),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )


class ScheduledExportServiceRunLifecycleTest(TestCase):
    """Tests for create_export_run and update_export_run."""

    def setUp(self):
        unique_id = uuid.uuid4().hex[:8]
        self.plan = _create_plan_with_export_limits()
        self.tenant = Tenant.objects.create(
            name=f"Run Lifecycle Tenant {unique_id}",
            slug=f"run-lifecycle-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
            plan=self.plan,
        )
        self.user = User.objects.create_user(
            email=f"run-lifecycle-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{unique_id}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        self.service = ScheduledExportService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.export = self.service.create_scheduled_export(
            tenant=self.tenant,
            created_by=self.user,
            name="Run Test Export",
            destination_type=DestinationType.S3,
            destination_config={"bucket": "test-bucket"},
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"asset_ids": [str(self.asset.id)]},
        )

    def test_create_export_run_success(self):
        """create_export_run creates run with RUNNING status."""
        run = self.service.create_export_run(
            scheduled_export_id=str(self.export.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            prefect_flow_run_id="pf-123",
        )
        self.assertEqual(run.status, ScheduledExportRunStatus.RUNNING)
        self.assertEqual(run.prefect_flow_run_id, "pf-123")

    def test_create_export_run_idempotency_prefect_flow_run_id(self):
        """Same prefect_flow_run_id returns existing run."""
        run1 = self.service.create_export_run(
            scheduled_export_id=str(self.export.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            prefect_flow_run_id="pf-idem",
        )
        run2 = self.service.create_export_run(
            scheduled_export_id=str(self.export.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            prefect_flow_run_id="pf-idem",
        )
        self.assertEqual(run1.id, run2.id)

    def test_create_export_run_tenant_required(self):
        """create_export_run raises ValidationError when tenant_id is missing."""
        service_no_tenant = ScheduledExportService(user_id=str(self.user.id))
        with self.assertRaises(ValidationError) as cm:
            service_no_tenant.create_export_run(
                scheduled_export_id=str(self.export.id),
            )
        self.assertEqual(cm.exception.code, "TENANT_REQUIRED")

    def test_create_export_run_not_found(self):
        """create_export_run raises NotFoundError for non-existent scheduled_export_id."""
        with self.assertRaises(NotFoundError):
            self.service.create_export_run(
                scheduled_export_id=str(uuid.uuid4()),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
            )

    def test_update_export_run_success(self):
        """update_export_run updates status and counts."""
        run = self.service.create_export_run(
            scheduled_export_id=str(self.export.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        updated = self.service.update_export_run(
            run_id=str(run.id),
            tenant_id=str(self.tenant.id),
            status=ScheduledExportRunStatus.COMPLETED,
            items_found=10,
            items_exported=8,
            items_failed=2,
            completed_at=timezone.now().isoformat(),
        )
        self.assertEqual(updated.status, ScheduledExportRunStatus.COMPLETED)
        self.assertEqual(updated.items_found, 10)
        self.assertEqual(updated.items_exported, 8)
        self.assertEqual(updated.items_failed, 2)
        self.assertIsNotNone(updated.completed_at)

    def test_update_export_run_not_found(self):
        """update_export_run raises NotFoundError for non-existent run_id."""
        with self.assertRaises(NotFoundError):
            self.service.update_export_run(
                run_id=str(uuid.uuid4()),
                tenant_id=str(self.tenant.id),
                status=ScheduledExportRunStatus.COMPLETED,
            )


class ScheduledExportServiceProcessExportItemTest(TestCase):
    """Tests for process_export_item: success, validation, not found, scope, destination types."""

    def setUp(self):
        unique_id = uuid.uuid4().hex[:8]
        self.plan = _create_plan_with_export_limits()
        self.tenant = Tenant.objects.create(
            name=f"Process Item Tenant {unique_id}",
            slug=f"process-item-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
            plan=self.plan,
        )
        self.user = User.objects.create_user(
            email=f"process-item-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key=f"test-asset-{unique_id}",
            name="Test Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )
        self.file = File.objects.create(
            tenant=self.tenant,
            name="test-file.csv",
            size=1024,
            content_type="text/csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )
        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            file=self.file,
            format="CSV",
            schema_json={"columns": ["id", "name"]},
            created_by=self.user,
        )
        self.service = ScheduledExportService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.export = self.service.create_scheduled_export(
            tenant=self.tenant,
            created_by=self.user,
            name="Process Item Export",
            destination_type=DestinationType.S3,
            destination_config={"bucket": "process-bucket", "prefix": "out/"},
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={
                "dataset_ids": [str(self.dataset.id)],
                "file_ids": [str(self.file.id)],
            },
        )
        self.run = self.service.create_export_run(
            scheduled_export_id=str(self.export.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

    def test_process_export_item_dataset_success(self):
        """process_export_item with dataset_id returns upload instructions."""
        result = self.service.process_export_item(
            run_id=str(self.run.id),
            dataset_id=str(self.dataset.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["item_type"], "dataset")
        self.assertEqual(result["item_id"], str(self.dataset.id))
        self.assertIn("upload_url", result)
        self.assertIn("upload_method", result)
        self.assertIn("s3://process-bucket/", result["upload_url"])

    def test_process_export_item_file_success(self):
        """process_export_item with file_id returns upload instructions."""
        result = self.service.process_export_item(
            run_id=str(self.run.id),
            file_id=str(self.file.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["item_type"], "file")
        self.assertEqual(result["item_id"], str(self.file.id))
        self.assertIn("upload_url", result)

    def test_process_export_item_tenant_required(self):
        """process_export_item raises ValidationError when tenant_id is missing."""
        service_no_tenant = ScheduledExportService(user_id=str(self.user.id))
        with self.assertRaises(ValidationError) as cm:
            service_no_tenant.process_export_item(
                run_id=str(self.run.id),
                dataset_id=str(self.dataset.id),
            )
        self.assertEqual(cm.exception.code, "TENANT_REQUIRED")

    def test_process_export_item_run_not_found(self):
        """process_export_item raises NotFoundError for non-existent run_id."""
        with self.assertRaises(NotFoundError):
            self.service.process_export_item(
                run_id=str(uuid.uuid4()),
                dataset_id=str(self.dataset.id),
                tenant_id=str(self.tenant.id),
            )

    def test_process_export_item_item_required(self):
        """process_export_item raises ValidationError when neither dataset_id nor file_id provided."""
        with self.assertRaises(ValidationError) as cm:
            self.service.process_export_item(
                run_id=str(self.run.id),
                tenant_id=str(self.tenant.id),
            )
        self.assertEqual(cm.exception.code, "ITEM_REQUIRED")

    def test_process_export_item_multiple_items_rejected(self):
        """process_export_item raises ValidationError when both dataset_id and file_id provided."""
        with self.assertRaises(ValidationError) as cm:
            self.service.process_export_item(
                run_id=str(self.run.id),
                dataset_id=str(self.dataset.id),
                file_id=str(self.file.id),
                tenant_id=str(self.tenant.id),
            )
        self.assertEqual(cm.exception.code, "MULTIPLE_ITEMS")

    def test_process_export_item_export_not_active(self):
        """process_export_item raises ValidationError when scheduled export is not ACTIVE."""
        self.service.update_scheduled_export(
            scheduled_export_id=str(self.export.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            status=ScheduledExportStatus.PAUSED,
        )
        with self.assertRaises(ValidationError) as cm:
            self.service.process_export_item(
                run_id=str(self.run.id),
                dataset_id=str(self.dataset.id),
                tenant_id=str(self.tenant.id),
            )
        self.assertEqual(cm.exception.code, "EXPORT_NOT_ACTIVE")

    def test_process_export_item_item_not_in_scope(self):
        """process_export_item raises ValidationError when item is not in source_scope."""
        other_file = File.objects.create(
            tenant=self.tenant,
            name="other.csv",
            size=100,
            content_type="text/csv",
            status=FileStatus.ACTIVE,
            created_by=self.user,
        )
        with self.assertRaises(ValidationError) as cm:
            self.service.process_export_item(
                run_id=str(self.run.id),
                file_id=str(other_file.id),
                tenant_id=str(self.tenant.id),
            )
        self.assertEqual(cm.exception.code, "ITEM_NOT_IN_SCOPE")

    def test_process_export_item_dataset_not_found(self):
        """process_export_item raises NotFoundError when dataset_id does not exist."""
        with self.assertRaises(NotFoundError):
            self.service.process_export_item(
                run_id=str(self.run.id),
                dataset_id=str(uuid.uuid4()),
                tenant_id=str(self.tenant.id),
            )

    def test_process_export_item_file_not_found(self):
        """process_export_item raises NotFoundError when file_id does not exist."""
        with self.assertRaises(NotFoundError):
            self.service.process_export_item(
                run_id=str(self.run.id),
                file_id=str(uuid.uuid4()),
                tenant_id=str(self.tenant.id),
            )

    def test_process_export_item_destination_gcs(self):
        """process_export_item returns gs:// URL for GCS destination."""
        gcs_export = self.service.create_scheduled_export(
            tenant=self.tenant,
            created_by=self.user,
            name="GCS Export",
            destination_type=DestinationType.GCS,
            destination_config={"bucket": "gcs-bucket", "prefix": "gcs/"},
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"file_ids": [str(self.file.id)]},
        )
        gcs_run = self.service.create_export_run(
            scheduled_export_id=str(gcs_export.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        result = self.service.process_export_item(
            run_id=str(gcs_run.id),
            file_id=str(self.file.id),
            tenant_id=str(self.tenant.id),
        )
        self.assertIn("gs://gcs-bucket/", result["upload_url"])

    def test_process_export_item_destination_azure_blob(self):
        """process_export_item returns Azure Blob URL for AZURE_BLOB destination."""
        azure_export = self.service.create_scheduled_export(
            tenant=self.tenant,
            created_by=self.user,
            name="Azure Export",
            destination_type=DestinationType.AZURE_BLOB,
            destination_config={
                "container": "azure-container",
                "account_name": "myaccount",
                "prefix": "azure/",
            },
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"file_ids": [str(self.file.id)]},
        )
        azure_run = self.service.create_export_run(
            scheduled_export_id=str(azure_export.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )
        result = self.service.process_export_item(
            run_id=str(azure_run.id),
            file_id=str(self.file.id),
            tenant_id=str(self.tenant.id),
        )
        self.assertIn("blob.core.windows.net", result["upload_url"])
        self.assertIn("azure-container", result["upload_url"])
