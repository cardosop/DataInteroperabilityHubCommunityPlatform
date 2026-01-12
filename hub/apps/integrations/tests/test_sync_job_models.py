"""
Unit tests for MarketplaceSyncJob model.

Comprehensive tests for model creation, status transitions, error tracking, and validation.
"""
import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import timedelta

from hub.apps.tenants.models import Tenant
from hub.apps.integrations.models import MarketplaceConnection, MarketplaceSyncJob
from hub.apps.integrations.base import MarketplaceType, SyncDirection, SyncStatus


pytestmark = pytest.mark.django_db(transaction=True)


class MarketplaceSyncJobModelTest(TestCase):
    """Test MarketplaceSyncJob model"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant",
            slug="test-tenant"
        )
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test-key"}
        )

    def test_create_sync_job(self):
        """Test sync job creation with minimal required fields"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value
        )

        self.assertEqual(sync_job.tenant, self.tenant)
        self.assertEqual(sync_job.connection, self.connection)
        self.assertEqual(sync_job.direction, SyncDirection.PUSH.value)
        self.assertEqual(sync_job.status, SyncStatus.PENDING.value)
        self.assertEqual(sync_job.items_synced, 0)
        self.assertEqual(sync_job.items_failed, 0)
        self.assertEqual(sync_job.errors, [])
        self.assertEqual(sync_job.metadata, {})
        self.assertIsNotNone(sync_job.id)
        self.assertIsNotNone(sync_job.created_at)
        self.assertIsNone(sync_job.completed_at)

    def test_create_sync_job_with_all_fields(self):
        """Test sync job creation with all fields"""
        metadata = {"source": "api", "batch_size": 100}
        errors = [{"message": "Test error", "timestamp": "2025-01-01T00:00:00Z"}]

        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.RUNNING.value,
            items_synced=50,
            items_failed=5,
            errors=errors,
            metadata=metadata
        )

        self.assertEqual(sync_job.direction, SyncDirection.PULL.value)
        self.assertEqual(sync_job.status, SyncStatus.RUNNING.value)
        self.assertEqual(sync_job.items_synced, 50)
        self.assertEqual(sync_job.items_failed, 5)
        self.assertEqual(sync_job.errors, errors)
        self.assertEqual(sync_job.metadata, metadata)

    def test_sync_job_str_representation(self):
        """Test string representation of sync job"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.RUNNING.value
        )

        str_repr = str(sync_job)
        self.assertIn("PUSH", str_repr)
        self.assertIn("RUNNING", str_repr)
        self.assertIn("Test Connection", str_repr)

    def test_all_sync_directions(self):
        """Test that all sync directions can be used"""
        for direction in SyncDirection:
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=direction.value
            )

            self.assertEqual(sync_job.direction, direction.value)
            self.assertEqual(sync_job.get_direction_display(), direction.name.replace("_", " ").title())

    def test_all_sync_statuses(self):
        """Test that all sync statuses can be used"""
        for status in SyncStatus:
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
                status=status.value
            )

            self.assertEqual(sync_job.status, status.value)
            self.assertEqual(sync_job.get_status_display(), status.name.replace("_", " ").title())

    def test_validation_invalid_direction(self):
        """Test validation fails for invalid direction"""
        sync_job = MarketplaceSyncJob(
            tenant=self.tenant,
            connection=self.connection,
            direction="INVALID_DIRECTION"
        )

        with self.assertRaises(ValidationError):
            sync_job.full_clean()

    def test_validation_invalid_status(self):
        """Test validation fails for invalid status"""
        sync_job = MarketplaceSyncJob(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status="INVALID_STATUS"
        )

        with self.assertRaises(ValidationError):
            sync_job.full_clean()

    def test_validation_negative_items_synced(self):
        """Test validation fails for negative items_synced"""
        sync_job = MarketplaceSyncJob(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            items_synced=-1
        )

        with self.assertRaises(ValidationError):
            sync_job.full_clean()

    def test_validation_negative_items_failed(self):
        """Test validation fails for negative items_failed"""
        sync_job = MarketplaceSyncJob(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            items_failed=-1
        )

        with self.assertRaises(ValidationError):
            sync_job.full_clean()

    def test_validation_errors_not_list(self):
        """Test validation fails when errors is not a list"""
        sync_job = MarketplaceSyncJob(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            errors="not-a-list"
        )

        with self.assertRaises(ValidationError):
            sync_job.full_clean()

    def test_validation_metadata_not_dict(self):
        """Test validation fails when metadata is not a dict"""
        sync_job = MarketplaceSyncJob(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            metadata="not-a-dict"
        )

        with self.assertRaises(ValidationError):
            sync_job.full_clean()

    def test_mark_completed(self):
        """Test mark_completed method"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.RUNNING.value
        )

        initial_updated_at = sync_job.updated_at

        import time
        time.sleep(0.01)

        sync_job.mark_completed(items_synced=100, metadata={"duration": 30})

        sync_job.refresh_from_db()
        self.assertEqual(sync_job.status, SyncStatus.COMPLETED.value)
        self.assertIsNotNone(sync_job.completed_at)
        self.assertEqual(sync_job.items_synced, 100)
        self.assertEqual(sync_job.metadata["duration"], 30)
        self.assertGreater(sync_job.updated_at, initial_updated_at)

    def test_mark_completed_without_params(self):
        """Test mark_completed without optional parameters"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.RUNNING.value,
            items_synced=50
        )

        sync_job.mark_completed()

        sync_job.refresh_from_db()
        self.assertEqual(sync_job.status, SyncStatus.COMPLETED.value)
        self.assertIsNotNone(sync_job.completed_at)
        self.assertEqual(sync_job.items_synced, 50)  # Unchanged

    def test_mark_failed(self):
        """Test mark_failed method"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.RUNNING.value
        )

        sync_job.mark_failed(
            error_message="Connection timeout",
            items_synced=10,
            items_failed=5,
            metadata={"error_code": "TIMEOUT"}
        )

        sync_job.refresh_from_db()
        self.assertEqual(sync_job.status, SyncStatus.FAILED.value)
        self.assertIsNotNone(sync_job.completed_at)
        self.assertEqual(sync_job.items_synced, 10)
        self.assertEqual(sync_job.items_failed, 5)
        self.assertEqual(len(sync_job.errors), 1)
        self.assertIn("Connection timeout", sync_job.errors[0]["message"])
        self.assertEqual(sync_job.metadata["error_code"], "TIMEOUT")

    def test_mark_failed_without_error_message(self):
        """Test mark_failed without error message"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.RUNNING.value
        )

        sync_job.mark_failed(items_synced=0, items_failed=1)

        sync_job.refresh_from_db()
        self.assertEqual(sync_job.status, SyncStatus.FAILED.value)
        self.assertEqual(len(sync_job.errors), 0)  # No error added

    def test_add_error(self):
        """Test add_error method"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value
        )

        sync_job.add_error("First error")
        sync_job.add_error("Second error")

        sync_job.refresh_from_db()
        self.assertEqual(len(sync_job.errors), 2)
        self.assertIn("First error", sync_job.errors[0]["message"])
        self.assertIn("Second error", sync_job.errors[1]["message"])
        self.assertIn("timestamp", sync_job.errors[0])
        self.assertIn("timestamp", sync_job.errors[1])

    def test_add_error_without_save(self):
        """Test add_error without saving"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value
        )

        sync_job.add_error("Error 1", save=False)
        sync_job.add_error("Error 2", save=False)

        # Errors should be in memory but not saved yet
        self.assertEqual(len(sync_job.errors), 2)

        # Save manually
        sync_job.save()

        sync_job.refresh_from_db()
        self.assertEqual(len(sync_job.errors), 2)

    def test_add_error_empty_message(self):
        """Test add_error fails with empty message"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value
        )

        with self.assertRaises(ValueError):
            sync_job.add_error("")

        with self.assertRaises(ValueError):
            sync_job.add_error("   ")

    def test_add_error_invalid_type(self):
        """Test add_error fails with non-string message"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value
        )

        with self.assertRaises(ValueError):
            sync_job.add_error(123)

        with self.assertRaises(ValueError):
            sync_job.add_error(None)

    def test_mark_running(self):
        """Test mark_running method"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value
        )

        sync_job.mark_running()

        sync_job.refresh_from_db()
        self.assertEqual(sync_job.status, SyncStatus.RUNNING.value)

    def test_mark_running_already_running(self):
        """Test mark_running when already running doesn't cause issues"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.RUNNING.value
        )

        initial_updated_at = sync_job.updated_at

        # Should not raise error and should update timestamp
        sync_job.mark_running()

        sync_job.refresh_from_db()
        self.assertEqual(sync_job.status, SyncStatus.RUNNING.value)
        # Updated_at should change even if status doesn't
        self.assertGreaterEqual(sync_job.updated_at, initial_updated_at)

    def test_mark_partial(self):
        """Test mark_partial method"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.RUNNING.value
        )

        sync_job.mark_partial(
            items_synced=80,
            items_failed=20,
            metadata={"partial_reason": "Rate limit"}
        )

        sync_job.refresh_from_db()
        self.assertEqual(sync_job.status, SyncStatus.PARTIAL.value)
        self.assertIsNotNone(sync_job.completed_at)
        self.assertEqual(sync_job.items_synced, 80)
        self.assertEqual(sync_job.items_failed, 20)
        self.assertEqual(sync_job.metadata["partial_reason"], "Rate limit")

    def test_is_terminal(self):
        """Test is_terminal method"""
        # Test terminal states
        for status in [SyncStatus.COMPLETED, SyncStatus.FAILED, SyncStatus.PARTIAL]:
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
                status=status.value
            )
            self.assertTrue(sync_job.is_terminal())

        # Test non-terminal states
        for status in [SyncStatus.PENDING, SyncStatus.RUNNING]:
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
                status=status.value
            )
            self.assertFalse(sync_job.is_terminal())

    def test_is_running(self):
        """Test is_running method"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.RUNNING.value
        )
        self.assertTrue(sync_job.is_running())

        sync_job.status = SyncStatus.PENDING.value
        sync_job.save()
        self.assertFalse(sync_job.is_running())

    def test_cascade_delete_connection(self):
        """Test that sync jobs are deleted when connection is deleted"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value
        )

        sync_job_id = sync_job.id

        # Delete connection
        self.connection.delete()

        # Verify sync job is deleted
        self.assertFalse(MarketplaceSyncJob.objects.filter(id=sync_job_id).exists())

    def test_cascade_delete_tenant(self):
        """Test that sync jobs are deleted when tenant is deleted"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value
        )

        sync_job_id = sync_job.id

        # Delete tenant
        self.tenant.delete()

        # Verify sync job is deleted
        self.assertFalse(MarketplaceSyncJob.objects.filter(id=sync_job_id).exists())

    def test_indexes_exist(self):
        """Test that indexes are created correctly"""
        # Create sync jobs to test indexes
        MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value
        )

        MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.COMPLETED.value
        )

        # Verify queries use indexes (check execution plan)
        from django.db import connection as db_connection

        with db_connection.cursor() as cursor:
            # Query that should use tenant + connection index
            cursor.execute("""
                EXPLAIN SELECT * FROM marketplace_sync_jobs
                WHERE tenant_id = %s AND connection_id = %s
            """, [self.tenant.id, self.connection.id])

            # Just verify query executes without error
            # Actual index usage depends on PostgreSQL query planner

    def test_ordering_by_created_at_desc(self):
        """Test that sync jobs are ordered by created_at descending"""
        sync_job1 = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value
        )

        import time
        time.sleep(0.01)

        sync_job2 = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PULL.value
        )

        sync_jobs = list(MarketplaceSyncJob.objects.all())
        self.assertEqual(sync_jobs[0], sync_job2)  # Most recent first
        self.assertEqual(sync_jobs[1], sync_job1)

    def test_metadata_merge_on_mark_completed(self):
        """Test that metadata is merged correctly on mark_completed"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            metadata={"existing": "value", "count": 5}
        )

        sync_job.mark_completed(metadata={"count": 10, "new": "field"})

        sync_job.refresh_from_db()
        self.assertEqual(sync_job.metadata["existing"], "value")  # Preserved
        self.assertEqual(sync_job.metadata["count"], 10)  # Updated
        self.assertEqual(sync_job.metadata["new"], "field")  # Added

    def test_metadata_merge_on_mark_failed(self):
        """Test that metadata is merged correctly on mark_failed"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            metadata={"existing": "value"}
        )

        sync_job.mark_failed(
            error_message="Test error",
            metadata={"error_type": "network", "existing": "updated"}
        )

        sync_job.refresh_from_db()
        self.assertEqual(sync_job.metadata["existing"], "updated")  # Updated
        self.assertEqual(sync_job.metadata["error_type"], "network")  # Added

    def test_metadata_invalid_type(self):
        """Test that mark_completed/mark_failed reject non-dict metadata"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value
        )

        with self.assertRaises(ValueError):
            sync_job.mark_completed(metadata="not-a-dict")

        with self.assertRaises(ValueError):
            sync_job.mark_failed(metadata=["not-a-dict"])

    def test_error_timestamps(self):
        """Test that errors include timestamps"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value
        )

        before_time = timezone.now()
        sync_job.add_error("Test error")
        after_time = timezone.now()

        sync_job.refresh_from_db()
        error_timestamp = sync_job.errors[0]["timestamp"]

        # Parse ISO timestamp
        from datetime import datetime
        parsed_time = datetime.fromisoformat(error_timestamp.replace('Z', '+00:00'))

        # Check timestamp is between before and after
        self.assertGreaterEqual(parsed_time, before_time)
        self.assertLessEqual(parsed_time, after_time)

    def test_multiple_errors_accumulation(self):
        """Test that multiple errors can be accumulated"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value
        )

        errors = ["Error 1", "Error 2", "Error 3"]
        for error in errors:
            sync_job.add_error(error)

        sync_job.refresh_from_db()
        self.assertEqual(len(sync_job.errors), 3)
        error_messages = [e["message"] for e in sync_job.errors]
        self.assertEqual(set(error_messages), set(errors))

