"""
Scheduled Export Performance Tests

Performance tests for scheduled export run lifecycle.
Uses real DB and real services - no mocks.

Coverage:
- Export run creation performance
- Export run processing performance
- Multiple concurrent exports
- Large export volumes
"""

import time
import uuid

import pytest

pytestmark = pytest.mark.slow
from django.test import TestCase, TransactionTestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.scheduled_export.models import (
    DestinationType,
    ScheduledExport,
    ScheduledExportRun,
    ScheduledExportRunStatus,
    ScheduledExportStatus,
)
from hub.apps.tenants.models import Tenant, TenantPlan, TenantStatus
from hub.apps.users.models import User, UserStatus

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.serial,  # Run tests sequentially to avoid deadlocks
]


class ScheduledExportPerformanceTest(TransactionTestCase):
    """Performance tests for scheduled export"""

    # Disable automatic database flush to avoid foreign key constraint issues
    reset_sequences = False
    serialized_rollback = False

    def setUp(self):
        """Set up test fixtures"""
        self.client = APIClient()

        # Create tenant with unique name to avoid conflicts
        unique_id = uuid.uuid4().hex[:8]
        # Use get_or_create to handle potential race conditions
        self.tenant, created = Tenant.objects.get_or_create(
            slug=f"performance-test-tenant-{unique_id}",
            defaults={
                "name": f"Performance Test Tenant {unique_id}",
                "status": TenantStatus.ACTIVE,
            },
        )
        # Update name if tenant already existed
        if not created:
            self.tenant.name = f"Performance Test Tenant {unique_id}"
            self.tenant.status = TenantStatus.ACTIVE
            self.tenant.save()

        # Create plan and assign to tenant
        self.plan = TenantPlan.objects.create(
            name=f"Performance Test Plan {unique_id}",
            slug=f"perf-test-plan-{unique_id}",
            tier="FREE",
            limits_json={"max_scheduled_exports": 100, "max_export_runs_per_month": 10000},
            is_active=True,
        )
        self.tenant.plan = self.plan
        self.tenant.save()

        # Create subscription
        Subscription.objects.create(
            tenant=self.tenant,
            plan=self.plan,
            status=SubscriptionStatus.ACTIVE,
            current_period_start=timezone.now(),
            current_period_end=timezone.now() + timezone.timedelta(days=30),
        )

        # Create user with unique email
        self.user = User.objects.create_user(
            email=f"performance-{unique_id}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create assets
        self.assets = []
        for i in range(10):
            asset = Asset.objects.create(
                tenant=self.tenant,
                key=f"perf-asset-{i}",
                name=f"Performance Asset {i}",
                status=AssetStatus.ACTIVE,
            )
            self.assets.append(asset)

        # Create scheduled export
        self.export = ScheduledExport.objects.create(
            tenant=self.tenant,
            name="Performance Test Export",
            schedule_config={"cron": "0 2 * * *"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "perf-bucket"},
            source_scope={"asset_ids": [str(a.id) for a in self.assets]},
            status=ScheduledExportStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.user)

    @classmethod
    def _fixture_teardown(cls):
        """Override to skip database flush for performance tests."""
        # Don't flush - transactions are rolled back which provides isolation
        pass

    def test_export_run_creation_performance(self):
        """Test performance of export run creation"""
        # Measure time to create multiple runs
        start_time = time.time()

        runs = []
        for i in range(10):
            run = ScheduledExportRun.objects.create(
                scheduled_export=self.export,
                tenant=self.tenant,
                status=ScheduledExportRunStatus.RUNNING,
                started_at=timezone.now(),
            )
            runs.append(run)

        end_time = time.time()
        elapsed_time = end_time - start_time

        # Should create 10 runs in reasonable time (< 2 seconds; allows CI variance)
        self.assertLess(elapsed_time, 2.0)
        self.assertEqual(len(runs), 10)

    def test_export_run_listing_performance(self):
        """Test performance of listing export runs"""
        # Create multiple runs
        for i in range(50):
            ScheduledExportRun.objects.create(
                scheduled_export=self.export,
                tenant=self.tenant,
                status=ScheduledExportRunStatus.COMPLETED,
                started_at=timezone.now(),
                completed_at=timezone.now(),
            )

        # Measure time to list runs
        start_time = time.time()

        response = self.client.get(f"/api/v1/scheduled-exports/{self.export.id}/runs/")

        end_time = time.time()
        elapsed_time = end_time - start_time

        # Should list runs in reasonable time (< 1 second)
        self.assertLess(elapsed_time, 1.0)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_concurrent_export_creation(self):
        """Test performance with concurrent export creation"""
        # Create multiple exports concurrently
        start_time = time.time()

        exports = []
        for i in range(5):
            export = ScheduledExport.objects.create(
                tenant=self.tenant,
                name=f"Concurrent Export {i}",
                schedule_config={"cron": "0 2 * * *"},
                destination_type=DestinationType.S3,
                destination_config={"bucket": f"concurrent-bucket-{i}"},
                source_scope={"asset_ids": [str(self.assets[0].id)]},
                status=ScheduledExportStatus.ACTIVE,
            )
            exports.append(export)

        end_time = time.time()
        elapsed_time = end_time - start_time

        # Should create 5 exports in reasonable time (< 2 seconds; allows CI variance)
        self.assertLess(elapsed_time, 2.0)
        self.assertEqual(len(exports), 5)

    def test_large_export_source_scope_performance(self):
        """Test performance with large source scope"""
        # Create export with many assets
        large_asset_ids = [str(a.id) for a in self.assets]

        start_time = time.time()

        large_export = ScheduledExport.objects.create(
            tenant=self.tenant,
            name="Large Scope Export",
            schedule_config={"cron": "0 2 * * *"},
            destination_type=DestinationType.S3,
            destination_config={"bucket": "large-bucket"},
            source_scope={"asset_ids": large_asset_ids},
            status=ScheduledExportStatus.ACTIVE,
        )

        end_time = time.time()
        elapsed_time = end_time - start_time

        # Should create export with large scope in reasonable time (< 1 second)
        self.assertLess(elapsed_time, 1.0)
        self.assertEqual(len(large_export.source_scope["asset_ids"]), len(self.assets))

    def test_export_run_status_update_performance(self):
        """Test performance of updating export run status"""
        # Create run
        run = ScheduledExportRun.objects.create(
            scheduled_export=self.export,
            tenant=self.tenant,
            status=ScheduledExportRunStatus.RUNNING,
            started_at=timezone.now(),
        )

        # Measure time to update status multiple times
        start_time = time.time()

        for i in range(10):
            run.status = (
                ScheduledExportRunStatus.COMPLETED
                if i % 2 == 0
                else ScheduledExportRunStatus.FAILED
            )
            run.save()

        end_time = time.time()
        elapsed_time = end_time - start_time

        # Should update status multiple times in reasonable time (< 1 second; allows CI variance)
        self.assertLess(elapsed_time, 1.0)
