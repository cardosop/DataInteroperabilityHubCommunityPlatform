"""
Comprehensive integration tests for dead letter queue functionality.

Tests cover:
- DLQ processor (retry logic, exponential backoff, resolution)
- DLQ management command
- DLQ API endpoints (list, retry, resolve)
- Authentication and authorization
- Pagination
- Filtering

All tests use real implementations (no mocks/stubs) per requirements.
"""
import uuid
from datetime import timedelta
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model
from django.db import connection
from django.core.cache import cache
from django.urls import reverse
from django.core.management import call_command
from django.utils import timezone
from io import StringIO
from rest_framework.test import APIClient
from rest_framework import status

from hub.apps.core.events.bus import get_event_bus
from hub.apps.core.events.models import Event, DeadLetterQueue
from hub.apps.core.events.dlq_processor import (
    retry_dlq_entry,
    resolve_dlq_entry,
    process_dlq_entries,
    should_retry_dlq_entry,
    calculate_retry_delay,
    DEFAULT_MAX_RETRIES,
)
from hub.apps.core.events.service_publishers import ODPSEventPublisher
from hub.apps.billing.models import Subscription, SubscriptionStatus
from hub.apps.tenants.models import Tenant, TenantPlan
from hub.apps.users.models import Role, UserStatus

User = get_user_model()


