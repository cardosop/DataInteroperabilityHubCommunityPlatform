"""
Integration tests for ObservabilityEventPublisher.

Tests event publishing using real EventPublisher and EventBus (no mocks/stubs).
All tests use real services and models following engineering best practices.
"""

import uuid

from django.test import TestCase, override_settings
from django.utils import timezone

from hub.apps.core.events.models import Event
from hub.apps.core.events.service_publishers import ObservabilityEventPublisher
from hub.apps.tenants.models import KYCStatus, Tenant, TenantStatus
from hub.apps.users.models import User, UserStatus

uid = uuid.uuid4().hex[:8]


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Disable async persistence for tests
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,  # Disable write-behind for tests
)
class ObservabilityEventPublisherIntegrationTest(TestCase):
    """Integration tests for ObservabilityEventPublisher using real EventPublisher."""

    def setUp(self):
        """Set up test fixtures."""
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
            region="us-east-1",
        )
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        # Create a test service with ObservabilityEventPublisher
        class TestObservabilityService(ObservabilityEventPublisher):
            def __init__(self, tenant_id=None, user_id=None):
                self.tenant_id = tenant_id
                self.user_id = user_id
                super().__init__(tenant_id=tenant_id, user_id=user_id)

        self.service = TestObservabilityService(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_publish_metric_recorded_event(self):
        """Test publishing observability.metric.recorded event with real EventPublisher."""
        run_id = uuid.uuid4().hex[:8]
        metric_name = f"http_requests_total_{run_id}"
        metric_value = 100.0
        metric_type = "counter"
        labels = {"method": "GET", "status": "200", "run_id": run_id}

        event_id = self.service.publish_metric_recorded(
            metric_name=metric_name,
            metric_value=metric_value,
            metric_type=metric_type,
            labels=labels,
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted to database
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "observability.metric.recorded")
        self.assertEqual(event.data["metric_name"], metric_name)
        self.assertEqual(event.data["metric_value"], metric_value)
        self.assertEqual(event.data["metric_type"], metric_type)
        self.assertEqual(event.data["labels"], labels)
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))
        self.assertEqual(event.source_service, "observability_service")

    def test_publish_metric_recorded_with_minimal_data(self):
        """Test publishing observability.metric.recorded event with only required fields."""
        run_id = uuid.uuid4().hex[:8]
        metric_name = f"test_metric_minimal_{run_id}"
        event_id = self.service.publish_metric_recorded(metric_name=metric_name)

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "observability.metric.recorded")
        self.assertEqual(event.data["metric_name"], metric_name)
        self.assertIsNone(event.data.get("metric_value"))
        self.assertIsNone(event.data.get("metric_type"))
        self.assertIsNone(event.data.get("labels"))

    def test_publish_trace_created_event(self):
        """Test publishing observability.trace.created event with real EventPublisher."""
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())
        operation_name = "http_request"
        duration_ms = 150.5
        status = "ok"
        attributes = {"http.method": "GET", "http.status_code": 200}

        event_id = self.service.publish_trace_created(
            trace_id=trace_id,
            span_id=span_id,
            operation_name=operation_name,
            duration_ms=duration_ms,
            status=status,
            attributes=attributes,
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "observability.trace.created")
        self.assertEqual(event.data["trace_id"], trace_id)
        self.assertEqual(event.data["span_id"], span_id)
        self.assertEqual(event.data["operation_name"], operation_name)
        self.assertEqual(event.data["duration_ms"], duration_ms)
        self.assertEqual(event.data["status"], status)
        self.assertEqual(event.data["attributes"], attributes)

    def test_publish_trace_created_with_minimal_data(self):
        """Test publishing observability.trace.created event with only required fields."""
        trace_id = str(uuid.uuid4())
        span_id = str(uuid.uuid4())

        event_id = self.service.publish_trace_created(trace_id=trace_id, span_id=span_id)

        # Verify event was published
        self.assertIsNotNone(event_id)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "observability.trace.created")
        self.assertEqual(event.data["trace_id"], trace_id)
        self.assertEqual(event.data["span_id"], span_id)
        self.assertIsNone(event.data.get("operation_name"))
        self.assertIsNone(event.data.get("duration_ms"))
        self.assertIsNone(event.data.get("status"))
        self.assertIsNone(event.data.get("attributes"))

    def test_publish_log_created_event(self):
        """Test publishing observability.log.created event with real EventPublisher."""
        run_id = uuid.uuid4().hex[:8]
        log_level = "INFO"
        message = f"User logged in successfully {run_id}"
        logger_name = "hub.apps.auth"
        context = {"user_id": str(uuid.uuid4()), "ip_address": "192.168.1.1"}

        event_id = self.service.publish_log_created(
            log_level=log_level, message=message, logger_name=logger_name, context=context
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "observability.log.created")
        self.assertEqual(event.data["log_level"], log_level)
        self.assertEqual(event.data["message"], message)
        self.assertEqual(event.data["logger_name"], logger_name)
        self.assertEqual(event.data["context"], context)

    def test_publish_log_created_with_minimal_data(self):
        """Test publishing observability.log.created event with only required fields."""
        run_id = uuid.uuid4().hex[:8]
        message = f"Test log message {run_id}"
        event_id = self.service.publish_log_created(message=message)

        # Verify event was published
        self.assertIsNotNone(event_id)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "observability.log.created")
        self.assertEqual(event.data["message"], message)
        self.assertIsNone(event.data.get("log_level"))
        self.assertIsNone(event.data.get("logger_name"))
        self.assertIsNone(event.data.get("context"))

    def test_publish_alert_triggered_event(self):
        """Test publishing observability.alert.triggered event with real EventPublisher."""
        alert_name = "high_error_rate"
        alert_severity = "critical"
        alert_message = "Error rate exceeded threshold"
        metric_name = "error_rate"
        threshold_value = 0.05
        current_value = 0.08
        triggered_at = timezone.now().isoformat()

        event_id = self.service.publish_alert_triggered(
            alert_name=alert_name,
            alert_severity=alert_severity,
            alert_message=alert_message,
            metric_name=metric_name,
            threshold_value=threshold_value,
            current_value=current_value,
            triggered_at=triggered_at,
        )

        # Verify event was published
        self.assertIsNotNone(event_id)
        self.assertIsInstance(event_id, str)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "observability.alert.triggered")
        self.assertEqual(event.data["alert_name"], alert_name)
        self.assertEqual(event.data["alert_severity"], alert_severity)
        self.assertEqual(event.data["alert_message"], alert_message)
        self.assertEqual(event.data["metric_name"], metric_name)
        self.assertEqual(event.data["threshold_value"], threshold_value)
        self.assertEqual(event.data["current_value"], current_value)
        self.assertEqual(event.data["triggered_at"], triggered_at)

    def test_publish_alert_triggered_with_auto_timestamp(self):
        """Test publishing observability.alert.triggered event with auto-generated timestamp."""
        before_publish = timezone.now()
        event_id = self.service.publish_alert_triggered(
            alert_name="test_alert", alert_severity="warning", alert_message="Test alert message"
        )
        after_publish = timezone.now()

        # Verify event was published
        self.assertIsNotNone(event_id)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "observability.alert.triggered")
        self.assertIsNotNone(event.data.get("triggered_at"))
        # Verify timestamp is within reasonable range
        triggered_at = timezone.datetime.fromisoformat(
            event.data["triggered_at"].replace("Z", "+00:00")
        )
        self.assertGreaterEqual(triggered_at, before_publish)
        self.assertLessEqual(triggered_at, after_publish)

    def test_publish_alert_triggered_with_minimal_data(self):
        """Test publishing observability.alert.triggered event with only required fields."""
        event_id = self.service.publish_alert_triggered(
            alert_name="test_alert", alert_severity="info"
        )

        # Verify event was published
        self.assertIsNotNone(event_id)

        # Verify event was persisted
        event = Event.objects.get(event_id=event_id)
        self.assertEqual(event.event_type, "observability.alert.triggered")
        self.assertEqual(event.data["alert_name"], "test_alert")
        self.assertEqual(event.data["alert_severity"], "info")
        self.assertIsNone(event.data.get("alert_message"))
        self.assertIsNone(event.data.get("metric_name"))
        self.assertIsNone(event.data.get("threshold_value"))
        self.assertIsNone(event.data.get("current_value"))

    def test_event_publisher_uses_service_tenant_user(self):
        """Test that event publisher uses service tenant_id and user_id by default."""
        run_id = uuid.uuid4().hex[:8]
        event_id = self.service.publish_metric_recorded(metric_name=f"test_metric_svc_{run_id}")

        event = Event.objects.get(event_id=event_id)
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))

    def test_event_publisher_allows_override_tenant_user(self):
        """Test that event publisher allows overriding tenant_id and user_id via kwargs."""
        run_id = uuid.uuid4().hex[:8]
        other_tenant = Tenant.objects.create(
            name=f"Other Tenant {run_id}",
            slug=f"other-tenant-{run_id}",
            status=TenantStatus.ACTIVE,
            kyc_status=KYCStatus.VERIFIED,
            region="us-west-2",
        )
        other_user = User.objects.create_user(
            email=f"other-{run_id}@example.com",
            password="testpass123",
            tenant=other_tenant,
            status=UserStatus.ACTIVE,
        )

        event_id = self.service.publish_metric_recorded(
            metric_name=f"test_metric_override_{run_id}",
            tenant_id=str(other_tenant.id),
            user_id=str(other_user.id),
        )

        event = Event.objects.get(event_id=event_id)
        self.assertEqual(str(event.tenant_id), str(other_tenant.id))
        self.assertEqual(str(event.user_id), str(other_user.id))
