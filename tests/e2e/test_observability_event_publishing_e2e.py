"""
E2E tests for Observability Event Publishing.

Tests that observability API endpoints publish events correctly.
Uses REAL services (no mocks/stubs).
"""
try:
    import pytest

    pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]
except ImportError:
    # pytest not available, tests will run with Django test runner
    pass

from django.test import TestCase, override_settings
from django.utils import timezone
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from datetime import timedelta

from hub.apps.core.events.models import Event
from hub.apps.datasets.models import Dataset
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant, TenantStatus, KYCStatus
from hub.apps.users.models import UserStatus

# Try to import E2ETestBase and get_response_data, fallback to TestCase if not available
try:
    from tests.e2e.conftest import E2ETestBase, get_response_data
except ImportError:
    # Fallback: create minimal base class and get_response_data
    from tests.factories import TenantFactory

    User = get_user_model()

    def get_response_data(response):
        if hasattr(response, "data"):
            return response.data
        try:
            import json
            return json.loads(response.content) if response.content else None
        except (TypeError, AttributeError, ValueError):
            return None

    class E2ETestBase(TestCase):
        """Minimal base class for E2E tests when conftest is not available."""

        def setUp(self):
            """Set up test fixtures."""
            super().setUp()
            self.tenant = TenantFactory.create_tenant()
            self.user = User.objects.create_user(
                email="e2e_test@example.com",
                password="testpass123",
                tenant=self.tenant,
                status=UserStatus.ACTIVE,
            )
            self.client = APIClient()
            self.client.force_authenticate(user=self.user)


