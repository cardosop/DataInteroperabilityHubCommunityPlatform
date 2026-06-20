"""
Integration tests for Webhook API (Phase 12.2.2)

Tests for WebhookViewSet create and update endpoints via API
with real DB and real audit events. No mocks.
"""

import uuid

import pytest
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.audit.models import AuditEvent
from hub.apps.tenants.models import Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus
from hub.apps.webhooks.models import Webhook, WebhookDelivery, WebhookEventType, WebhookStatus

pytestmark = pytest.mark.django_db(transaction=True)


class WebhookAPIIntegrationTest(TestCase):
    """Test WebhookViewSet API endpoints with real DB and audit (Phase 12.2.2)"""

    reset_sequences = False
    serialized_rollback = False

    def _fixture_teardown(self):
        """Skip TRUNCATE CASCADE to avoid timeout."""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.client = APIClient()

        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}",
            slug=f"test-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        ensure_tenant_has_active_subscription(self.tenant)

        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.client.force_authenticate(user=self.user)

    def test_create_webhook_via_api(self):
        """Test creating webhook via API endpoint (Phase 12.2.2)"""
        initial_audit_count = AuditEvent.objects.filter(resource_type="WEBHOOK").count()

        response = self.client.post(
            "/api/v1/webhooks/webhooks/",
            {
                "name": "Test Webhook",
                "url": "https://example.com/webhook",
                "secret": "test-secret-key",
                "event_types": [WebhookEventType.ASSET_CREATED, WebhookEventType.CONTRACT_CREATED],
                "status": WebhookStatus.ACTIVE,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)

        webhook_id = response.data["id"]
        webhook = Webhook.objects.get(id=webhook_id)
        self.assertEqual(webhook.name, "Test Webhook")

        # Verify exactly one audit event was created (Phase 12.4.1)
        audit_events = AuditEvent.objects.filter(
            resource_type="WEBHOOK", action="WEBHOOK_CREATED", resource_id=webhook_id
        )
        self.assertEqual(audit_events.count(), 1, "Exactly one audit event should be created")

        # Verify no duplicate audit events
        total_audit_count = AuditEvent.objects.filter(resource_type="WEBHOOK").count()
        self.assertEqual(
            total_audit_count, initial_audit_count + 1, "Only one new audit event should exist"
        )

    def test_create_webhook_via_api_failure_missing_name(self):
        """Failure: POST with empty name returns 400 and error details (no audit)."""
        response = self.client.post(
            "/api/v1/webhooks/webhooks/",
            {
                "name": "",
                "url": "https://example.com/webhook",
                "secret": "test-secret",
                "event_types": [WebhookEventType.ASSET_CREATED],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.data or {}
        if isinstance(data, dict):
            self.assertIn("name", data,
                          f"Expected 'name' in error response keys, got: {list(data.keys())}")
        else:
            self.assertIn("name", str(data).lower(),
                          f"Expected 'name' in error response body, got: {data}")
        self.assertEqual(Webhook.objects.filter(tenant=self.tenant).count(), 0)

    def test_update_webhook_via_api_failure_not_found(self):
        """Failure: PATCH non-existent webhook id returns 404."""
        import uuid

        fake_id = str(uuid.uuid4())
        response = self.client.patch(
            f"/api/v1/webhooks/webhooks/{fake_id}/",
            {"name": "Updated"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_create_webhook_via_api_edge_minimal_payload(self):
        """Edge case: minimal valid payload (single event type, required fields only)."""
        response = self.client.post(
            "/api/v1/webhooks/webhooks/",
            {
                "name": "Minimal",
                "url": "https://example.com/hook",
                "secret": "s",
                "event_types": [WebhookEventType.ASSET_CREATED],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", response.data)
        webhook = Webhook.objects.get(id=response.data["id"])
        self.assertEqual(webhook.name, "Minimal")
        self.assertEqual(len(webhook.event_types), 1)

    def test_create_webhook_via_api_error_handling_invalid_url(self):
        """Error handling: invalid URL returns 400 with validation detail."""
        response = self.client.post(
            "/api/v1/webhooks/webhooks/",
            {
                "name": "Test",
                "url": "not-a-url",
                "secret": "secret",
                "event_types": [WebhookEventType.ASSET_CREATED],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.data or {}
        if isinstance(data, dict):
            self.assertIn("url", data,
                          f"Expected 'url' in error response, got keys: {list(data.keys())}")
        else:
            self.assertIn("url", str(data).lower(),
                          f"Expected 'url' in error response body, got: {data}")

    def test_update_webhook_via_api(self):
        """Test updating webhook via API endpoint (Phase 12.2.2)"""
        # Create webhook first
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Original Name",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ASSET_CREATED],
            created_by=self.user,
        )

        initial_audit_count = AuditEvent.objects.filter(
            resource_type="WEBHOOK", action="WEBHOOK_UPDATED", resource_id=str(webhook.id)
        ).count()

        response = self.client.patch(
            f"/api/v1/webhooks/webhooks/{webhook.id}/",
            {
                "name": "Updated Name",
                "status": WebhookStatus.PAUSED,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        webhook.refresh_from_db()
        self.assertEqual(webhook.name, "Updated Name")
        self.assertEqual(webhook.status, WebhookStatus.PAUSED)

        # Verify exactly one audit event was created for update
        audit_events = AuditEvent.objects.filter(
            resource_type="WEBHOOK", action="WEBHOOK_UPDATED", resource_id=str(webhook.id)
        )
        self.assertEqual(
            audit_events.count(),
            initial_audit_count + 1,
            "Exactly one new audit event should be created for update",
        )

    def test_list_webhooks_unauthenticated_returns_401(self):
        """Error handling: list endpoint returns 401 when unauthenticated."""
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/webhooks/webhooks/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_webhook_missing_required_returns_400(self):
        """Failure: create with missing required fields returns 400."""
        response = self.client.post(
            "/api/v1/webhooks/webhooks/",
            {"url": "https://example.com/webhook", "secret": "secret"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.data or {}
        self.assertIn("name", data,
                      f"Expected 'name' field error in response, got: {data}")

    def test_create_webhook_invalid_url_returns_400(self):
        """Error handling: invalid URL returns 400."""
        response = self.client.post(
            "/api/v1/webhooks/webhooks/",
            {
                "name": "Test",
                "url": "not-a-valid-url",
                "secret": "secret",
                "event_types": [WebhookEventType.ASSET_CREATED],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        data = response.data or {}
        if isinstance(data, dict):
            self.assertIn("url", data,
                          f"Expected 'url' in error response, got keys: {list(data.keys())}")
        else:
            self.assertIn("url", str(data).lower(),
                          f"Expected 'url' in error response body, got: {data}")

    def test_retrieve_webhook_not_found_returns_404(self):
        """Error handling: retrieve non-existent webhook returns 404."""
        import uuid

        fake_id = uuid.uuid4()
        response = self.client.get(f"/api/v1/webhooks/webhooks/{fake_id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        data = response.data or {}
        self.assertIn("error", data,
                      f"Expected 'error' key in 404 response, got: {data}")

    def test_create_webhook_response_structure_tdd(self):
        """TDD: create response contains required keys."""
        response = self.client.post(
            "/api/v1/webhooks/webhooks/",
            {
                "name": "TDD Webhook",
                "url": "https://example.com/webhook",
                "secret": "secret",
                "event_types": [WebhookEventType.ASSET_CREATED],
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        for key in ("id", "name", "url", "status", "event_types"):
            self.assertIn(key, response.data, f"Missing key in create response: {key}")
        self.assertEqual(response.data["name"], "TDD Webhook")

    def test_webhook_deliveries_list(self):
        """GET /webhooks/{id}/deliveries/ returns delivery list for a webhook."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Deliveries Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ASSET_CREATED],
            created_by=self.user,
        )
        # Create a delivery for this webhook
        WebhookDelivery.objects.create(
            webhook=webhook,
            event_type=WebhookEventType.ASSET_CREATED,
            payload={"event_type": "asset.created", "data": {}},
            signature="test",
        )
        response = self.client.get(
            f"/api/v1/webhooks/webhooks/{webhook.id}/deliveries/"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response should be a paginated list
        self.assertIn("results", response.data)
        self.assertGreaterEqual(len(response.data["results"]), 1)

    def test_webhook_retry_delivery(self):
        """POST /webhooks/{id}/retry/ triggers delivery retry."""
        webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Retry Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ASSET_CREATED],
            created_by=self.user,
        )
        response = self.client.post(
            f"/api/v1/webhooks/webhooks/{webhook.id}/retry/"
        )
        # 200 means retry was queued or webhook has no failed deliveries
        self.assertIn(
            response.status_code,
            [status.HTTP_200_OK, status.HTTP_404_NOT_FOUND],
        )

    def test_webhook_retry_delivery_nonexistent_webhook(self):
        """POST /webhooks/{id}/retry/ with nonexistent webhook returns 404."""
        import uuid

        fake_id = uuid.uuid4()
        response = self.client.post(
            f"/api/v1/webhooks/webhooks/{fake_id}/retry/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
