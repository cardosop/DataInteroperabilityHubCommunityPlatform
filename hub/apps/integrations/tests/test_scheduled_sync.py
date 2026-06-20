"""
Tests for Scheduled Marketplace Sync

Comprehensive tests for scheduled sync functionality including:
- Unit tests for schedule_sync() and unschedule_sync() methods
- Integration tests with scheduler
- E2E tests for scheduled sync execution
"""

import contextlib
import logging
import uuid
from datetime import timedelta

import pytest
from django.db.models.signals import post_save
from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.assets.models import Asset
from hub.apps.audit.models import AuditEvent
from hub.apps.core.services.base import ConflictError, NotFoundError, ValidationError
from hub.apps.integrations.base import MarketplaceType, SyncDirection
from hub.apps.integrations.models import (
    MarketplaceConnection,
    MarketplaceSyncJob,
    ScheduledMarketplaceSync,
    ScheduledMarketplaceSyncStatus,
    ScheduleType,
)
from hub.apps.integrations.services import MarketplaceIntegrationService
from hub.apps.integrations.tasks import process_scheduled_syncs
from tests.fixtures.test_data_factories import TenantFactory, UserFactory

pytestmark = pytest.mark.django_db(transaction=True)

_logger = logging.getLogger("hub.apps.integrations.tests.scheduled_sync")


def _disconnect_semantic_signals():
    """Disconnect semantic service post_save signals to prevent timeouts
    during integration tests that create many Asset/Contract rows.

    Logs a debug message on failure rather than silently swallowing the
    exception so that signal import refactors surface in test output.
    """
    from django.db.models.signals import post_save as _ps

    try:
        from hub.apps.assets.models import Asset as _Asset
        from hub.apps.contracts.models import Contract as _Contract
        from hub.apps.semantic.signals import asset_saved, contract_saved

        _ps.disconnect(contract_saved, sender=_Contract)
        _ps.disconnect(asset_saved, sender=_Asset)
    except (ImportError, AttributeError) as exc:
        _logger.debug("Cannot disconnect semantic signals (may already be disconnected): %s", exc)
    except Exception:
        _logger.warning("Unexpected error disconnecting semantic signals", exc_info=True)


def _reconnect_semantic_signals():
    """Reconnect semantic service post_save signals after integration tests.

    Logs a debug message on failure rather than silently swallowing the
    exception so that signal import refactors surface in test output.
    """
    from django.db.models.signals import post_save as _ps

    try:
        from hub.apps.assets.models import Asset as _Asset
        from hub.apps.contracts.models import Contract as _Contract
        from hub.apps.semantic.signals import asset_saved, contract_saved

        _ps.connect(contract_saved, sender=_Contract, weak=False)
        _ps.connect(asset_saved, sender=_Asset, weak=False)
    except (ImportError, AttributeError) as exc:
        _logger.debug("Cannot reconnect semantic signals (may not be available): %s", exc)
    except Exception:
        _logger.warning("Unexpected error reconnecting semantic signals", exc_info=True)


