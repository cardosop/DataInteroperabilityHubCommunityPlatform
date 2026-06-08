"""
Tests for ScheduledExportService and ScheduledExportBusinessRules.

Comprehensive tests with real DB, no mocks.
"""

import uuid
from decimal import Decimal

import pytest
from django.test import TestCase
from django.utils import timezone
from rest_framework import status

from hub.apps.assets.models import Asset
from hub.apps.audit.models import AuditEvent
from hub.apps.contracts.models import Contract
from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File, FileStatus
from hub.apps.scheduled_export.business_rules import ScheduledExportBusinessRules
from hub.apps.scheduled_export.models import (
    DestinationType,
    ScheduledExport,
    ScheduledExportRun,
    ScheduledExportRunStatus,
    ScheduledExportStatus,
)
from hub.apps.scheduled_export.services import ScheduledExportService
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import User, UserStatus

pytestmark = [
    pytest.mark.django_db,
    pytest.mark.timeout(600),
]


class ScheduledExportServiceTest(TestCase):
    """Tests for ScheduledExportService create/update methods."""

    def setUp(self):
        unique_id = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Service Test Tenant {unique_id}",
            slug=f"service-test-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"service-test-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.service = ScheduledExportService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_create_scheduled_export_success(self):
        """Test successful creation of scheduled export via service."""
        # Create an asset for the source_scope
        asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            created_by=self.user,
        )
        export = self.service.create_scheduled_export(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Export",
            destination_type=DestinationType.S3,
            destination_config={"bucket": "test-bucket"},
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"asset_ids": [str(asset.id)]},
        )

        self.assertIsNotNone(export.id)
        self.assertEqual(export.name, "Test Export")
        self.assertEqual(export.destination_type, DestinationType.S3)
        self.assertEqual(export.status, ScheduledExportStatus.ACTIVE)
        self.assertIsNotNone(export.next_run_at)

        # Verify audit event was created
        audit_events = AuditEvent.objects.filter(
            resource_type="SCHEDULED_EXPORT",
            action="CREATED",
            resource_id=str(export.id),
        )
        self.assertEqual(audit_events.count(), 1)

    def test_create_scheduled_export_business_rules_validation(self):
        """Test that business rules validation is applied during creation."""
        # Create an asset for the source_scope
        asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            created_by=self.user,
        )
        # Invalid destination config (missing bucket)
        from hub.apps.core.services.base import ValidationError

        with self.assertRaises(ValidationError) as cm:
            self.service.create_scheduled_export(
                tenant=self.tenant,
                created_by=self.user,
                name="Test Export",
                destination_type=DestinationType.S3,
                destination_config={},  # Missing bucket
                schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
                source_scope={"asset_ids": [str(asset.id)]},
            )
        # Check that it's a business rules validation error
        self.assertEqual(cm.exception.code, "BUSINESS_RULES_VALIDATION")

    def test_update_scheduled_export_success(self):
        """Test successful update of scheduled export via service."""
        # Create an asset for the source_scope
        asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            created_by=self.user,
        )
        # Create export
        export = self.service.create_scheduled_export(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Export",
            destination_type=DestinationType.S3,
            destination_config={"bucket": "test-bucket"},
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"asset_ids": [str(asset.id)]},
        )

        # Update export
        updated_export = self.service.update_scheduled_export(
            scheduled_export_id=str(export.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Updated Export Name",
            status=ScheduledExportStatus.PAUSED,
        )

        self.assertEqual(updated_export.name, "Updated Export Name")
        self.assertEqual(updated_export.status, ScheduledExportStatus.PAUSED)

        # Verify audit event was created
        audit_events = AuditEvent.objects.filter(
            resource_type="SCHEDULED_EXPORT",
            action="UPDATED",
            resource_id=str(export.id),
        )
        self.assertEqual(audit_events.count(), 1)

    def test_update_scheduled_export_schedule_recalculates_next_run_at(self):
        """Test that updating schedule_config recalculates next_run_at."""
        # Create an asset for the source_scope
        asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            created_by=self.user,
        )
        # Create export
        export = self.service.create_scheduled_export(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Export",
            destination_type=DestinationType.S3,
            destination_config={"bucket": "test-bucket"},
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"asset_ids": [str(asset.id)]},
        )

        original_next_run_at = export.next_run_at
        self.assertIsNotNone(original_next_run_at)

        # Update schedule with a different cron
        updated_export = self.service.update_scheduled_export(
            scheduled_export_id=str(export.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            schedule_config={
                "cron": "0 2 * * *",
                "timezone": "UTC",
            },  # Different hour (2 AM instead of midnight)
        )

        # Verify schedule_config was updated
        self.assertEqual(updated_export.schedule_config["cron"], "0 2 * * *")
        updated_export.refresh_from_db()
        # next_run_at must exist and be recalculated (at hour=2)
        self.assertIsNotNone(updated_export.next_run_at)
        self.assertEqual(
            updated_export.next_run_at.hour, 2,
            f"next_run_at should be at 02:00 UTC per new cron, "
            f"got {updated_export.next_run_at}",
        )
        # Must differ from original (which was midnight cron)
        self.assertNotEqual(
            updated_export.next_run_at, original_next_run_at,
            "next_run_at should change when schedule changes",
        )

    def test_create_export_run_success(self):
        """Test successful creation of export run via service."""
        # Create an asset for the source_scope
        asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            created_by=self.user,
        )
        export = self.service.create_scheduled_export(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Export",
            destination_type=DestinationType.S3,
            destination_config={"bucket": "test-bucket"},
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"asset_ids": [str(asset.id)]},
        )

        run = self.service.create_export_run(
            scheduled_export_id=str(export.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            prefect_flow_run_id="prefect-123",
        )

        self.assertIsNotNone(run.id)
        self.assertEqual(run.status, ScheduledExportRunStatus.RUNNING)
        self.assertEqual(run.prefect_flow_run_id, "prefect-123")

    def test_create_export_run_idempotency_prefect_flow_run_id(self):
        """Test idempotency by prefect_flow_run_id."""
        # Create an asset for the source_scope
        asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            created_by=self.user,
        )
        export = self.service.create_scheduled_export(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Export",
            destination_type=DestinationType.S3,
            destination_config={"bucket": "test-bucket"},
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"asset_ids": [str(asset.id)]},
        )

        # Create first run
        run1 = self.service.create_export_run(
            scheduled_export_id=str(export.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            prefect_flow_run_id="prefect-123",
        )

        # Create second run with same prefect_flow_run_id (should return existing)
        run2 = self.service.create_export_run(
            scheduled_export_id=str(export.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            prefect_flow_run_id="prefect-123",
        )

        self.assertEqual(run1.id, run2.id)

    def test_update_export_run_success(self):
        """Test successful update of export run via service."""
        # Create an asset for the source_scope
        asset = Asset.objects.create(
            tenant=self.tenant,
            name="Test Asset",
            created_by=self.user,
        )
        export = self.service.create_scheduled_export(
            tenant=self.tenant,
            created_by=self.user,
            name="Test Export",
            destination_type=DestinationType.S3,
            destination_config={"bucket": "test-bucket"},
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"asset_ids": [str(asset.id)]},
        )

        run = self.service.create_export_run(
            scheduled_export_id=str(export.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
        )

        # Update run
        updated_run = self.service.update_export_run(
            run_id=str(run.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            status=ScheduledExportRunStatus.COMPLETED,
            items_found=10,
            items_exported=8,
            items_failed=2,
            completed_at=timezone.now().isoformat(),
        )

        self.assertEqual(updated_run.status, ScheduledExportRunStatus.COMPLETED)
        self.assertEqual(updated_run.items_found, 10)
        self.assertEqual(updated_run.items_exported, 8)
        self.assertEqual(updated_run.items_failed, 2)
        self.assertIsNotNone(updated_run.completed_at)


class ScheduledExportBusinessRulesTest(TestCase):
    """Tests for ScheduledExportBusinessRules validation."""

    def setUp(self):
        unique_id = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Rules Test Tenant {unique_id}",
            slug=f"rules-test-tenant-{unique_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.UNVERIFIED,
        )
        self.user = User.objects.create_user(
            email=f"rules-test-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.rules = ScheduledExportBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_validate_destination_format_limits_success(self):
        """Test validation of format limits."""
        export = ScheduledExport(
            tenant=self.tenant,
            name="Test Export",
            destination_type=DestinationType.S3,
            destination_config={
                "bucket": "test-bucket",
                "format_limits": {"allowed_formats": ["CSV", "JSON"]},
            },
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"asset_ids": []},
        )

        result = self.rules.validate(
            scheduled_export=export,
            tenant=self.tenant,
            user=self.user,
            validation_type="destination",
        )

        self.assertTrue(result.is_valid)

    def test_validate_destination_format_limits_invalid_format(self):
        """Test validation fails for invalid format."""
        export = ScheduledExport(
            tenant=self.tenant,
            name="Test Export",
            destination_type=DestinationType.S3,
            destination_config={
                "bucket": "test-bucket",
                "format_limits": {"allowed_formats": ["INVALID_FORMAT"]},
            },
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"asset_ids": []},
        )

        result = self.rules.validate(
            scheduled_export=export,
            tenant=self.tenant,
            user=self.user,
            validation_type="destination",
        )

        # Should have warnings but still be valid (warnings don't fail validation)
        self.assertTrue(result.is_valid)
        self.assertTrue(len(result.warnings) > 0)

    def test_validate_destination_size_limits_success(self):
        """Test validation of size limits."""
        export = ScheduledExport(
            tenant=self.tenant,
            name="Test Export",
            destination_type=DestinationType.S3,
            destination_config={
                "bucket": "test-bucket",
                "size_limits": {
                    "max_file_size_bytes": 100 * 1024 * 1024,  # 100MB
                    "max_total_size_bytes": 1024 * 1024 * 1024,  # 1GB
                },
            },
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"asset_ids": []},
        )

        result = self.rules.validate(
            scheduled_export=export,
            tenant=self.tenant,
            user=self.user,
            validation_type="destination",
        )

        self.assertTrue(result.is_valid)

    def test_validate_destination_size_limits_invalid_negative(self):
        """Test validation fails for negative size limits."""
        export = ScheduledExport(
            tenant=self.tenant,
            name="Test Export",
            destination_type=DestinationType.S3,
            destination_config={
                "bucket": "test-bucket",
                "size_limits": {"max_file_size_bytes": -100},
            },
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"asset_ids": []},
        )

        result = self.rules.validate(
            scheduled_export=export,
            tenant=self.tenant,
            user=self.user,
            validation_type="destination",
        )

        self.assertFalse(result.is_valid)
        self.assertTrue(any("max_file_size_bytes" in err for err in result.errors))

    def test_validate_destination_size_limits_large_warning(self):
        """Test validation warns for very large size limits."""
        export = ScheduledExport(
            tenant=self.tenant,
            name="Test Export",
            destination_type=DestinationType.S3,
            destination_config={
                "bucket": "test-bucket",
                "size_limits": {
                    "max_file_size_bytes": 200 * 1024 * 1024 * 1024,  # 200GB (exceeds 100GB)
                },
            },
            schedule_config={"cron": "0 0 * * *", "timezone": "UTC"},
            source_scope={"asset_ids": []},
        )

        result = self.rules.validate(
            scheduled_export=export,
            tenant=self.tenant,
            user=self.user,
            validation_type="destination",
        )

        # Should be valid but have warnings
        self.assertTrue(result.is_valid)
        self.assertTrue(len(result.warnings) > 0)
        self.assertTrue(any("100GB" in w for w in result.warnings))

    def test_validate_unknown_validation_type_returns_invalid(self):
        """Edge case: unknown validation_type returns invalid result with error."""
        result = self.rules.validate(
            scheduled_export=None,
            tenant=self.tenant,
            user=self.user,
            validation_type="unknown_type",
        )
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("unknown_type", result.errors[0].lower())