def _set_statement_timeout(timeout_ms=120000):
    """Set a longer statement timeout for tests that use select_for_update."""
    with connection.cursor() as cursor:
        cursor.execute(f"SET statement_timeout = '{timeout_ms}'")


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_ENABLE_PERSISTENCE=True,
)
class DLQProcessorTest(TestCase):
    """
    Integration tests for DLQ processor.
    """

    def setUp(self):
        """Set up test fixtures."""
        # Increase statement timeout for select_for_update safety
        _set_statement_timeout(120000)

        self.tenant_id = str(uuid.uuid4())
        self.user_id = str(uuid.uuid4())

        # Create tenant
        self.tenant = Tenant.objects.create(
            id=self.tenant_id,
            name=f"Test Tenant {uuid.uuid4()}",
            slug=f"test-tenant-{uuid.uuid4()}"
        )

        # Create user
        self.user = User.objects.create_user(
            id=self.user_id,
            email=f"test-{uuid.uuid4()}@example.com",
            password="testpass123",
            tenant=self.tenant
        )

        # Create subscription so middleware doesn't block write ops
        free_plan = TenantPlan.objects.filter(slug="free").first()
        if free_plan:
            Subscription.objects.get_or_create(
                tenant=self.tenant,
                defaults={
                    "plan": free_plan,
                    "status": SubscriptionStatus.ACTIVE,
                    "stripe_subscription_id": f"sub_{uuid.uuid4().hex[:16]}",
                }
            )

        # Create event bus
        self.event_bus = get_event_bus()

        cache.clear()

    def tearDown(self):
        """Clean up after each test."""
        cache.clear()

    def _publish_test_event(self):
        """Helper to publish a test event."""
        publisher = ODPSEventPublisher()
        publisher.tenant_id = self.tenant_id
        publisher.user_id = self.user_id

        from hub.apps.core.events.publisher import EventPublisher
        publisher._event_publisher = EventPublisher(
            service_name="test_service",
            tenant_id=self.tenant_id,
            user_id=self.user_id
        )

        event_id = publisher.publish_odps_created(
            contract_id=str(uuid.uuid4()),
            status="DRAFT"
        )
        return event_id

    def test_create_dlq_entry(self):
        """Test creating a DLQ entry."""
        event_data = {
            "event_id": str(uuid.uuid4()),
            "event_type": "odps.created",
            "event_version": "1.0.0",
            "timestamp": timezone.now().isoformat() + "Z",
            "source": {
                "service": "test_service",
                "tenant_id": self.tenant_id,
            },
            "data": {"contract_id": str(uuid.uuid4())},
            "metadata": {}
        }

        dlq_entry = DeadLetterQueue.objects.create(
            event=event_data,
            event_type="odps.created",
            subscriber="test_subscriber",
            error_message="Test error",
            error_details={"traceback": "test traceback"},
            retry_count=0
        )

        self.assertIsNotNone(dlq_entry.id)
        self.assertEqual(dlq_entry.event_type, "odps.created")
        self.assertEqual(dlq_entry.subscriber, "test_subscriber")
        self.assertEqual(dlq_entry.retry_count, 0)
        self.assertIsNone(dlq_entry.resolved_at)

    def test_retry_dlq_entry_success(self):
        """Test successfully retrying a DLQ entry."""
        # Increase statement timeout for select_for_update
        _set_statement_timeout(120000)

        # Create event and publish it
        event_id = self._publish_test_event()

        # Create DLQ entry with last_attempt_at set to None (or old enough time)
        event_data = Event.objects.get(event_id=event_id)
        dlq_entry = DeadLetterQueue.objects.create(
            event={
                "event_id": str(event_id),
                "event_type": event_data.event_type,
                "event_version": event_data.event_version,
                "timestamp": event_data.timestamp.isoformat() + "Z",
                "source": {
                    "service": event_data.source_service,
                    "tenant_id": str(event_data.tenant_id),
                },
                "data": event_data.data,
                "metadata": event_data.metadata or {}
            },
            event_type=event_data.event_type,
            subscriber="test_subscriber",
            error_message="Test error",
            retry_count=0
        )
        # Set last_attempt_at far enough back to pass the backoff check
        # (base delay for retry_count=0 is 60s, so 300s ensures we pass easily)
        old_time = timezone.now() - timedelta(seconds=300)
        DeadLetterQueue.objects.filter(id=dlq_entry.id).update(last_attempt_at=old_time)

        dlq_entry_id = str(dlq_entry.id)

        # Retry entry
        success, error_msg = retry_dlq_entry(dlq_entry_id, user_id=str(self.user_id))

        if not success:
            print(f"Retry failed with error: {error_msg}")

        self.assertTrue(success, f"Retry failed: {error_msg}")
        self.assertIsNone(error_msg)

        # Verify entry was updated
        dlq_entry.refresh_from_db()
        self.assertEqual(dlq_entry.retry_count, 1)
        self.assertIsNotNone(dlq_entry.last_attempt_at)

    def test_retry_dlq_entry_max_retries_exceeded(self):
        """Test retrying a DLQ entry that has exceeded max retries."""
        dlq_entry = DeadLetterQueue.objects.create(
            event={"event_id": str(uuid.uuid4()), "event_type": "odps.created", "data": {}},
            event_type="odps.created",
            subscriber="test_subscriber",
            error_message="Test error",
            retry_count=DEFAULT_MAX_RETRIES
        )

        success, error_msg = retry_dlq_entry(str(dlq_entry.id))

        self.assertFalse(success)
        self.assertIn("max retries", error_msg.lower())

    def test_retry_dlq_entry_already_resolved(self):
        """Test retrying a DLQ entry that is already resolved."""
        dlq_entry = DeadLetterQueue.objects.create(
            event={"event_id": str(uuid.uuid4()), "event_type": "odps.created", "data": {}},
            event_type="odps.created",
            subscriber="test_subscriber",
            error_message="Test error",
            resolved_at=timezone.now()
        )

        success, error_msg = retry_dlq_entry(str(dlq_entry.id))

        self.assertFalse(success)
        self.assertIn("resolved", error_msg.lower())

    def test_resolve_dlq_entry(self):
        """Test resolving a DLQ entry."""
        dlq_entry = DeadLetterQueue.objects.create(
            event={"event_id": str(uuid.uuid4()), "event_type": "odps.created", "data": {}},
            event_type="odps.created",
            subscriber="test_subscriber",
            error_message="Test error"
        )

        success, error_msg = resolve_dlq_entry(
            str(dlq_entry.id),
            user_id=str(self.user_id),
            resolution_notes="Manually resolved"
        )

        self.assertTrue(success)
        self.assertIsNone(error_msg)

        # Verify entry was resolved
        dlq_entry.refresh_from_db()
        self.assertIsNotNone(dlq_entry.resolved_at)
        self.assertEqual(str(dlq_entry.resolved_by), str(self.user_id))
        self.assertEqual(dlq_entry.error_details.get('resolution_notes'), "Manually resolved")

    def test_should_retry_dlq_entry(self):
        """Test should_retry_dlq_entry logic."""
        # Entry that should be retried (last_attempt_at old enough to pass backoff)
        entry1 = DeadLetterQueue.objects.create(
            event={"event_id": str(uuid.uuid4()), "event_type": "odps.created", "data": {}},
            event_type="odps.created",
            subscriber="test_subscriber",
            error_message="Test error",
            retry_count=0
        )
        # Set last_attempt_at far enough back (base delay for retry_count=0 is 60s)
        old_time = timezone.now() - timedelta(seconds=300)
        DeadLetterQueue.objects.filter(id=entry1.id).update(last_attempt_at=old_time)
        entry1.refresh_from_db()
        self.assertTrue(should_retry_dlq_entry(entry1))

        # Entry that exceeded max retries
        entry2 = DeadLetterQueue.objects.create(
            event={"event_id": str(uuid.uuid4()), "event_type": "odps.created", "data": {}},
            event_type="odps.created",
            subscriber="test_subscriber",
            error_message="Test error",
            retry_count=DEFAULT_MAX_RETRIES
        )
        self.assertFalse(should_retry_dlq_entry(entry2))

        # Entry that is resolved
        entry3 = DeadLetterQueue.objects.create(
            event={"event_id": str(uuid.uuid4()), "event_type": "odps.created", "data": {}},
            event_type="odps.created",
            subscriber="test_subscriber",
            error_message="Test error",
            resolved_at=timezone.now()
        )
        self.assertFalse(should_retry_dlq_entry(entry3))

    def test_calculate_retry_delay(self):
        """Test exponential backoff delay calculation."""
        # First retry: base delay
        delay1 = calculate_retry_delay(0, base_delay=60)
        self.assertEqual(delay1, 60)

        # Second retry: 2x base delay
        delay2 = calculate_retry_delay(1, base_delay=60)
        self.assertEqual(delay2, 120)

        # Third retry: 4x base delay
        delay3 = calculate_retry_delay(2, base_delay=60)
        self.assertEqual(delay3, 240)

        # Delay capped at max
        delay4 = calculate_retry_delay(10, base_delay=60, max_delay=3600)
        self.assertEqual(delay4, 3600)

    def test_process_dlq_entries(self):
        """Test processing multiple DLQ entries."""
        # Create multiple DLQ entries
        entries = []
        for i in range(5):
            entry = DeadLetterQueue.objects.create(
                event={"event_id": str(uuid.uuid4()), "event_type": "odps.created", "data": {}},
                event_type="odps.created",
                subscriber="test_subscriber",
                error_message=f"Test error {i}",
                retry_count=0
            )
            entries.append(entry)
        # Set last_attempt_at far enough back to pass the backoff check for all entries
        # (base delay for retry_count=0 is 60s, so 300s ensures we pass easily)
        old_time = timezone.now() - timedelta(seconds=300)
        DeadLetterQueue.objects.filter(id__in=[e.id for e in entries]).update(last_attempt_at=old_time)

        # Process entries (dry run)
        results = process_dlq_entries(max_entries=10, dry_run=True)

        self.assertEqual(results['total_found'], 5)
        self.assertEqual(results['processed'], 5)
        self.assertEqual(results['succeeded'], 0)  # Dry run doesn't actually retry


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_ENABLE_PERSISTENCE=True,
)
class DLQCommandTest(TestCase):
    """
    Integration tests for DLQ management command.
    """

    def setUp(self):
        """Set up test fixtures."""
        self.tenant_id = str(uuid.uuid4())

        # Create tenant
        self.tenant = Tenant.objects.create(
            id=self.tenant_id,
            name=f"Test Tenant {uuid.uuid4()}",
            slug=f"test-tenant-{uuid.uuid4()}"
        )

        cache.clear()

    def tearDown(self):
        """Clean up after each test."""
        cache.clear()

    def test_process_dlq_command_dry_run(self):
        """Test DLQ command in dry-run mode."""
        # Create DLQ entries
        for i in range(3):
            DeadLetterQueue.objects.create(
                event={"event_id": str(uuid.uuid4()), "event_type": "odps.created", "data": {}},
                event_type="odps.created",
                subscriber="test_subscriber",
                error_message=f"Test error {i}",
                retry_count=0
            )

        # Run command in dry-run mode
        out = StringIO()
        call_command('process_dlq', '--dry-run', stdout=out)

        output = out.getvalue()
        self.assertIn('DRY RUN MODE', output)
        self.assertIn('Found 3', output)

    def test_process_dlq_command_with_filters(self):
        """Test DLQ command with filters."""
        # Create DLQ entries with different event types
        DeadLetterQueue.objects.create(
            event={"event_id": str(uuid.uuid4()), "event_type": "odps.created", "data": {}},
            event_type="odps.created",
            subscriber="test_subscriber",
            error_message="Test error",
            retry_count=0
        )
        DeadLetterQueue.objects.create(
            event={"event_id": str(uuid.uuid4()), "event_type": "odps.updated", "data": {}},
            event_type="odps.updated",
            subscriber="test_subscriber",
            error_message="Test error",
            retry_count=0
        )

        # Run command with event_type filter
        out = StringIO()
        call_command('process_dlq', '--event-type', 'odps.created', '--dry-run', stdout=out)

        output = out.getvalue()
        self.assertIn('Found 1', output)

    def test_process_dlq_command_resolve(self):
        """Test DLQ command resolve option."""
        dlq_entry = DeadLetterQueue.objects.create(
            event={"event_id": str(uuid.uuid4()), "event_type": "odps.created", "data": {}},
            event_type="odps.created",
            subscriber="test_subscriber",
            error_message="Test error"
        )

        # Resolve entry
        out = StringIO()
        call_command('process_dlq', '--resolve', str(dlq_entry.id), stdout=out)

        # Verify entry was resolved
        dlq_entry.refresh_from_db()
        self.assertIsNotNone(dlq_entry.resolved_at)


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,
    EVENT_BUS_ENABLE_PERSISTENCE=True,
)
class DLQAPITest(TestCase):
    """
    Integration tests for DLQ API endpoints.
    """

    def setUp(self):
        """Set up test fixtures."""
        # Increase statement timeout for select_for_update in API views
        _set_statement_timeout(120000)

        self.tenant_id = str(uuid.uuid4())
        self.user_id = str(uuid.uuid4())
        self.admin_user_id = str(uuid.uuid4())
        unique_suffix = str(uuid.uuid4())[:8]

        # Create tenant
        self.tenant = Tenant.objects.create(
            id=self.tenant_id,
            name=f"Test Tenant {unique_suffix}",
            slug=f"test-tenant-{unique_suffix}"
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
            defaults={"description": "Tenant Administrator"}
        )
        self.admin_user.user_roles.create(
            role=tenant_admin_role
        )

        # Create subscription so middleware doesn't block write ops
        free_plan = TenantPlan.objects.filter(slug="free").first()
        if free_plan:
            Subscription.objects.get_or_create(
                tenant=self.tenant,
                defaults={
                    "plan": free_plan,
                    "status": SubscriptionStatus.ACTIVE,
                    "stripe_subscription_id": f"sub_{uuid.uuid4().hex[:16]}",
                }
            )

        # Create API client
        self.client = APIClient()

        cache.clear()

    def tearDown(self):
        """Clean up after each test."""
        cache.clear()

    def _publish_test_event(self):
        """Helper to publish a test event."""
        publisher = ODPSEventPublisher()
        publisher.tenant_id = self.tenant_id
        publisher.user_id = self.user_id

        from hub.apps.core.events.publisher import EventPublisher
        publisher._event_publisher = EventPublisher(
            service_name="test_service",
            tenant_id=self.tenant_id,
            user_id=self.user_id
        )

        event_id = publisher.publish_odps_created(
            contract_id=str(uuid.uuid4()),
            status="DRAFT"
        )
        return event_id

    def test_list_dlq_entries_unauthorized(self):
        """Test listing DLQ entries without authentication."""
        url = reverse('events:dlq-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_list_dlq_entries_forbidden(self):
        """Test listing DLQ entries without admin role."""
        self.client.force_authenticate(user=self.user)
        url = reverse('events:dlq-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_dlq_entries_success(self):
        """Test successfully listing DLQ entries."""
        # Create DLQ entries
        for i in range(5):
            DeadLetterQueue.objects.create(
                event={"event_id": str(uuid.uuid4()), "event_type": "odps.created", "data": {}},
                event_type="odps.created",
                subscriber="test_subscriber",
                error_message=f"Test error {i}",
                retry_count=0
            )

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('events:dlq-list')
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIn('count', response.data)
        self.assertEqual(len(response.data['results']), 5)

    def test_list_dlq_entries_with_filters(self):
        """Test listing DLQ entries with filters."""
        # Create DLQ entries with different event types
        DeadLetterQueue.objects.create(
            event={"event_id": str(uuid.uuid4()), "event_type": "odps.created", "data": {}},
            event_type="odps.created",
            subscriber="subscriber1",
            error_message="Test error",
            retry_count=0
        )
        DeadLetterQueue.objects.create(
            event={"event_id": str(uuid.uuid4()), "event_type": "odps.updated", "data": {}},
            event_type="odps.updated",
            subscriber="subscriber2",
            error_message="Test error",
            retry_count=0
        )

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('events:dlq-list')

        # Filter by event_type
        response = self.client.get(url, {'event_type': 'odps.created'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['event_type'], 'odps.created')

        # Filter by subscriber
        response = self.client.get(url, {'subscriber': 'subscriber1'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['subscriber'], 'subscriber1')

    def test_retry_dlq_entry_success(self):
        """Test successfully retrying a DLQ entry via API."""
        # Create a valid event first to get proper event structure
        event_id = self._publish_test_event()

        # Get the event from database
        event_data = Event.objects.get(event_id=event_id)

        # Create DLQ entry with proper event structure
        dlq_entry = DeadLetterQueue.objects.create(
            event={
                "event_id": str(event_id),
                "event_type": event_data.event_type,
                "event_version": event_data.event_version,
                "timestamp": event_data.timestamp.isoformat() + "Z",
                "source": {
                    "service": event_data.source_service,
                    "tenant_id": str(event_data.tenant_id),
                },
                "data": event_data.data,
                "metadata": event_data.metadata or {}
            },
            event_type=event_data.event_type,
            subscriber="test_subscriber",
            error_message="Test error",
            retry_count=0
        )
        # Set last_attempt_at far enough back to pass the backoff check
        old_time = timezone.now() - timedelta(seconds=300)
        DeadLetterQueue.objects.filter(id=dlq_entry.id).update(last_attempt_at=old_time)

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('events:dlq-retry', kwargs={'dlq_id': dlq_entry.id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['success'])

        # Verify entry was updated
        dlq_entry.refresh_from_db()
        self.assertEqual(dlq_entry.retry_count, 1)

    def test_retry_dlq_entry_not_found(self):
        """Test retrying a non-existent DLQ entry."""
        self.client.force_authenticate(user=self.admin_user)
        fake_id = uuid.uuid4()
        url = reverse('events:dlq-retry', kwargs={'dlq_id': fake_id})
        response = self.client.post(url)

        # Should return 400 (bad request) or 404 (not found) depending on when the error is detected
        self.assertIn(response.status_code, [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND])

    def test_resolve_dlq_entry_success(self):
        """Test successfully resolving a DLQ entry via API."""
        # Create DLQ entry (doesn't need valid event data for resolution)
        dlq_entry = DeadLetterQueue.objects.create(
            event={"event_id": str(uuid.uuid4()), "event_type": "odps.created", "data": {}},
            event_type="odps.created",
            subscriber="test_subscriber",
            error_message="Test error"
        )

        # Authenticate as admin
        self.client.force_authenticate(user=self.admin_user)
        url = reverse('events:dlq-resolve', kwargs={'dlq_id': dlq_entry.id})
        response = self.client.post(url, {'notes': 'Manually resolved'}, format='json')

        if response.status_code != status.HTTP_200_OK:
            # Access response content safely - DRF Response has .data,
            # but if the view returns an error, log it for debugging
            resp_data = getattr(response, 'data', None)
            if resp_data is None:
                import json
                resp_data = json.loads(response.content)
            print(f"Response status: {response.status_code}")
            print(f"Response data: {resp_data}")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Access response data - DRF Response always provides .data
        resp_data = getattr(response, 'data', None)
        if resp_data is None:
            import json
            resp_data = json.loads(response.content)
        self.assertTrue(resp_data['success'])

        # Verify entry was resolved
        dlq_entry.refresh_from_db()
        self.assertIsNotNone(dlq_entry.resolved_at)

    def test_resolve_dlq_entry_not_found(self):
        """Test resolving a non-existent DLQ entry."""
        self.client.force_authenticate(user=self.admin_user)
        fake_id = uuid.uuid4()
        url = reverse('events:dlq-resolve', kwargs={'dlq_id': fake_id})
        response = self.client.post(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

