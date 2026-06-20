"""
Comprehensive integration tests for event replay functionality.

Tests cover:
- Event replay API endpoint
- Event replay management command
- Rate limiting
- Authentication and authorization
- Idempotency (duplicate detection)
- Filtering (event_type, tenant_id, time range)
- Batch processing

All tests use real implementations (no mocks/stubs) per requirements.
"""

import uuid
from datetime import UTC, datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.core.events.bus import get_event_bus
from hub.apps.core.events.models import Event
from hub.apps.core.events.service_publishers import ODPSEventPublisher
from hub.apps.tenants.models import Tenant, TenantPlan
from hub.apps.users.models import Role, UserStatus

User = get_user_model()


def _set_statement_timeout(timeout_ms=120000):
    """Set a longer statement timeout for tests that use select_for_update."""
    with connection.cursor() as cursor:
        cursor.execute(f"SET statement_timeout = '{timeout_ms}'")


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Disable async persistence for tests
    EVENT_BUS_ENABLE_PERSISTENCE=True,  # Enable persistence
    RATE_LIMIT_ENABLED=True,  # Enable rate limiting for tests
)
class EventReplayAPITest(TestCase):
    """
    Integration tests for event replay API endpoint.
    """

    def setUp(self):
        """Set up test fixtures."""
        # Increase statement timeout for tests that hit select_for_update via API
        _set_statement_timeout(120000)

        cache.clear()

        self.tenant_id = str(uuid.uuid4())
        self.user_id = str(uuid.uuid4())
        self.admin_user_id = str(uuid.uuid4())
        unique_suffix = str(uuid.uuid4())[:8]

        # Create tenant
        self.tenant = Tenant.objects.create(
            id=self.tenant_id,
            name=f"Test Tenant {unique_suffix}",
            slug=f"test-tenant-{unique_suffix}",
        )

        # Create regular user
        self.user = User.objects.create_user(
            id=self.user_id,
            email=f"test-{unique_suffix}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create admin user
        self.admin_user = User.objects.create_user(
            id=self.admin_user_id,
            email=f"admin-{unique_suffix}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Assign TENANT_ADMIN role to admin user
        tenant_admin_role, _ = Role.objects.get_or_create(
            name="TENANT_ADMIN",
            tenant=self.tenant,
            defaults={"description": "Tenant Administrator"},
        )
        self.admin_user.user_roles.create(role=tenant_admin_role)

        # Create subscription so middleware doesn't block write ops
        free_plan = TenantPlan.objects.filter(slug="free").first()
        if free_plan:
            Subscription.objects.get_or_create(
                tenant=self.tenant,
                defaults={
                    "plan": free_plan,
                    "status": SubscriptionStatus.ACTIVE,
                    "stripe_subscription_id": f"sub_{uuid.uuid4().hex[:16]}",
                },
            )

        # Create API client
        self.client = APIClient()

        # Create publisher
        self.publisher = ODPSEventPublisher()
        self.publisher.tenant_id = self.tenant_id
        self.publisher.user_id = self.user_id

        from hub.apps.core.events.publisher import EventPublisher

        self.publisher._event_publisher = EventPublisher(
            service_name="odps_service", tenant_id=self.tenant_id, user_id=self.user_id
        )

        # Get event bus instance
        self.event_bus = get_event_bus()

    def tearDown(self):
        """Clean up after each test."""
        cache.clear()
        super().tearDown()

    def test_replay_events_requires_authentication(self):
        """Test that replay endpoint requires authentication."""
        url = reverse("events:replay-events")
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_replay_events_requires_admin_role(self):
        """Test that replay endpoint requires admin role."""
        self.client.force_authenticate(user=self.user)
        url = reverse("events:replay-events")
        response = self.client.post(url, {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_replay_events_success(self):
        """Test successful event replay."""
        # Create some events with distinct contract_ids
        event_ids = []
        for i in range(3):
            event_id = self.publisher.publish_odps_created(
                contract_id=str(uuid.uuid4()), status="DRAFT"
            )
            self.assertIsNotNone(event_id, f"Event {i} publish returned None")
            event_ids.append(event_id)

        # Verify all 3 events exist in DB before replaying
        db_count = Event.objects.filter(tenant_id=self.tenant_id).count()
        self.assertEqual(db_count, 3, f"Expected 3 events in DB, found {db_count}")

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        # Replay events
        url = reverse("events:replay-events")
        response = self.client.post(url, {"tenant_id": self.tenant_id, "limit": 10}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["success"])
        self.assertEqual(response.data["events_replayed"], 3)
        self.assertEqual(response.data["total_events_found"], 3)

    def test_replay_events_with_event_type_filter(self):
        """Test event replay with event_type filter."""
        # Create events of different types
        self.publisher.publish_odps_created(contract_id=str(uuid.uuid4()), status="DRAFT")
        self.publisher.publish_odps_updated(
            contract_id=str(uuid.uuid4()), changes={}, previous_status="DRAFT", new_status="ACTIVE"
        )

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        # Replay only odps.created events
        url = reverse("events:replay-events")
        response = self.client.post(
            url,
            {"event_type": "odps.created", "tenant_id": self.tenant_id, "limit": 10},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["events_replayed"], 1)
        self.assertEqual(response.data["total_events_found"], 1)

    def test_replay_events_with_time_range_filter(self):
        """Test event replay with time range filter."""
        # Create events at different times
        now = datetime.now(UTC)

        # Create event 2 hours ago
        event1_id = self.publisher.publish_odps_created(
            contract_id=str(uuid.uuid4()), status="DRAFT"
        )
        event1 = Event.objects.get(event_id=event1_id)
        event1.timestamp = now - timedelta(hours=2)
        event1.save()

        # Create event 1 hour ago
        event2_id = self.publisher.publish_odps_created(
            contract_id=str(uuid.uuid4()), status="DRAFT"
        )
        event2 = Event.objects.get(event_id=event2_id)
        event2.timestamp = now - timedelta(hours=1)
        event2.save()

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        # Replay events from last 90 minutes
        url = reverse("events:replay-events")
        response = self.client.post(
            url,
            {
                "tenant_id": self.tenant_id,
                "start_time": (now - timedelta(minutes=90)).isoformat(),
                "end_time": now.isoformat(),
                "limit": 10,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["events_replayed"], 1)  # Only event2
        self.assertEqual(response.data["total_events_found"], 1)

    def test_replay_events_rate_limiting(self):
        """Test that rate limiting works for event replay."""
        # Ensure clean cache to reset rate limit counters
        cache.clear()

        # Create an event
        self.publisher.publish_odps_created(contract_id=str(uuid.uuid4()), status="DRAFT")

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        url = reverse("events:replay-events")

        # Make 10 requests (should succeed)
        for _i in range(10):
            response = self.client.post(
                url, {"tenant_id": self.tenant_id, "limit": 1}, format="json"
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # 11th request should be rate limited
        response = self.client.post(url, {"tenant_id": self.tenant_id, "limit": 1}, format="json")
        self.assertEqual(response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertIn("RATE_LIMIT_EXCEEDED", response.data["error"]["code"])

    def test_replay_events_idempotency(self):
        """Test that replaying the same event twice skips duplicates."""
        # Create an event
        event_id = self.publisher.publish_odps_created(
            contract_id=str(uuid.uuid4()), status="DRAFT"
        )
        self.assertIsNotNone(event_id, "Event publish returned None")

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        url = reverse("events:replay-events")

        # First replay
        response1 = self.client.post(url, {"tenant_id": self.tenant_id, "limit": 10}, format="json")
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertEqual(response1.data["events_replayed"], 1)
        self.assertEqual(response1.data["events_skipped"], 0)

        # Second replay (should skip duplicate)
        response2 = self.client.post(url, {"tenant_id": self.tenant_id, "limit": 10}, format="json")
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertEqual(response2.data["events_replayed"], 0)
        self.assertEqual(response2.data["events_skipped"], 1)

    def test_replay_events_limit_parameter(self):
        """Test that limit parameter works correctly."""
        # Create 5 events
        for i in range(5):
            event_id = self.publisher.publish_odps_created(
                contract_id=str(uuid.uuid4()), status="DRAFT"
            )
            self.assertIsNotNone(event_id, f"Event {i} publish returned None")

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        # Replay with limit of 3
        url = reverse("events:replay-events")
        response = self.client.post(url, {"tenant_id": self.tenant_id, "limit": 3}, format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["events_replayed"], 3)
        self.assertEqual(response.data["total_events_found"], 5)

    def test_replay_events_max_limit_enforced(self):
        """Test that maximum limit (1000) is enforced."""
        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        # Try to replay with limit > 1000
        url = reverse("events:replay-events")
        response = self.client.post(
            url, {"tenant_id": self.tenant_id, "limit": 2000}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("limit", response.data["error"]["details"])

    def test_replay_events_no_events_found(self):
        """Test replay when no events match filters."""
        # Ensure clean cache to avoid rate limit state from prior tests
        cache.clear()

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)

        # Replay with filter that matches no events
        url = reverse("events:replay-events")
        response = self.client.post(
            url,
            {"event_type": "nonexistent.event", "tenant_id": self.tenant_id, "limit": 10},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["events_replayed"], 0)
        self.assertEqual(response.data["total_events_found"], 0)


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Disable async persistence for tests
    EVENT_BUS_ENABLE_PERSISTENCE=True,  # Enable persistence
)
class EventReplayCommandTest(TestCase):
    """
    Integration tests for event replay management command.
    """

    def setUp(self):
        """Set up test fixtures."""
        from django.core.management import call_command

        self.call_command = call_command

        cache.clear()

        self.tenant_id = str(uuid.uuid4())
        self.user_id = str(uuid.uuid4())
        unique_suffix = str(uuid.uuid4())[:8]

        # Create tenant
        self.tenant = Tenant.objects.create(
            id=self.tenant_id,
            name=f"Test Tenant {unique_suffix}",
            slug=f"test-tenant-{unique_suffix}",
        )

        # Create user
        self.user = User.objects.create_user(
            id=self.user_id,
            email=f"test-{unique_suffix}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )

        # Create publisher
        self.publisher = ODPSEventPublisher()
        self.publisher.tenant_id = self.tenant_id
        self.publisher.user_id = self.user_id

        from hub.apps.core.events.publisher import EventPublisher

        self.publisher._event_publisher = EventPublisher(
            service_name="odps_service", tenant_id=self.tenant_id, user_id=self.user_id
        )

    def tearDown(self):
        """Clean up after each test."""
        cache.clear()
        super().tearDown()

    def test_replay_command_dry_run(self):
        """Test replay command in dry-run mode."""
        # Create some events
        for _i in range(3):
            self.publisher.publish_odps_created(contract_id=str(uuid.uuid4()), status="DRAFT")

        # Run command in dry-run mode
        from io import StringIO

        out = StringIO()
        self.call_command("replay_events", "--tenant-id", self.tenant_id, "--dry-run", stdout=out)

        output = out.getvalue()
        self.assertIn("DRY RUN MODE", output)
        self.assertIn("Found 3 event(s)", output)

    def test_replay_command_success(self):
        """Test successful event replay command."""
        # Create some events
        event_ids = []
        for _i in range(3):
            event_id = self.publisher.publish_odps_created(
                contract_id=str(uuid.uuid4()), status="DRAFT"
            )
            event_ids.append(event_id)

        # Run command
        from io import StringIO

        out = StringIO()
        self.call_command(
            "replay_events", "--tenant-id", self.tenant_id, "--limit", "10", stdout=out
        )

        output = out.getvalue()
        self.assertIn("Found 3 event(s)", output)
        self.assertIn("Events replayed: 3", output)

    def test_replay_command_with_event_type_filter(self):
        """Test replay command with event_type filter."""
        # Create events of different types
        self.publisher.publish_odps_created(contract_id=str(uuid.uuid4()), status="DRAFT")
        self.publisher.publish_odps_updated(
            contract_id=str(uuid.uuid4()), changes={}, previous_status="DRAFT", new_status="ACTIVE"
        )

        # Run command with event_type filter
        from io import StringIO

        out = StringIO()
        self.call_command(
            "replay_events",
            "--tenant-id",
            self.tenant_id,
            "--event-type",
            "odps.created",
            "--limit",
            "10",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("Found 1 event(s)", output)
        self.assertIn("Events replayed: 1", output)

    def test_replay_command_with_time_range_filter(self):
        """Test replay command with time range filter."""
        # Create events at different times
        now = datetime.now(UTC)

        # Create event 2 hours ago
        event1_id = self.publisher.publish_odps_created(
            contract_id=str(uuid.uuid4()), status="DRAFT"
        )
        event1 = Event.objects.get(event_id=event1_id)
        event1.timestamp = now - timedelta(hours=2)
        event1.save()

        # Create event 1 hour ago
        event2_id = self.publisher.publish_odps_created(
            contract_id=str(uuid.uuid4()), status="DRAFT"
        )
        event2 = Event.objects.get(event_id=event2_id)
        event2.timestamp = now - timedelta(hours=1)
        event2.save()

        # Run command with time range filter
        from io import StringIO

        out = StringIO()
        start_time = (now - timedelta(minutes=90)).isoformat()
        end_time = now.isoformat()

        self.call_command(
            "replay_events",
            "--tenant-id",
            self.tenant_id,
            "--start-time",
            start_time,
            "--end-time",
            end_time,
            "--limit",
            "10",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("Found 1 event(s)", output)
        self.assertIn("Events replayed: 1", output)

    def test_replay_command_idempotency(self):
        """Test that replay command skips duplicates."""
        # Create an event
        self.publisher.publish_odps_created(contract_id=str(uuid.uuid4()), status="DRAFT")

        # First replay
        from io import StringIO

        out1 = StringIO()
        self.call_command(
            "replay_events", "--tenant-id", self.tenant_id, "--limit", "10", stdout=out1
        )

        output1 = out1.getvalue()
        self.assertIn("Events replayed: 1", output1)

        # Second replay (should skip duplicate)
        out2 = StringIO()
        self.call_command(
            "replay_events", "--tenant-id", self.tenant_id, "--limit", "10", stdout=out2
        )

        output2 = out2.getvalue()
        self.assertIn("Events skipped (duplicates): 1", output2)
        self.assertIn("Events replayed: 0", output2)

    def test_replay_command_batch_processing(self):
        """Test that replay command processes events in batches."""
        # Create 5 events
        for _i in range(5):
            self.publisher.publish_odps_created(contract_id=str(uuid.uuid4()), status="DRAFT")

        # Run command with batch size of 2
        from io import StringIO

        out = StringIO()
        self.call_command(
            "replay_events",
            "--tenant-id",
            self.tenant_id,
            "--batch-size",
            "2",
            "--limit",
            "10",
            stdout=out,
        )

        output = out.getvalue()
        self.assertIn("Found 5 event(s)", output)
        self.assertIn("Events replayed: 5", output)
        # Should show batch progress
        self.assertIn("Processing batch", output)