class ScheduledSyncServiceUnitTest(TestCase):
    """Unit tests for schedule_sync() and unschedule_sync() methods"""

    def setUp(self):
        """Set up test fixtures"""
        _disconnect_semantic_signals()
        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant)
        self.service = MarketplaceIntegrationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id), request_id="test-request-123"
        )
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            name="Test Connection",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            is_active=True,
        )
        self.connection.set_config(
            {"api_key": "test-api-key", "endpoint": "https://api.example.com"}
        )

    def test_schedule_sync_daily_success(self):
        """Test successful scheduling of daily sync"""
        schedule_config = {"time": "02:00"}

        scheduled_sync = self.service.schedule_sync(
            connection_id=str(self.connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Daily Sync Test",
            direction=SyncDirection.PUSH.value,
            schedule_type=ScheduleType.DAILY.value,
            schedule_config=schedule_config,
            sync_options={"asset_ids": ["asset-1", "asset-2"]},
        )

        # Verify scheduled sync was created
        self.assertTrue(scheduled_sync.id, "Scheduled sync should have a non-empty id after save")
        self.assertEqual(scheduled_sync.name, "Daily Sync Test")
        self.assertEqual(scheduled_sync.direction, SyncDirection.PUSH.value)
        self.assertEqual(scheduled_sync.schedule_type, ScheduleType.DAILY.value)
        self.assertEqual(scheduled_sync.schedule_config, schedule_config)
        self.assertEqual(scheduled_sync.status, ScheduledMarketplaceSyncStatus.ACTIVE.value)
        self.assertIsNotNone(scheduled_sync.next_run_at)
        self.assertEqual(scheduled_sync.connection, self.connection)
        self.assertEqual(scheduled_sync.tenant, self.tenant)

    def test_schedule_sync_weekly_success(self):
        """Test successful scheduling of weekly sync"""
        schedule_config = {"days_of_week": [0, 2, 4], "time": "03:00"}  # Monday, Wednesday, Friday

        scheduled_sync = self.service.schedule_sync(
            connection_id=str(self.connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Weekly Sync Test",
            direction=SyncDirection.PULL.value,
            schedule_type=ScheduleType.WEEKLY.value,
            schedule_config=schedule_config,
            sync_options={"listing_ids": ["listing-1"]},
        )

        # Verify scheduled sync was created
        self.assertIsNotNone(scheduled_sync.id)
        self.assertEqual(scheduled_sync.schedule_type, ScheduleType.WEEKLY.value)
        self.assertEqual(scheduled_sync.schedule_config, schedule_config)
        self.assertIsNotNone(scheduled_sync.next_run_at)

    def test_schedule_sync_monthly_success(self):
        """Test successful scheduling of monthly sync"""
        schedule_config = {"day_of_month": 15, "time": "04:00"}

        scheduled_sync = self.service.schedule_sync(
            connection_id=str(self.connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Monthly Sync Test",
            direction=SyncDirection.BIDIRECTIONAL.value,
            schedule_type=ScheduleType.MONTHLY.value,
            schedule_config=schedule_config,
            sync_options={"asset_ids": ["asset-1"], "listing_ids": ["listing-1"]},
        )

        # Verify scheduled sync was created
        self.assertIsNotNone(scheduled_sync.id)
        self.assertEqual(scheduled_sync.schedule_type, ScheduleType.MONTHLY.value)
        self.assertIsNotNone(scheduled_sync.next_run_at)

    def test_schedule_sync_custom_cron_success(self):
        """Test successful scheduling with custom cron expression"""
        schedule_config = {"cron": "0 2 * * *", "timezone": "UTC"}  # Daily at 2 AM

        scheduled_sync = self.service.schedule_sync(
            connection_id=str(self.connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Cron Sync Test",
            direction=SyncDirection.PUSH.value,
            schedule_type=ScheduleType.CUSTOM_CRON.value,
            schedule_config=schedule_config,
            sync_options={"asset_ids": ["asset-1"]},
        )

        # Verify scheduled sync was created
        self.assertIsNotNone(scheduled_sync.id)
        self.assertEqual(scheduled_sync.schedule_type, ScheduleType.CUSTOM_CRON.value)
        self.assertIsNotNone(scheduled_sync.next_run_at)

    def test_schedule_sync_connection_not_found(self):
        """Test error handling when connection not found"""
        fake_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError):
            self.service.schedule_sync(
                connection_id=fake_id,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Sync",
                direction=SyncDirection.PUSH.value,
                schedule_type=ScheduleType.DAILY.value,
                schedule_config={"time": "00:00"},
            )

    def test_schedule_sync_connection_not_active(self):
        """Test error handling when connection is not active"""
        self.connection.is_active = False
        self.connection.save()

        with self.assertRaises(ValidationError) as cm:
            self.service.schedule_sync(
                connection_id=str(self.connection.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Sync",
                direction=SyncDirection.PUSH.value,
                schedule_type=ScheduleType.DAILY.value,
                schedule_config={"time": "00:00"},
            )

        self.assertIn("not active", str(cm.exception).lower())

    def test_schedule_sync_invalid_direction(self):
        """Test error handling for invalid sync direction"""
        with self.assertRaises(ValidationError) as cm:
            self.service.schedule_sync(
                connection_id=str(self.connection.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Sync",
                direction="INVALID_DIRECTION",
                schedule_type=ScheduleType.DAILY.value,
                schedule_config={"time": "00:00"},
            )

        self.assertIn("direction", str(cm.exception).lower())

    def test_schedule_sync_invalid_schedule_type(self):
        """Test error handling for invalid schedule type"""
        with self.assertRaises(ValidationError) as cm:
            self.service.schedule_sync(
                connection_id=str(self.connection.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Sync",
                direction=SyncDirection.PUSH.value,
                schedule_type="INVALID_TYPE",
                schedule_config={"time": "00:00"},
            )

        self.assertIn("schedule type", str(cm.exception).lower())

    def test_schedule_sync_invalid_cron_expression(self):
        """Test error handling for invalid cron expression"""
        with self.assertRaises(ValidationError) as cm:
            self.service.schedule_sync(
                connection_id=str(self.connection.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test Sync",
                direction=SyncDirection.PUSH.value,
                schedule_type=ScheduleType.CUSTOM_CRON.value,
                schedule_config={"cron": "invalid cron"},
            )

        self.assertIn("cron", str(cm.exception).lower())

    def test_schedule_sync_duplicate_name(self):
        """Test error handling for duplicate schedule name"""
        # Create first scheduled sync
        self.service.schedule_sync(
            connection_id=str(self.connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Duplicate Test",
            direction=SyncDirection.PUSH.value,
            schedule_type=ScheduleType.DAILY.value,
            schedule_config={"time": "00:00"},
        )

        # Try to create another with same name
        with self.assertRaises(ConflictError) as cm:
            self.service.schedule_sync(
                connection_id=str(self.connection.id),
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Duplicate Test",
                direction=SyncDirection.PULL.value,
                schedule_type=ScheduleType.DAILY.value,
                schedule_config={"time": "01:00"},
            )

        self.assertIn("already exists", str(cm.exception).lower())

    def test_unschedule_sync_success(self):
        """Test successful unscheduling of sync"""
        # Create scheduled sync
        scheduled_sync = self.service.schedule_sync(
            connection_id=str(self.connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Unschedule Test",
            direction=SyncDirection.PUSH.value,
            schedule_type=ScheduleType.DAILY.value,
            schedule_config={"time": "00:00"},
        )

        scheduled_sync_id = str(scheduled_sync.id)

        # Unschedule it
        self.service.unschedule_sync(
            scheduled_sync_id=scheduled_sync_id, tenant_id=str(self.tenant.id)
        )

        # Verify it was deleted
        with self.assertRaises(ScheduledMarketplaceSync.DoesNotExist):
            ScheduledMarketplaceSync.objects.get(id=scheduled_sync_id)

    def test_unschedule_sync_not_found(self):
        """Test error handling when scheduled sync not found"""
        fake_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError):
            self.service.unschedule_sync(scheduled_sync_id=fake_id, tenant_id=str(self.tenant.id))

    @override_settings(EVENT_BUS_ASYNC_PERSISTENCE=False)
    def test_schedule_sync_creates_audit_event(self):
        """Test that schedule_sync emits SCHEDULED_SYNC_CREATED audit event."""
        schedule_config = {"time": "02:00"}
        scheduled_sync = self.service.schedule_sync(
            connection_id=str(self.connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Audit Test Scheduled Sync",
            direction=SyncDirection.PUSH.value,
            schedule_type=ScheduleType.DAILY.value,
            schedule_config=schedule_config,
            sync_options={"asset_ids": ["asset-1"]},
        )

        # Audit event is created synchronously (EVENT_BUS_ASYNC_PERSISTENCE=False).
        audit_events = AuditEvent.objects.filter(
            resource_type="SCHEDULED_MARKETPLACE_SYNC",
            action="SCHEDULED_SYNC_CREATED",
            resource_id=str(scheduled_sync.id),
        )
        self.assertEqual(audit_events.count(), 1,
            "Expected exactly one SCHEDULED_SYNC_CREATED audit event")
        audit_event = audit_events.first()
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertEqual(audit_event.tenant, self.tenant)
        self.assertEqual(audit_event.result, "SUCCESS")

    @override_settings(EVENT_BUS_ASYNC_PERSISTENCE=False)
    def test_unschedule_sync_creates_audit_event(self):
        """Test that unschedule_sync emits SCHEDULED_SYNC_DELETED audit event."""
        import time

        scheduled_sync = self.service.schedule_sync(
            connection_id=str(self.connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Audit Unschedule Test",
            direction=SyncDirection.PUSH.value,
            schedule_type=ScheduleType.DAILY.value,
            schedule_config={"time": "00:00"},
        )
        scheduled_sync_id = str(scheduled_sync.id)

        self.service.unschedule_sync(
            scheduled_sync_id=scheduled_sync_id, tenant_id=str(self.tenant.id)
        )

        time.sleep(0.05)  # noqa: sleep-needed  # INTENTIONAL: test-specific timing requirement
        audit_events = AuditEvent.objects.filter(
            resource_type="SCHEDULED_MARKETPLACE_SYNC",
            action="SCHEDULED_SYNC_DELETED",
            resource_id=scheduled_sync_id,
        )
        self.assertEqual(audit_events.count(), 1,
            "Expected exactly one SCHEDULED_SYNC_CREATED audit event")
        audit_event = audit_events.first()
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertEqual(audit_event.tenant, self.tenant)
        self.assertEqual(audit_event.result, "SUCCESS")

    def test_schedule_sync_calculates_next_run_at(self):
        """Test that next_run_at is calculated correctly"""
        schedule_config = {"time": "14:30"}  # 2:30 PM

        scheduled_sync = self.service.schedule_sync(
            connection_id=str(self.connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Next Run Test",
            direction=SyncDirection.PUSH.value,
            schedule_type=ScheduleType.DAILY.value,
            schedule_config=schedule_config,
        )

        # Verify next_run_at is set and in the future
        self.assertIsNotNone(scheduled_sync.next_run_at)
        self.assertGreater(scheduled_sync.next_run_at, timezone.now())

        # Verify time is correct (within same day or next day)
        if scheduled_sync.next_run_at.date() == timezone.now().date():
            # Same day - should be at 14:30
            self.assertEqual(scheduled_sync.next_run_at.hour, 14)
            self.assertEqual(scheduled_sync.next_run_at.minute, 30)
        else:
            # Next day - should also be at 14:30
            self.assertEqual(scheduled_sync.next_run_at.hour, 14)
            self.assertEqual(scheduled_sync.next_run_at.minute, 30)


class ScheduledSyncSchedulerWithStubConnectorTest(TestCase):
    """Tests for scheduled sync scheduler integration.

    Uses a TestMarketplaceConnector stub registered in the factory
    to exercise the full scheduling pipeline (schedule → process →
    sync job creation) without external marketplace dependencies.
    """

    def setUp(self):
        """Set up test fixtures"""
        _disconnect_semantic_signals()

        # Clean up any scheduled syncs left by prior test classes
        # (transaction=True means Django TestCase doesn't roll back between classes)
        ScheduledMarketplaceSync.objects.all().delete()

        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant)
        self.service = MarketplaceIntegrationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            name="Test Connection",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            is_active=True,
        )
        self.connection.set_config(
            {"api_key": "test-api-key", "endpoint": "https://api.example.com"}
        )

        # Register test connector
        from hub.apps.integrations.factory import MarketplaceConnectorFactory
        from hub.apps.integrations.tests.test_tasks import TestMarketplaceConnector

        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, TestMarketplaceConnector
        )

    def tearDown(self):
        """Clean up after tests"""
        from hub.apps.integrations.factory import MarketplaceConnectorFactory

        with contextlib.suppress(ValueError):
            MarketplaceConnectorFactory.unregister_connector(
                MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
            )
        # Reconnect semantic signals after test
        _reconnect_semantic_signals()

    def test_process_scheduled_syncs_triggers_due_sync(self):
        """Test that process_scheduled_syncs triggers due syncs"""
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-1",
            name="Test Asset 1",
            description="Test asset description",
        )

        # Create scheduled sync that's due (next_run_at in the past)
        # First create it, then update next_run_at to bypass the save() calculation
        scheduled_sync = ScheduledMarketplaceSync.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            name="Due Sync Test",
            direction=SyncDirection.PUSH.value,
            schedule_type=ScheduleType.DAILY.value,
            schedule_config={"time": "00:00"},
            sync_options={"asset_ids": [str(asset.id)], "options": {}},
            status=ScheduledMarketplaceSyncStatus.ACTIVE,
            created_by=self.user,
        )
        # Override next_run_at after creation to make it due
        scheduled_sync.next_run_at = timezone.now() - timedelta(minutes=1)
        scheduled_sync.save(update_fields=["next_run_at"])

        # Get initial sync job count
        initial_job_count = MarketplaceSyncJob.objects.filter(
            tenant=self.tenant, connection=self.connection
        ).count()

        # Process scheduled syncs - uses real service with test connector
        result = process_scheduled_syncs()

        # Verify sync was triggered
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["failed"], 0)

        # Verify sync job was created
        final_job_count = MarketplaceSyncJob.objects.filter(
            tenant=self.tenant, connection=self.connection
        ).count()
        self.assertEqual(final_job_count, initial_job_count + 1)

        # Verify scheduled sync was updated
        scheduled_sync.refresh_from_db()
        self.assertIsNotNone(scheduled_sync.last_run_at)
        self.assertIsNotNone(scheduled_sync.last_sync_job_id)
        self.assertGreater(scheduled_sync.next_run_at, timezone.now())

        # Verify sync job exists and is linked
        sync_job = MarketplaceSyncJob.objects.get(id=scheduled_sync.last_sync_job_id)
        self.assertEqual(sync_job.direction, SyncDirection.PUSH.value)
        self.assertEqual(sync_job.connection, self.connection)

    def test_process_scheduled_syncs_skips_not_due(self):
        """Test that process_scheduled_syncs skips syncs that are not due"""
        # Create scheduled sync that's not due (next_run_at in the future)
        scheduled_sync = ScheduledMarketplaceSync.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            name="Not Due Sync Test",
            direction=SyncDirection.PUSH.value,
            schedule_type=ScheduleType.DAILY.value,
            schedule_config={"time": "00:00"},
            sync_options={"asset_ids": ["asset-1"]},
            status=ScheduledMarketplaceSyncStatus.ACTIVE,
            next_run_at=timezone.now() + timedelta(hours=1),  # Due in 1 hour
            created_by=self.user,
        )

        # Get initial sync job count
        initial_job_count = MarketplaceSyncJob.objects.filter(
            tenant=self.tenant, connection=self.connection
        ).count()

        # Process scheduled syncs - uses real service with test connector
        result = process_scheduled_syncs()

        # Verify sync was not triggered
        self.assertEqual(result["processed"], 0)
        self.assertEqual(result["failed"], 0)

        # Verify no sync job was created
        final_job_count = MarketplaceSyncJob.objects.filter(
            tenant=self.tenant, connection=self.connection
        ).count()
        self.assertEqual(final_job_count, initial_job_count)

        # Verify scheduled sync was not updated
        scheduled_sync.refresh_from_db()
        self.assertIsNone(scheduled_sync.last_run_at)
        self.assertIsNone(scheduled_sync.last_sync_job_id)

    def test_process_scheduled_syncs_skips_paused(self):
        """Test that process_scheduled_syncs skips paused syncs"""
        # Create paused scheduled sync that's due
        scheduled_sync = ScheduledMarketplaceSync.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            name="Paused Sync Test",
            direction=SyncDirection.PUSH.value,
            schedule_type=ScheduleType.DAILY.value,
            schedule_config={"time": "00:00"},
            sync_options={"asset_ids": ["asset-1"]},
            status=ScheduledMarketplaceSyncStatus.PAUSED,
            next_run_at=timezone.now() - timedelta(minutes=1),  # Due but paused
            created_by=self.user,
        )

        # Get initial sync job count
        initial_job_count = MarketplaceSyncJob.objects.filter(
            tenant=self.tenant, connection=self.connection
        ).count()

        # Process scheduled syncs - uses real service with test connector
        result = process_scheduled_syncs()

        # Verify sync was not triggered
        self.assertEqual(result["processed"], 0)
        self.assertEqual(result["failed"], 0)

        # Verify no sync job was created
        final_job_count = MarketplaceSyncJob.objects.filter(
            tenant=self.tenant, connection=self.connection
        ).count()
        self.assertEqual(final_job_count, initial_job_count)

        # Verify scheduled sync was not updated
        scheduled_sync.refresh_from_db()
        self.assertIsNone(scheduled_sync.last_run_at)
        self.assertIsNone(scheduled_sync.last_sync_job_id)

    def test_process_scheduled_syncs_handles_errors(self):
        """Test that process_scheduled_syncs handles misconfigured syncs gracefully"""
        # Create scheduled sync with PUSH direction but no asset_ids - triggers error branch
        scheduled_sync = ScheduledMarketplaceSync.objects.create(
            tenant=self.tenant,
            connection=self.connection,
            name="Error Sync Test",
            direction=SyncDirection.PUSH.value,
            schedule_type=ScheduleType.DAILY.value,
            schedule_config={"time": "00:00"},
            sync_options={},  # No asset_ids for PUSH - process_scheduled_syncs records failure
            status=ScheduledMarketplaceSyncStatus.ACTIVE,
            created_by=self.user,
        )
        scheduled_sync.next_run_at = timezone.now() - timedelta(minutes=1)
        scheduled_sync.save(update_fields=["next_run_at"])

        result = process_scheduled_syncs()

        self.assertEqual(result["processed"], 0)
        self.assertEqual(result["failed"], 1)
        self.assertEqual(len(result["errors"]), 1)
        self.assertIn("scheduled_sync_id", result["errors"][0])
        self.assertEqual(result["errors"][0]["scheduled_sync_id"], str(scheduled_sync.id))


class ScheduledSyncStubConnectorEndToEndTest(TestCase):
    """End-to-end tests for scheduled sync execution using a stub connector.

    Uses a TestMarketplaceConnector stub to verify the full scheduled
    sync lifecycle: schedule → due-detection → process → sync job
    creation → next_run_at update.  No real marketplace API calls.
    """

    def setUp(self):
        """Set up test fixtures"""
        _disconnect_semantic_signals()

        # Clean up any scheduled syncs left by prior test classes
        # (transaction=True means Django TestCase doesn't roll back between classes)
        ScheduledMarketplaceSync.objects.all().delete()

        self.tenant = TenantFactory.create_tenant()
        self.user = UserFactory.create_user(tenant=self.tenant)
        self.service = MarketplaceIntegrationService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )
        self.connection = MarketplaceConnection.objects.create(
            tenant=self.tenant,
            name="Test Connection",
            marketplace_type=MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            is_active=True,
        )
        self.connection.set_config(
            {"api_key": "test-api-key", "endpoint": "https://api.example.com"}
        )

        # Register test connector
        from hub.apps.integrations.factory import MarketplaceConnectorFactory
        from hub.apps.integrations.tests.test_tasks import TestMarketplaceConnector

        MarketplaceConnectorFactory.register_connector(
            MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE, TestMarketplaceConnector
        )

    def tearDown(self):
        """Clean up after tests"""
        from hub.apps.integrations.factory import MarketplaceConnectorFactory

        with contextlib.suppress(ValueError):
            MarketplaceConnectorFactory.unregister_connector(
                MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE
            )
        # Reconnect semantic signals after test
        _reconnect_semantic_signals()

    def test_scheduled_sync_e2e_push(self):
        """Test end-to-end scheduled sync execution for PUSH"""
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-1",
            name="Test Asset 1",
            description="Test asset description",
        )

        # Schedule sync
        scheduled_sync = self.service.schedule_sync(
            connection_id=str(self.connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="E2E Push Test",
            direction=SyncDirection.PUSH.value,
            schedule_type=ScheduleType.DAILY.value,
            schedule_config={"time": "00:00"},
            sync_options={"asset_ids": [str(asset.id)], "options": {}},
        )

        # Set next_run_at to past to make it due
        scheduled_sync.next_run_at = timezone.now() - timedelta(minutes=1)
        scheduled_sync.save()

        # Process scheduled syncs (this will trigger real sync)
        result = process_scheduled_syncs()

        # Verify sync was processed
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["failed"], 0)

        # Verify scheduled sync was updated
        scheduled_sync.refresh_from_db()
        self.assertIsNotNone(scheduled_sync.last_run_at)
        self.assertIsNotNone(scheduled_sync.last_sync_job_id)

        # Verify sync job was created
        sync_job = MarketplaceSyncJob.objects.get(id=scheduled_sync.last_sync_job_id)
        self.assertEqual(sync_job.direction, SyncDirection.PUSH.value)
        self.assertEqual(sync_job.connection, self.connection)

    def test_scheduled_sync_e2e_pull(self):
        """Test end-to-end scheduled sync execution for PULL"""
        # Schedule sync
        scheduled_sync = self.service.schedule_sync(
            connection_id=str(self.connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="E2E Pull Test",
            direction=SyncDirection.PULL.value,
            schedule_type=ScheduleType.DAILY.value,
            schedule_config={"time": "00:00"},
            sync_options={"listing_ids": ["listing-1", "listing-2"], "options": {}},
        )

        # Set next_run_at to past to make it due
        scheduled_sync.next_run_at = timezone.now() - timedelta(minutes=1)
        scheduled_sync.save()

        # Process scheduled syncs
        result = process_scheduled_syncs()

        # Verify sync was processed
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["failed"], 0)

        # Verify scheduled sync was updated
        scheduled_sync.refresh_from_db()
        self.assertIsNotNone(scheduled_sync.last_run_at)
        self.assertIsNotNone(scheduled_sync.last_sync_job_id)

        # Verify sync job was created
        sync_job = MarketplaceSyncJob.objects.get(id=scheduled_sync.last_sync_job_id)
        self.assertEqual(sync_job.direction, SyncDirection.PULL.value)

    def test_scheduled_sync_e2e_bidirectional(self):
        """Test end-to-end scheduled sync execution for BIDIRECTIONAL"""
        # Create asset
        asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-1",
            name="Test Asset 1",
            description="Test asset description",
        )

        # Schedule bidirectional sync
        scheduled_sync = self.service.schedule_sync(
            connection_id=str(self.connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="E2E Bidirectional Test",
            direction=SyncDirection.BIDIRECTIONAL.value,
            schedule_type=ScheduleType.DAILY.value,
            schedule_config={"time": "00:00"},
            sync_options={
                "asset_ids": [str(asset.id)],
                "listing_ids": ["listing-1"],
                "options": {},
            },
        )

        # Set next_run_at to past to make it due
        scheduled_sync.next_run_at = timezone.now() - timedelta(minutes=1)
        scheduled_sync.save()

        # Process scheduled syncs
        result = process_scheduled_syncs()

        # Verify sync was processed
        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["failed"], 0)

        # Verify scheduled sync was updated
        scheduled_sync.refresh_from_db()
        self.assertIsNotNone(scheduled_sync.last_run_at)
        self.assertIsNotNone(scheduled_sync.last_sync_job_id)

    def test_scheduled_sync_e2e_multiple_due_syncs(self):
        """Test end-to-end execution with multiple due syncs"""
        # Create multiple scheduled syncs
        asset1 = Asset.objects.create(tenant=self.tenant, key="test-asset-1", name="Test Asset 1")
        asset2 = Asset.objects.create(tenant=self.tenant, key="test-asset-2", name="Test Asset 2")

        scheduled_sync1 = self.service.schedule_sync(
            connection_id=str(self.connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="E2E Multi Test 1",
            direction=SyncDirection.PUSH.value,
            schedule_type=ScheduleType.DAILY.value,
            schedule_config={"time": "00:00"},
            sync_options={"asset_ids": [str(asset1.id)]},
        )
        scheduled_sync1.next_run_at = timezone.now() - timedelta(minutes=1)
        scheduled_sync1.save()

        scheduled_sync2 = self.service.schedule_sync(
            connection_id=str(self.connection.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="E2E Multi Test 2",
            direction=SyncDirection.PUSH.value,
            schedule_type=ScheduleType.DAILY.value,
            schedule_config={"time": "00:00"},
            sync_options={"asset_ids": [str(asset2.id)]},
        )
        scheduled_sync2.next_run_at = timezone.now() - timedelta(minutes=1)
        scheduled_sync2.save()

        # Process scheduled syncs
        result = process_scheduled_syncs()

        # Verify both syncs were processed
        self.assertEqual(result["processed"], 2)
        self.assertEqual(result["failed"], 0)

        # Verify both scheduled syncs were updated
        scheduled_sync1.refresh_from_db()
        scheduled_sync2.refresh_from_db()
        self.assertIsNotNone(scheduled_sync1.last_run_at)
        self.assertIsNotNone(scheduled_sync2.last_run_at)
