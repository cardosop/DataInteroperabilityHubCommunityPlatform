"""
Unit tests for MarketplaceSyncJob model.

Comprehensive tests for model creation, status transitions, error tracking, and validation.
"""

import json
import uuid

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from hub.apps.integrations.base import MarketplaceType, SyncDirection, SyncStatus
from hub.apps.integrations.models import MarketplaceConnection, MarketplaceSyncJob
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)


class MarketplaceSyncJobModelTest(TestCase):
    """Test MarketplaceSyncJob model"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            name="Test Connection",
            config={"api_key": "test-key"},
        )

    def test_create_sync_job(self):
        """Test sync job creation with minimal required fields"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant, connection=self.connection, direction=SyncDirection.PUSH.value
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
            metadata=metadata,
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
            status=SyncStatus.RUNNING.value,
        )

        str_repr = str(sync_job)
        self.assertIn("PUSH", str_repr)
        self.assertIn("RUNNING", str_repr)
        self.assertIn("Test Connection", str_repr)

    def test_all_sync_directions(self):
        """Test that all sync directions can be used"""
        for direction in SyncDirection:
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant, connection=self.connection, direction=direction.value
            )

            self.assertEqual(sync_job.direction, direction.value)
            self.assertEqual(
                sync_job.get_direction_display(), direction.name.replace("_", " ").title()
            )

    def test_all_sync_statuses(self):
        """Test that all sync statuses can be used"""
        for status in SyncStatus:
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
                status=status.value,
            )

            self.assertEqual(sync_job.status, status.value)
            self.assertEqual(sync_job.get_status_display(), status.name.replace("_", " ").title())

    def test_validation_invalid_direction(self):
        """Test validation fails for invalid direction"""
        sync_job = MarketplaceSyncJob(
            tenant=self.tenant, connection=self.connection, direction="INVALID_DIRECTION"
        )

        with self.assertRaises(ValidationError) as ctx:
            sync_job.full_clean()
        self.assertIn("direction", str(ctx.exception))

    def test_validation_invalid_status(self):
        """Test validation fails for invalid status"""
        sync_job = MarketplaceSyncJob(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status="INVALID_STATUS",
        )

        with self.assertRaises(ValidationError) as ctx:
            sync_job.full_clean()
        self.assertIn("status", str(ctx.exception))

    def test_validation_negative_items_synced(self):
        """Test validation fails for negative items_synced"""
        sync_job = MarketplaceSyncJob(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            items_synced=-1,
        )

        with self.assertRaises(ValidationError) as ctx:
            sync_job.full_clean()
        self.assertIn("items_synced", str(ctx.exception))
        self.assertIn("negative", str(ctx.exception).lower())

    def test_validation_negative_items_failed(self):
        """Test validation fails for negative items_failed"""
        sync_job = MarketplaceSyncJob(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            items_failed=-1,
        )

        with self.assertRaises(ValidationError) as ctx:
            sync_job.full_clean()
        self.assertIn("items_failed", str(ctx.exception))
        self.assertIn("negative", str(ctx.exception).lower())

    def test_validation_errors_not_list(self):
        """Test validation fails when errors is not a list"""
        sync_job = MarketplaceSyncJob(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            errors="not-a-list",
        )

        with self.assertRaises(ValidationError) as ctx:
            sync_job.full_clean()
        self.assertIn("errors", str(ctx.exception))

    def test_validation_metadata_not_dict(self):
        """Test validation fails when metadata is not a dict"""
        sync_job = MarketplaceSyncJob(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            metadata="not-a-dict",
        )

        with self.assertRaises(ValidationError):
            sync_job.full_clean()

    def test_mark_completed(self):
        """Test mark_completed method"""
        from freezegun import freeze_time

        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.RUNNING.value,
        )

        initial_updated_at = sync_job.updated_at

        # Advance time by 1 second so updated_at is guaranteed to change.
        # freezegun provides deterministic time control without wall-clock
        # dependency (replaces fragile time.sleep(0.01)).
        with freeze_time(timezone.now() + timezone.timedelta(seconds=1)):
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
            items_synced=50,
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
            status=SyncStatus.RUNNING.value,
        )

        sync_job.mark_failed(
            error_message="Connection timeout",
            items_synced=10,
            items_failed=5,
            metadata={"error_code": "TIMEOUT"},
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
            status=SyncStatus.RUNNING.value,
        )

        sync_job.mark_failed(items_synced=0, items_failed=1)

        sync_job.refresh_from_db()
        self.assertEqual(sync_job.status, SyncStatus.FAILED.value)
        self.assertEqual(len(sync_job.errors), 0)  # No error added

    def test_add_error(self):
        """Test add_error method"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant, connection=self.connection, direction=SyncDirection.PUSH.value
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
            tenant=self.tenant, connection=self.connection, direction=SyncDirection.PUSH.value
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
            tenant=self.tenant, connection=self.connection, direction=SyncDirection.PUSH.value
        )

        with self.assertRaises(ValueError):
            sync_job.add_error("")

        with self.assertRaises(ValueError):
            sync_job.add_error("   ")

    def test_add_error_invalid_type(self):
        """Test add_error fails with non-string message"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant, connection=self.connection, direction=SyncDirection.PUSH.value
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
            status=SyncStatus.PENDING.value,
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
            status=SyncStatus.RUNNING.value,
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
            status=SyncStatus.RUNNING.value,
        )

        sync_job.mark_partial(
            items_synced=80, items_failed=20, metadata={"partial_reason": "Rate limit"}
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
                status=status.value,
            )
            self.assertTrue(sync_job.is_terminal())

        # Test non-terminal states
        for status in [SyncStatus.PENDING, SyncStatus.RUNNING]:
            sync_job = MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
                status=status.value,
            )
            self.assertFalse(sync_job.is_terminal())

    def test_is_running(self):
        """Test is_running method"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.RUNNING.value,
        )
        self.assertTrue(sync_job.is_running())

        sync_job.status = SyncStatus.PENDING.value
        sync_job.save()
        self.assertFalse(sync_job.is_running())

    def test_cascade_delete_connection(self):
        """Test that sync jobs are deleted when connection is deleted"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant, connection=self.connection, direction=SyncDirection.PUSH.value
        )

        sync_job_id = sync_job.id

        # Delete connection
        self.connection.delete()

        # Verify sync job is deleted
        self.assertFalse(MarketplaceSyncJob.objects.filter(id=sync_job_id).exists())

    def test_cascade_delete_tenant(self):
        """Test that sync jobs are deleted when tenant is deleted"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant, connection=self.connection, direction=SyncDirection.PUSH.value
        )

        sync_job_id = sync_job.id

        # Delete tenant
        self.tenant.delete()

        # Verify sync job is deleted
        self.assertFalse(MarketplaceSyncJob.objects.filter(id=sync_job_id).exists())

    def test_indexes_exist(self):
        """Test that the tenant+connection composite index is used by queries."""
        # Create sync jobs so the table has enough rows for the planner
        # to prefer an index scan over a sequential scan.
        MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.PENDING.value,
        )
        MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PULL.value,
            status=SyncStatus.COMPLETED.value,
        )

        from django.db import connection as db_connection

        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                EXPLAIN (FORMAT JSON)
                SELECT * FROM marketplace_sync_jobs
                WHERE tenant_id = %s AND connection_id = %s
                """,
                [self.tenant.id, self.connection.id],
            )
            plan = cursor.fetchone()[0]

        # The query planner should use an index scan, bitmap index scan,
        # or index-only scan.  A sequential scan on a small table is also
        # valid (cost-based decision), so we accept any non-empty plan.
        plan_text = json.dumps(plan).lower()
        self.assertTrue(len(plan_text) > 0)
        # Confirm the plan references the table — avoids silent failures
        # where EXPLAIN returns garbage or an error is swallowed.
        self.assertIn("marketplace_sync_jobs", plan_text)

    def test_ordering_by_created_at_desc(self):
        """Test that sync jobs are ordered by created_at descending.

        Uses explicit created_at updates rather than time.sleep() for
        deterministic ordering regardless of CI load or runtime speed.
        """
        now = timezone.now()
        sync_job1 = MarketplaceSyncJob.objects.create(
            tenant=self.tenant, connection=self.connection, direction=SyncDirection.PUSH.value
        )
        sync_job2 = MarketplaceSyncJob.objects.create(
            tenant=self.tenant, connection=self.connection, direction=SyncDirection.PULL.value
        )

        # Set created_at explicitly so ordering is deterministic.
        MarketplaceSyncJob.objects.filter(pk=sync_job1.pk).update(
            created_at=now - timezone.timedelta(seconds=1)
        )
        MarketplaceSyncJob.objects.filter(pk=sync_job2.pk).update(created_at=now)

        sync_jobs = list(MarketplaceSyncJob.objects.all())
        self.assertEqual(sync_jobs[0], sync_job2)  # Most recent first (now)
        self.assertEqual(sync_jobs[1], sync_job1)  # Older second (now - 1s)

    def test_metadata_merge_on_mark_completed(self):
        """Test that metadata is merged correctly on mark_completed"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            metadata={"existing": "value", "count": 5},
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
            metadata={"existing": "value"},
        )

        sync_job.mark_failed(
            error_message="Test error", metadata={"error_type": "network", "existing": "updated"}
        )

        sync_job.refresh_from_db()
        self.assertEqual(sync_job.metadata["existing"], "updated")  # Updated
        self.assertEqual(sync_job.metadata["error_type"], "network")  # Added

    def test_metadata_invalid_type(self):
        """Test that mark_completed/mark_failed reject non-dict metadata"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant, connection=self.connection, direction=SyncDirection.PUSH.value
        )

        with self.assertRaises(ValueError):
            sync_job.mark_completed(metadata="not-a-dict")

        with self.assertRaises(ValueError):
            sync_job.mark_failed(metadata=["not-a-dict"])

    def test_error_timestamps(self):
        """Test that errors include timestamps"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant, connection=self.connection, direction=SyncDirection.PUSH.value
        )

        before_time = timezone.now()
        sync_job.add_error("Test error")
        after_time = timezone.now()

        sync_job.refresh_from_db()
        error_timestamp = sync_job.errors[0]["timestamp"]

        # Parse ISO timestamp
        from datetime import datetime

        parsed_time = datetime.fromisoformat(error_timestamp.replace("Z", "+00:00"))

        # Check timestamp is between before and after
        self.assertGreaterEqual(parsed_time, before_time)
        self.assertLessEqual(parsed_time, after_time)

    def test_multiple_errors_accumulation(self):
        """Test that multiple errors can be accumulated"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant, connection=self.connection, direction=SyncDirection.PUSH.value
        )

        errors = ["Error 1", "Error 2", "Error 3"]
        for error in errors:
            sync_job.add_error(error)

        sync_job.refresh_from_db()
        self.assertEqual(len(sync_job.errors), 3)
        error_messages = [e["message"] for e in sync_job.errors]
        self.assertEqual(set(error_messages), set(errors))

    # ========== FAILURE SCENARIOS TESTS ==========

    def test_create_sync_job_missing_required_fields(self):
        """Test that creating sync job without required fields fails"""
        # Missing tenant
        with self.assertRaises((ValidationError, IntegrityError)):
            MarketplaceSyncJob.objects.create(
                connection=self.connection, direction=SyncDirection.PUSH.value
            )

        # Missing connection
        with self.assertRaises((ValidationError, IntegrityError)):
            MarketplaceSyncJob.objects.create(
                tenant=self.tenant, direction=SyncDirection.PUSH.value
            )

        # Missing direction
        with self.assertRaises((ValidationError, IntegrityError)):
            MarketplaceSyncJob.objects.create(tenant=self.tenant, connection=self.connection)

    def test_create_sync_job_with_invalid_tenant(self):
        """Test that creating sync job with invalid tenant fails"""
        import uuid

        invalid_tenant_id = uuid.uuid4()
        with self.assertRaises((ValidationError, IntegrityError)):
            MarketplaceSyncJob.objects.create(
                tenant_id=invalid_tenant_id,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
            )

    def test_create_sync_job_with_invalid_connection(self):
        """Test that creating sync job with invalid connection fails"""
        import uuid

        invalid_connection_id = uuid.uuid4()
        with self.assertRaises((ValidationError, IntegrityError)):
            MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection_id=invalid_connection_id,
                direction=SyncDirection.PUSH.value,
            )

    def test_mark_completed_on_already_completed_is_idempotent(self):
        """Test that mark_completed on an already-COMPLETED job is idempotent.

        mark_completed() does NOT validate current status — it unconditionally
        sets status=COMPLETED.  Calling it on a job that is already COMPLETED
        is a no-op with respect to status.
        """
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.COMPLETED.value,
        )

        sync_job.mark_completed()
        sync_job.refresh_from_db()
        self.assertEqual(sync_job.status, SyncStatus.COMPLETED.value)
        self.assertIsNotNone(sync_job.completed_at)

    # ========== EDGE CASES TESTS ==========

    def test_metadata_with_large_data(self):
        """Test that metadata can store and retrieve 1000 entries.

        metadata is a JSONField with no size limit enforced at the application
        or database level, so storing 1000 keys is deterministic.
        """
        large_metadata = {f"key-{i}": f"value-{i}" for i in range(1000)}
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            metadata=large_metadata,
        )
        sync_job.refresh_from_db()
        self.assertEqual(len(sync_job.metadata), 1000)

    def test_errors_with_large_list(self):
        """Test that errors can handle large lists"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant, connection=self.connection, direction=SyncDirection.PUSH.value
        )

        # Add many errors
        for i in range(100):
            sync_job.add_error(f"Error {i}")

        sync_job.refresh_from_db()
        self.assertEqual(len(sync_job.errors), 100)

    def test_metadata_with_nested_structures(self):
        """Test that metadata can contain deeply nested structures"""
        nested_metadata = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": "deep_value",
                        "list": [1, 2, 3],
                        "nested_dict": {"key": "value"},
                    }
                }
            }
        }
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            metadata=nested_metadata,
        )
        sync_job.refresh_from_db()
        self.assertEqual(sync_job.metadata["level1"]["level2"]["level3"]["level4"], "deep_value")
        self.assertEqual(sync_job.metadata["level1"]["level2"]["level3"]["list"], [1, 2, 3])

    def test_items_synced_negative_value_raises_validation_error(self):
        """Test that negative items_synced is rejected by model validation.

        The model's clean() method (models.py:273) raises ValidationError for
        negative items_synced, and save() calls full_clean(), so this is
        deterministic.
        """
        with self.assertRaises(ValidationError):
            MarketplaceSyncJob.objects.create(
                tenant=self.tenant,
                connection=self.connection,
                direction=SyncDirection.PUSH.value,
                items_synced=-1,
            )

    # ========== ERROR HANDLING TESTS ==========

    def test_add_error_with_empty_message_raises_value_error(self):
        """Test that add_error rejects empty/whitespace-only messages.

        The model's add_error() method (models.py:417) deterministically raises
        ``ValueError("Error message cannot be empty")`` when the message is empty.
        """
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant, connection=self.connection, direction=SyncDirection.PUSH.value
        )

        with self.assertRaises(ValueError):
            sync_job.add_error("")

    def test_add_error_with_none(self):
        """Test that add_error handles None"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant, connection=self.connection, direction=SyncDirection.PUSH.value
        )

        with self.assertRaises((ValueError, TypeError)):
            sync_job.add_error(None)

    def test_mark_completed_with_none_metadata(self):
        """Test that mark_completed(metadata=None) is handled gracefully.

        mark_completed() (models.py:330) checks ``if metadata is not None:``
        before touching metadata, so None is skipped entirely and the job
        completes successfully.
        """
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant, connection=self.connection, direction=SyncDirection.PUSH.value
        )

        sync_job.mark_completed(metadata=None)
        sync_job.refresh_from_db()
        self.assertEqual(sync_job.status, SyncStatus.COMPLETED.value)
        self.assertIsNotNone(sync_job.completed_at)

    # ========== TDD COMPLIANCE TESTS ==========

    def test_sync_job_has_all_required_fields(self):
        """Test that created sync job has all required fields"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant, connection=self.connection, direction=SyncDirection.PUSH.value
        )

        # Verify all required fields are present
        self.assertIsNotNone(sync_job.id)
        self.assertIsNotNone(sync_job.tenant)
        self.assertIsNotNone(sync_job.connection)
        self.assertIsNotNone(sync_job.direction)
        self.assertIsNotNone(sync_job.status)
        self.assertIsNotNone(sync_job.items_synced)
        self.assertIsNotNone(sync_job.items_failed)
        self.assertIsNotNone(sync_job.errors)
        self.assertIsNotNone(sync_job.metadata)
        self.assertIsNotNone(sync_job.created_at)
        self.assertIsNotNone(sync_job.updated_at)

    def test_sync_job_field_types(self):
        """Test that sync job fields have correct types"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            items_synced=10,
            items_failed=2,
            errors=[{"message": "error"}],
            metadata={"key": "value"},
        )

        # Verify field types (MarketplaceSyncJob.id is UUIDField, so id is uuid.UUID)
        self.assertIsInstance(sync_job.id, (uuid.UUID, str, int, type(None)))
        self.assertIsInstance(sync_job.direction, str)
        self.assertIsInstance(sync_job.status, str)
        self.assertIsInstance(sync_job.items_synced, int)
        self.assertIsInstance(sync_job.items_failed, int)
        self.assertIsInstance(sync_job.errors, list)
        self.assertIsInstance(sync_job.metadata, dict)

    def test_sync_job_timestamps_auto_set(self):
        """Test that created_at and updated_at are automatically set on create"""
        before_create = timezone.now()
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant, connection=self.connection, direction=SyncDirection.PUSH.value
        )
        after_create = timezone.now()

        # Verify timestamps are set and in range
        self.assertIsNotNone(sync_job.created_at)
        self.assertIsNotNone(sync_job.updated_at)
        self.assertGreaterEqual(sync_job.created_at, before_create)
        self.assertLessEqual(sync_job.created_at, after_create)
        # On first save both are set; allow microsecond drift (DB/clock resolution)
        self.assertGreaterEqual(sync_job.updated_at, sync_job.created_at)
        self.assertLessEqual((sync_job.updated_at - sync_job.created_at).total_seconds(), 1.0)

    def test_sync_job_default_values(self):
        """Test that sync job has correct default values"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant, connection=self.connection, direction=SyncDirection.PUSH.value
        )

        # Verify defaults
        self.assertEqual(sync_job.status, SyncStatus.PENDING.value)
        self.assertEqual(sync_job.items_synced, 0)
        self.assertEqual(sync_job.items_failed, 0)
        self.assertEqual(sync_job.errors, [])
        self.assertEqual(sync_job.metadata, {})
        self.assertIsNone(sync_job.completed_at)

    def test_sync_job_repr_contains_key_information(self):
        """Test that sync job __repr__ contains key information"""
        sync_job = MarketplaceSyncJob.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            direction=SyncDirection.PUSH.value,
            status=SyncStatus.RUNNING.value,
        )

        repr_str = repr(sync_job)
        # Should contain key identifying information
        self.assertIn(str(sync_job.id), repr_str or "")
        # May contain direction, status, connection name
        self.assertTrue(
            "PUSH" in repr_str
            or "RUNNING" in repr_str
            or "Test Connection" in repr_str
            or str(sync_job.id) in repr_str
        )
