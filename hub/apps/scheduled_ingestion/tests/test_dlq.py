"""
Unit tests for Dead Letter Queue
"""

import uuid
from datetime import timedelta

import pytest
from django.test import TestCase
from django.utils import timezone

from hub.apps.scheduled_ingestion.dead_letter_queue import DeadLetterQueueManager
from hub.apps.scheduled_ingestion.incremental_state import IncrementalStateManager
from hub.apps.scheduled_ingestion.models import DeadLetterQueueItem, ScheduledIngestion
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)


class DeadLetterQueueTest(TestCase):
    """Test Dead Letter Queue"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )

        self.user = User.objects.create_user(
            email=f"user-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.scheduled_ingestion = ScheduledIngestion.objects.create(
            tenant=self.tenant,
            name="Test Ingestion",
            source_type="S3",
            source_config={"bucket": "test-bucket"},
            schedule_type="DAILY",
            schedule_config={"time": "00:00"},
            file_pattern=".*\\.csv",
            created_by=self.user,
        )

    def test_sync_from_ingestion_state(self):
        """Test syncing DLQ items from ingestion state"""
        # Mark files as permanently failed
        state_manager = IncrementalStateManager(self.scheduled_ingestion)

        # Mark files as failed multiple times to exceed max retries
        for i in range(3):
            state_manager.mark_file_failed(
                file_path="file1.csv",
                error_message="Connection timeout",
                error_code="TIMEOUT",
                retry_count=i,
                max_retries=3,
            )

        # Sync DLQ
        count = DeadLetterQueueManager.sync_from_ingestion_state(str(self.scheduled_ingestion.id))

        assert count == 1

        # Verify DLQ item created
        dlq_item = DeadLetterQueueItem.objects.get(
            scheduled_ingestion=self.scheduled_ingestion, file_path="file1.csv"
        )

        assert dlq_item.error_code == "TIMEOUT"
        assert dlq_item.retry_count == 3
        assert dlq_item.resolution_status == "PENDING"

    def test_retry_file(self):
        """Test retrying a failed file"""
        # Create DLQ item
        dlq_item = DeadLetterQueueItem.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            file_path="file1.csv",
            error_message="Connection timeout",
            error_code="TIMEOUT",
            retry_count=3,
            first_failed_at=timezone.now() - timedelta(hours=1),
            last_failed_at=timezone.now() - timedelta(minutes=30),
            permanently_failed_at=timezone.now() - timedelta(minutes=30),
            resolution_status="PENDING",
        )

        # Pre-condition: ensure "file1.csv" is tracked as failed in ingestion state
        state_manager = IncrementalStateManager(self.scheduled_ingestion)
        state_manager.mark_file_failed(
            "file1.csv", "Connection timeout", retry_count=3, max_retries=3
        )
        assert state_manager.is_file_failed("file1.csv"), (
            "File must be in failed state before retry"
        )

        # Retry file
        success = DeadLetterQueueManager.retry_file(
            dlq_item_id=str(dlq_item.id), user_id=str(self.user.id)
        )

        assert success

        # Verify DLQ item updated
        dlq_item.refresh_from_db()
        assert dlq_item.resolution_status == "RETRYING"
        assert dlq_item.retry_count == 4
        assert dlq_item.resolved_by == self.user

        # Verify file cleared from ingestion state — retry_file creates a new
        # IncrementalStateManager internally, so we must refresh our view.
        state_manager.scheduled_ingestion.refresh_from_db()
        state_manager = IncrementalStateManager(self.scheduled_ingestion)
        assert not state_manager.is_file_failed("file1.csv"), (
            "File must be cleared from failed state after retry"
        )

    def test_resolve_item(self):
        """Test resolving a DLQ item"""
        # Create DLQ item
        dlq_item = DeadLetterQueueItem.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            file_path="file1.csv",
            error_message="Invalid format",
            error_code="VALIDATION_ERROR",
            retry_count=3,
            first_failed_at=timezone.now() - timedelta(hours=1),
            last_failed_at=timezone.now() - timedelta(minutes=30),
            permanently_failed_at=timezone.now() - timedelta(minutes=30),
            resolution_status="PENDING",
        )

        # Resolve as IGNORED
        DeadLetterQueueManager.resolve_item(
            dlq_item_id=str(dlq_item.id),
            resolution_status="IGNORED",
            resolution_notes="File format is not supported",
            user_id=str(self.user.id),
        )

        # Verify DLQ item updated
        dlq_item.refresh_from_db()
        assert dlq_item.resolution_status == "IGNORED"
        assert dlq_item.resolution_notes == "File format is not supported"
        assert dlq_item.resolved_by == self.user
        assert dlq_item.resolved_at is not None

    def test_get_dlq_dashboard(self):
        """Test getting DLQ dashboard"""
        # Create DLQ items
        DeadLetterQueueItem.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            file_path="file1.csv",
            error_message="Error 1",
            error_code="TIMEOUT",
            retry_count=3,
            first_failed_at=timezone.now(),
            last_failed_at=timezone.now(),
            permanently_failed_at=timezone.now(),
            resolution_status="PENDING",
        )

        DeadLetterQueueItem.objects.create(
            scheduled_ingestion=self.scheduled_ingestion,
            file_path="file2.csv",
            error_message="Error 2",
            error_code="VALIDATION_ERROR",
            retry_count=3,
            first_failed_at=timezone.now(),
            last_failed_at=timezone.now(),
            permanently_failed_at=timezone.now(),
            resolution_status="RESOLVED",
        )

        dashboard = DeadLetterQueueManager.get_dlq_dashboard(tenant_id=str(self.tenant.id))

        assert "summary" in dashboard
        assert dashboard["summary"]["total_items"] == 2
        assert dashboard["summary"]["pending_items"] == 1
        assert dashboard["summary"]["resolved_items"] == 1
        assert "items" in dashboard
        assert len(dashboard["items"]) == 2