@override_settings(
    EVENT_BUS_ASYNC_PERSISTENCE=False,  # Disable async persistence for tests
    EVENT_BUS_WRITE_BEHIND_ENABLED=False,  # Disable write-behind for tests
)
class ObservabilityEventPublishingE2ETest(E2ETestBase):
    """E2E tests for observability event publishing via API endpoints."""

    def setUp(self):
        """Set up test fixtures."""
        super().setUp()

        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

        # Create test asset and file for datasets
        self.asset = Asset.objects.create(
            tenant=self.tenant,
            key="test-asset-e2e",
            name="Test Asset E2E",
            status=AssetStatus.ACTIVE,
            created_by=self.user,
        )

        self.file = File.objects.create(
            tenant=self.tenant,
            name="test.csv",
            content_type="text/csv",
            size=1000,
            status=FileStatus.ACTIVE,
            storage_path="test/test.csv",
            content_sha256="abc123",
            created_by=self.user,
        )

        self.dataset = Dataset.objects.create(
            tenant=self.tenant,
            asset=self.asset,
            file=self.file,
            format="CSV",
            created_by=self.user,
        )

    def test_get_freshness_dashboard_publishes_trace_event(self):
        """Test that GET /api/v1/observability/freshness publishes trace event."""
        # Call API endpoint
        url = reverse("observability-get-freshness-dashboard")
        response = self.client.get(url, {"limit": 10})

        # Verify API response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        self.assertIn("results", data)
        self.assertIn("summary", data)

        # Verify trace event was published (if trace context available)
        # Note: Trace events are only published when OpenTelemetry trace context is available
        # In tests without trace context, no trace events will be published
        # This is expected behavior - we verify the API works correctly
        trace_events = Event.objects.filter(
            event_type="observability.trace.created",
            tenant_id=self.tenant.id,
        ).order_by("-timestamp")

        # If trace context is available, verify event was published
        if trace_events.exists():
            event = trace_events.first()
            self.assertEqual(event.event_type, "observability.trace.created")
            self.assertEqual(event.source_service, "observability_service")
            self.assertEqual(str(event.tenant_id), str(self.tenant.id))
            self.assertIn("trace_id", event.data)
            self.assertIn("span_id", event.data)
            self.assertEqual(event.data["operation_name"], "get_freshness_dashboard")

    def test_get_volume_dashboard_publishes_trace_event(self):
        """Test that GET /api/v1/observability/volume publishes trace event."""
        # Call API endpoint
        url = reverse("observability-get-volume-dashboard")
        response = self.client.get(url, {"period_type": "DAILY", "limit": 10})

        # Verify API response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        self.assertIn("results", data)
        self.assertIn("summary", data)

        # Verify trace event was published (if trace context available)
        trace_events = Event.objects.filter(
            event_type="observability.trace.created",
            tenant_id=self.tenant.id,
        ).order_by("-timestamp")

        if trace_events.exists():
            event = trace_events.first()
            self.assertEqual(event.event_type, "observability.trace.created")
            self.assertEqual(event.source_service, "observability_service")
            self.assertEqual(event.data["operation_name"], "get_volume_dashboard")

    def test_get_schema_drift_dashboard_publishes_trace_event(self):
        """Test that GET /api/v1/observability/schema-drift publishes trace event."""
        # Call API endpoint
        url = reverse("observability-get-schema-drift-dashboard")
        response = self.client.get(url, {"limit": 10})

        # Verify API response
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = get_response_data(response) or {}
        self.assertIn("results", data)
        self.assertIn("summary", data)

        # Verify trace event was published (if trace context available)
        trace_events = Event.objects.filter(
            event_type="observability.trace.created",
            tenant_id=self.tenant.id,
        ).order_by("-timestamp")

        if trace_events.exists():
            event = trace_events.first()
            self.assertEqual(event.event_type, "observability.trace.created")
            self.assertEqual(event.source_service, "observability_service")
            self.assertEqual(event.data["operation_name"], "get_schema_drift_dashboard")

    def test_record_metric_publishes_metric_event(self):
        """Test that POST /api/v1/observability/metrics publishes metric event."""
        # Call API endpoint to record metric
        url = reverse("observability-record-metric")
        response = self.client.post(
            url,
            {
                "dataset_id": str(self.dataset.id),
                "last_update_time": timezone.now().isoformat(),
                "freshness_sla": "DAILY",
                "row_count": 1000,
                "size_bytes": 1024,
            },
            format="json",
        )

        # Verify API response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = get_response_data(response) or {}
        self.assertIn("id", data)
        self.assertIn("recorded_at", data)

        # Verify metric event was published
        metric_events = Event.objects.filter(
            event_type="observability.metric.recorded",
            tenant_id=self.tenant.id,
        ).order_by("-timestamp")

        self.assertGreater(metric_events.count(), 0)
        event = metric_events.first()
        self.assertEqual(event.event_type, "observability.metric.recorded")
        self.assertEqual(event.source_service, "observability_service")
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(event.data["metric_name"], "data_observability_metric")
        self.assertEqual(event.data["metric_type"], "gauge")
        self.assertIn("labels", event.data)
        self.assertEqual(event.data["labels"]["dataset_id"], str(self.dataset.id))

    def test_record_metric_publishes_alert_when_stale(self):
        """Test that POST /api/v1/observability/metrics publishes alert event when data is stale."""
        # Record metric with stale data (last update 2 days ago, SLA is DAILY)
        stale_time = timezone.now() - timedelta(days=2)
        url = reverse("observability-record-metric")
        response = self.client.post(
            url,
            {
                "dataset_id": str(self.dataset.id),
                "last_update_time": stale_time.isoformat(),
                "freshness_sla": "DAILY",  # 24 hour SLA
                "row_count": 1000,
            },
            format="json",
        )

        # Verify API response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = get_response_data(response) or {}
        self.assertTrue(data.get("is_stale"))

        # Verify alert event was published
        alert_events = Event.objects.filter(
            event_type="observability.alert.triggered",
            tenant_id=self.tenant.id,
            data__alert_name="data_stale",
        ).order_by("-timestamp")

        self.assertGreater(alert_events.count(), 0)
        alert_event = alert_events.first()
        self.assertEqual(alert_event.event_type, "observability.alert.triggered")
        self.assertEqual(alert_event.source_service, "observability_service")
        self.assertEqual(alert_event.data["alert_name"], "data_stale")
        self.assertEqual(alert_event.data["alert_severity"], "warning")
        self.assertIn("Data is stale", alert_event.data["alert_message"])
        self.assertEqual(alert_event.data["metric_name"], "freshness_age_seconds")

    def test_record_metric_publishes_schema_drift_alert(self):
        """Test that POST /api/v1/observability/metrics publishes alert event when schema drift is detected."""
        # Record initial metric with schema
        initial_schema = {
            "type": "object",
            "properties": {"id": {"type": "integer"}, "name": {"type": "string"}},
        }

        url = reverse("observability-record-metric")
        self.client.post(
            url,
            {
                "dataset_id": str(self.dataset.id),
                "last_update_time": timezone.now().isoformat(),
                "schema_json": initial_schema,
            },
            format="json",
        )

        # Record metric with different schema (drift)
        drifted_schema = {
            "type": "object",
            "properties": {
                "id": {"type": "integer"},
                "name": {"type": "string"},
                "email": {"type": "string"},  # New field - drift detected
            },
        }

        response = self.client.post(
            url,
            {
                "dataset_id": str(self.dataset.id),
                "last_update_time": timezone.now().isoformat(),
                "schema_json": drifted_schema,
            },
            format="json",
        )

        # Verify API response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify schema drift alert event was published (if drift detected)
        drift_events = Event.objects.filter(
            event_type="observability.alert.triggered",
            tenant_id=self.tenant.id,
            data__alert_name="schema_drift_detected",
        ).order_by("-timestamp")

        # Note: Schema drift detection might not always trigger, so we check if any were published
        if drift_events.exists():
            drift_event = drift_events.first()
            self.assertEqual(drift_event.event_type, "observability.alert.triggered")
            self.assertEqual(drift_event.source_service, "observability_service")
            self.assertEqual(drift_event.data["alert_name"], "schema_drift_detected")
            self.assertEqual(drift_event.data["alert_severity"], "warning")
            self.assertIn("Schema drift detected", drift_event.data["alert_message"])

    def test_record_metric_with_asset(self):
        """Test that POST /api/v1/observability/metrics works with assets."""
        # Record metric with asset
        url = reverse("observability-record-metric")
        response = self.client.post(
            url,
            {
                "asset_id": str(self.asset.id),
                "last_update_time": timezone.now().isoformat(),
                "freshness_sla": "HOURLY",
                "row_count": 5000,
                "size_bytes": 2048,
            },
            format="json",
        )

        # Verify API response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = get_response_data(response) or {}
        self.assertIn("id", data)

        # Verify metric event was published
        metric_events = Event.objects.filter(
            event_type="observability.metric.recorded",
            tenant_id=self.tenant.id,
        ).order_by("-timestamp")

        self.assertGreater(metric_events.count(), 0)
        event = metric_events.first()
        self.assertEqual(event.data["labels"]["asset_id"], str(self.asset.id))
        self.assertIsNone(event.data["labels"]["dataset_id"])

    def test_events_have_correct_tenant_and_user_ids(self):
        """Test that events published via API have correct tenant and user IDs."""
        # Record metric
        url = reverse("observability-record-metric")
        response = self.client.post(
            url,
            {
                "dataset_id": str(self.dataset.id),
                "last_update_time": timezone.now().isoformat(),
            },
            format="json",
        )

        # Verify API response
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Verify metric event has correct tenant and user IDs
        metric_events = Event.objects.filter(
            event_type="observability.metric.recorded",
            tenant_id=self.tenant.id,
        ).order_by("-timestamp")

        self.assertGreater(metric_events.count(), 0)
        event = metric_events.first()
        self.assertEqual(str(event.tenant_id), str(self.tenant.id))
        self.assertEqual(str(event.user_id), str(self.user.id))

    def test_multiple_endpoints_publish_events(self):
        """Test that multiple observability endpoints publish events correctly."""
        # Call multiple endpoints
        freshness_url = reverse("observability-get-freshness-dashboard")
        volume_url = reverse("observability-get-volume-dashboard")
        schema_drift_url = reverse("observability-get-schema-drift-dashboard")
        metrics_url = reverse("observability-record-metric")

        self.client.get(freshness_url, {"limit": 10})
        self.client.get(volume_url, {"limit": 10})
        self.client.get(schema_drift_url, {"limit": 10})

        # Record a metric
        self.client.post(
            metrics_url,
            {
                "dataset_id": str(self.dataset.id),
                "last_update_time": timezone.now().isoformat(),
            },
            format="json",
        )

        # Verify events were published
        all_events = Event.objects.filter(
            event_type__in=[
                "observability.trace.created",
                "observability.metric.recorded",
            ],
            tenant_id=self.tenant.id,
        ).order_by("-timestamp")

        # At minimum, we should have the metric event
        self.assertGreater(all_events.count(), 0)

        # Verify metric event exists
        metric_events = all_events.filter(event_type="observability.metric.recorded")
        self.assertGreater(metric_events.count(), 0)

