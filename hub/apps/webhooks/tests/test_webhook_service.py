"""
Unit tests for Webhook Service (Phase 12.2.2)

Tests for WebhookService.create_webhook and update_webhook
with real DB and real audit events. No mocks.
"""

import pytest
from django.test import TestCase

from hub.apps.audit.models import AuditEvent
from hub.apps.core.services.base import NotFoundError, ValidationError
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import User, UserStatus
from hub.apps.webhooks.models import Webhook, WebhookEventType, WebhookStatus
from hub.apps.webhooks.webhook_service import WebhookService

pytestmark = pytest.mark.django_db(transaction=True)


class WebhookServiceTest(TestCase):
    """Test WebhookService methods with real DB and audit (Phase 12.2.2)"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(
            name="Test Tenant", slug="test-tenant", status="ACTIVE", kyc_status="UNVERIFIED"
        )

        self.user = User.objects.create_user(
            email="user@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )

        self.service = WebhookService(tenant_id=str(self.tenant.id), user_id=str(self.user.id))

    def test_create_webhook(self):
        """Test creating webhook via service (Phase 12.2.2)"""
        webhook = self.service.create_webhook(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret-key",
            event_types=[WebhookEventType.ASSET_CREATED, WebhookEventType.CONTRACT_CREATED],
            status=WebhookStatus.ACTIVE,
            max_retries=5,
        )

        # Verify webhook was created
        self.assertIsNotNone(webhook.id)
        self.assertEqual(webhook.name, "Test Webhook")
        self.assertEqual(webhook.url, "https://example.com/webhook")
        self.assertEqual(webhook.status, WebhookStatus.ACTIVE)
        self.assertIn(WebhookEventType.ASSET_CREATED, webhook.event_types)
        self.assertEqual(webhook.created_by, self.user)

        # Verify exactly one audit event was created (Phase 12.4.1)
        audit_events = AuditEvent.objects.filter(
            resource_type="WEBHOOK", action="WEBHOOK_CREATED", resource_id=webhook.id
        )
        self.assertEqual(audit_events.count(), 1, "Exactly one audit event should be created")

        audit_event = audit_events.first()
        self.assertEqual(audit_event.actor_user, self.user)
        self.assertEqual(audit_event.tenant, self.tenant)
        self.assertEqual(str(audit_event.resource_id), str(webhook.id))
        details = (
            audit_event.details_json
            if hasattr(audit_event, "details_json")
            else audit_event.details
        )
        self.assertIn("name", details)
        self.assertEqual(details["name"], "Test Webhook")
        self.assertIn("event_types", details)

    def test_create_webhook_validation_error_no_name(self):
        """Test that webhook creation requires name"""
        with self.assertRaises(ValidationError) as cm:
            self.service.create_webhook(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="",
                url="https://example.com/webhook",
                secret="test-secret",
                event_types=[WebhookEventType.ASSET_CREATED],
            )

        self.assertIn("name", str(cm.exception).lower())

    def test_create_webhook_validation_error_no_url(self):
        """Test that webhook creation requires URL"""
        with self.assertRaises(ValidationError) as cm:
            self.service.create_webhook(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test",
                url="",
                secret="test-secret",
                event_types=[WebhookEventType.ASSET_CREATED],
            )

        self.assertIn("url", str(cm.exception).lower())

    def test_create_webhook_validation_error_no_secret(self):
        """Test that webhook creation requires secret"""
        with self.assertRaises(ValidationError) as cm:
            self.service.create_webhook(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test",
                url="https://example.com/webhook",
                secret="",
                event_types=[WebhookEventType.ASSET_CREATED],
            )

        self.assertIn("secret", str(cm.exception).lower())

    def test_create_webhook_validation_error_no_event_types(self):
        """Test that webhook creation requires at least one event type"""
        with self.assertRaises(ValidationError) as cm:
            self.service.create_webhook(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test",
                url="https://example.com/webhook",
                secret="test-secret",
                event_types=[],
            )

        self.assertIn("event type", str(cm.exception).lower())

    def test_create_webhook_validation_error_invalid_url(self):
        """Test that webhook creation validates URL format"""
        with self.assertRaises(ValidationError) as cm:
            self.service.create_webhook(
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Test",
                url="not-a-valid-url",
                secret="test-secret",
                event_types=[WebhookEventType.ASSET_CREATED],
            )

        self.assertIn("url", str(cm.exception).lower())

    def test_update_webhook(self):
        """Test updating webhook via service (Phase 12.2.2)"""
        # Create webhook first
        webhook = self.service.create_webhook(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Original Name",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ASSET_CREATED],
            status=WebhookStatus.ACTIVE,
        )

        # Update webhook
        updated_webhook = self.service.update_webhook(
            webhook_id=str(webhook.id),
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Updated Name",
            url="https://example.com/webhook-updated",
            status=WebhookStatus.PAUSED,
        )

        # Verify updates
        updated_webhook.refresh_from_db()
        self.assertEqual(updated_webhook.name, "Updated Name")
        self.assertEqual(updated_webhook.url, "https://example.com/webhook-updated")
        self.assertEqual(updated_webhook.status, WebhookStatus.PAUSED)

        # Verify exactly one audit event was created for update
        audit_events = AuditEvent.objects.filter(
            resource_type="WEBHOOK", action="WEBHOOK_UPDATED", resource_id=webhook.id
        )
        self.assertEqual(
            audit_events.count(), 1, "Exactly one audit event should be created for update"
        )

        audit_event = audit_events.first()
        self.assertEqual(audit_event.actor_user, self.user)
        details = (
            audit_event.details_json
            if hasattr(audit_event, "details_json")
            else audit_event.details
        )
        self.assertIn("changes", details)
        self.assertEqual(details["changes"]["name"], "Updated Name")
        self.assertIn("original", details)

    def test_update_webhook_not_found(self):
        """Test that updating non-existent webhook raises NotFoundError"""
        import uuid

        fake_webhook_id = str(uuid.uuid4())

        with self.assertRaises(NotFoundError):
            self.service.update_webhook(
                webhook_id=fake_webhook_id,
                tenant_id=str(self.tenant.id),
                user_id=str(self.user.id),
                name="Updated",
            )

    # --- Edge cases (TDD: explicit scenarios and assertions) ---

    def test_create_webhook_single_event_type(self):
        """Edge case: create webhook with exactly one event type (minimum valid)."""
        webhook = self.service.create_webhook(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Single Event Webhook",
            url="https://example.com/callback",
            secret="secret",
            event_types=[WebhookEventType.ASSET_CREATED],
        )
        self.assertIsNotNone(webhook.id)
        self.assertEqual(len(webhook.event_types), 1)
        self.assertEqual(webhook.event_types[0], WebhookEventType.ASSET_CREATED)
        audit = AuditEvent.objects.filter(
            resource_type="WEBHOOK", action="WEBHOOK_CREATED", resource_id=webhook.id
        )
        self.assertEqual(audit.count(), 1)

    def test_create_webhook_url_with_path(self):
        """Edge case: URL with path and query is accepted by URLValidator."""
        webhook = self.service.create_webhook(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Path Webhook",
            url="https://example.com/webhooks/callback?source=hub",
            secret="secret",
            event_types=[WebhookEventType.ASSET_CREATED],
        )
        self.assertIsNotNone(webhook.id)
        self.assertEqual(webhook.url, "https://example.com/webhooks/callback?source=hub")

    def test_create_webhook_max_retries_boundary(self):
        """Edge case: max_retries=1 and matching retry_intervals are persisted."""
        webhook = self.service.create_webhook(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Min Retries Webhook",
            url="https://example.com/webhook",
            secret="secret",
            event_types=[WebhookEventType.ASSET_CREATED],
            max_retries=1,
            retry_intervals=[60],
        )
        self.assertIsNotNone(webhook.id)
        self.assertEqual(webhook.max_retries, 1)
        self.assertEqual(webhook.retry_intervals, [60])

    def test_create_webhook_tdd_return_structure(self):
        """TDD: create_webhook returns object with required attributes."""
        webhook = self.service.create_webhook(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="TDD Webhook",
            url="https://example.com/webhook",
            secret="secret",
            event_types=[WebhookEventType.CONTRACT_CREATED],
        )
        for attr in ("id", "name", "url", "status", "event_types", "created_by", "tenant"):
            self.assertTrue(hasattr(webhook, attr), f"Missing attribute: {attr}")
        self.assertIsNotNone(webhook.id)
        self.assertEqual(webhook.name, "TDD Webhook")
        self.assertEqual(webhook.tenant, self.tenant)

    def test_create_webhook_edge_case_all_event_types(self):
        """Edge case: create with multiple event types; all are persisted."""
        all_types = [
            WebhookEventType.ASSET_CREATED,
            WebhookEventType.CONTRACT_CREATED,
            WebhookEventType.CONTRACT_UPDATED,
        ]
        webhook = self.service.create_webhook(
            tenant_id=str(self.tenant.id),
            user_id=str(self.user.id),
            name="Multi-Event Webhook",
            url="https://example.com/webhook",
            secret="secret",
            event_types=all_types,
        )
        self.assertIsNotNone(webhook.id)
        self.assertEqual(len(webhook.event_types), len(all_types))
        for et in all_types:
            self.assertIn(et, webhook.event_types)
