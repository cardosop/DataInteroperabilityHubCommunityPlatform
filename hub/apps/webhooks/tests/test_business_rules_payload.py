"""
Unit tests for Webhook Payload Validation

Tests for webhook payload validation, including:
- Payload size validation
- Payload structure validation
- Payload content validation
- Integration with WebhookDeliveryService
"""

import uuid

from django.test import TestCase

from hub.apps.tenants.models import KYCStatus, Tenant
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import User, UserStatus
from hub.apps.webhooks.business_rules import MAX_PAYLOAD_SIZE, WebhooksBusinessRules
from hub.apps.webhooks.models import (
    Webhook,
    WebhookDelivery,
    WebhookEventType,
)


class WebhookPayloadValidationTest(TestCase):
    """Test webhook payload validation"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ASSET_CREATED],
            created_by=self.user,
        )
        self.business_rules = WebhooksBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_validate_payload_size_within_limit(self):
        """Test payload size validation with payload within limit"""
        payload = {
            "event_type": "asset.created",
            "resource_type": "ASSET",
            "resource_id": "123e4567-e89b-12d3-a456-426614174000",
            "timestamp": "2024-01-01T00:00:00Z",
            "data": {"key": "value"},
        }
        result = self.business_rules._validate_payload_size(payload)
        self.assertTrue(result.is_valid)
        self.assertIn("payload_size_bytes", result.details)
        self.assertIn("max_payload_size_bytes", result.details)

    def test_validate_payload_size_exceeds_limit(self):
        """Test payload size validation with payload exceeding limit"""
        # Create a large payload (exceeds 1MB)
        large_data = {"data": "x" * (2 * 1024 * 1024)}  # 2MB
        payload = {
            "event_type": "asset.created",
            "resource_type": "ASSET",
            "resource_id": "123e4567-e89b-12d3-a456-426614174000",
            "timestamp": "2024-01-01T00:00:00Z",
            "data": large_data,
        }
        result = self.business_rules._validate_payload_size(payload)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("exceeds maximum", result.errors[0])

    def test_validate_payload_size_empty_payload(self):
        """Test payload size validation with empty payload"""
        payload = {}
        result = self.business_rules._validate_payload_size(payload)
        self.assertTrue(result.is_valid)
        # Empty dict serializes to "{}" which is 2 bytes, so it's valid but small
        self.assertIn("payload_size_bytes", result.details)
        self.assertLessEqual(result.details["payload_size_bytes"], 10)  # Should be small

    def test_validate_payload_size_large_payload_warning(self):
        """Test payload size validation with large but acceptable payload"""
        # Create a payload larger than 500KB to trigger warning
        large_data = {"data": "x" * (600 * 1024)}  # 600KB
        payload = {
            "event_type": "asset.created",
            "resource_type": "ASSET",
            "resource_id": "123e4567-e89b-12d3-a456-426614174000",
            "timestamp": "2024-01-01T00:00:00Z",
            "data": large_data,
        }
        result = self.business_rules._validate_payload_size(payload)
        self.assertTrue(result.is_valid)
        # Should have warning about large payload
        warnings_text = " ".join(result.warnings).lower()
        self.assertIn("large", warnings_text)

    def test_validate_payload_structure_valid_dict(self):
        """Test payload structure validation with valid dictionary"""
        payload = {
            "event_type": "asset.created",
            "resource_type": "ASSET",
            "resource_id": "123e4567-e89b-12d3-a456-426614174000",
            "timestamp": "2024-01-01T00:00:00Z",
            "data": {"key": "value"},
        }
        result = self.business_rules._validate_payload_structure(payload)
        self.assertTrue(result.is_valid)
        self.assertTrue(result.details.get("is_json_serializable"))

    def test_validate_payload_structure_invalid_type(self):
        """TDD: Given a non-dict payload (e.g. string), When _validate_payload_structure is called,
        Then result is invalid and errors mention 'must be a dictionary'."""
        payload = "not a dict"
        result = self.business_rules._validate_payload_structure(payload)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("must be a dictionary", result.errors[0])

    def test_validate_payload_structure_empty_dict(self):
        """Test payload structure validation with empty dictionary"""
        payload = {}
        result = self.business_rules._validate_payload_structure(payload)
        self.assertTrue(result.is_valid)
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("empty", result.warnings[0].lower())

    def test_validate_payload_content_all_required_fields(self):
        """Test payload content validation with all required fields"""
        payload = {
            "event_type": "asset.created",
            "resource_type": "ASSET",
            "resource_id": "123e4567-e89b-12d3-a456-426614174000",
            "timestamp": "2024-01-01T00:00:00Z",
            "data": {"key": "value"},
        }
        result = self.business_rules._validate_payload_content(payload)
        self.assertTrue(result.is_valid)
        self.assertEqual(result.details.get("event_type"), "asset.created")
        self.assertEqual(result.details.get("resource_type"), "ASSET")

    def test_validate_payload_content_missing_required_fields(self):
        """Test payload content validation with missing required fields"""
        payload = {
            "event_type": "asset.created",
            # Missing resource_type, resource_id, timestamp, data
        }
        result = self.business_rules._validate_payload_content(payload)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("missing_fields", result.details)
        missing_fields = result.details["missing_fields"]
        self.assertIn("resource_type", missing_fields)
        self.assertIn("resource_id", missing_fields)
        self.assertIn("timestamp", missing_fields)
        self.assertIn("data", missing_fields)

    def test_validate_payload_content_invalid_field_types(self):
        """Test payload content validation with invalid field types"""
        payload = {
            "event_type": 123,  # Should be string
            "resource_type": None,  # Should be string
            "resource_id": ["not", "a", "string"],  # Should be string
            "timestamp": 1234567890,  # Should be string
            "data": "not a dict",  # Should be dict (warning)
        }
        result = self.business_rules._validate_payload_content(payload)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_payload_content_empty_string_fields(self):
        """Test payload content validation with empty string fields"""
        payload = {
            "event_type": "",  # Empty string
            "resource_type": "   ",  # Whitespace only
            "resource_id": "123e4567-e89b-12d3-a456-426614174000",
            "timestamp": "2024-01-01T00:00:00Z",
            "data": {},
        }
        result = self.business_rules._validate_payload_content(payload)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)

    def test_validate_payload_content_invalid_timestamp_format(self):
        """Test payload content validation with invalid timestamp format"""
        payload = {
            "event_type": "asset.created",
            "resource_type": "ASSET",
            "resource_id": "123e4567-e89b-12d3-a456-426614174000",
            "timestamp": "not a valid timestamp",
            "data": {},
        }
        result = self.business_rules._validate_payload_content(payload)
        self.assertTrue(result.is_valid)  # We only warn about timestamp format
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("timestamp", result.warnings[0].lower())

    def test_validate_payload_content_event_type_mismatch(self):
        """Test payload content validation with event type mismatch"""
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ASSET_UPDATED,
            payload={
                "event_type": "asset.created",  # Different from delivery
                "resource_type": "ASSET",
                "resource_id": "123e4567-e89b-12d3-a456-426614174000",
                "timestamp": "2024-01-01T00:00:00Z",
                "data": {},
            },
            signature="test-signature",
        )
        payload = delivery.payload
        result = self.business_rules._validate_payload_content(payload, delivery)
        self.assertTrue(result.is_valid)  # We only warn about mismatch
        self.assertGreater(len(result.warnings), 0)
        self.assertIn("event_type", result.warnings[0].lower())

    def test_validate_payload_comprehensive(self):
        """Test comprehensive payload validation"""
        payload = {
            "event_type": "asset.created",
            "resource_type": "ASSET",
            "resource_id": "123e4567-e89b-12d3-a456-426614174000",
            "timestamp": "2024-01-01T00:00:00Z",
            "data": {"key": "value", "nested": {"nested_key": "nested_value"}},
        }
        result = self.business_rules._validate_payload(payload)
        self.assertTrue(result.is_valid)
        self.assertIn("payload_size_validation", result.details)
        self.assertIn("payload_structure_validation", result.details)
        self.assertIn("payload_content_validation", result.details)

    def test_validate_payload_with_delivery(self):
        """Test payload validation integrated with delivery validation"""
        payload = {
            "event_type": "asset.created",
            "resource_type": "ASSET",
            "resource_id": "123e4567-e89b-12d3-a456-426614174000",
            "timestamp": "2024-01-01T00:00:00Z",
            "data": {"key": "value"},
        }
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ASSET_CREATED,
            payload=payload,
            signature="test-signature",
        )
        result = self.business_rules._validate_delivery(delivery)
        self.assertTrue(result.is_valid)
        # Payload should be validated as part of delivery validation
        # Check that payload validation details are present
        self.assertIn("delivery_validation", result.details)


class WebhookPayloadValidationIntegrationTest(TestCase):
    """Integration tests for webhook payload validation with WebhookDeliveryService"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}", kyc_status=KYCStatus.VERIFIED
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
        )
        self.webhook = Webhook.objects.create(
            tenant=self.tenant,
            name="Test Webhook",
            url="https://example.com/webhook",
            secret="test-secret",
            event_types=[WebhookEventType.ASSET_CREATED],
            created_by=self.user,
        )
        self.business_rules = WebhooksBusinessRules(
            tenant_id=str(self.tenant.id), user_id=str(self.user.id)
        )

    def test_validate_payload_via_business_rules_validate(self):
        """Test payload validation via main validate method"""
        payload = {
            "event_type": "asset.created",
            "resource_type": "ASSET",
            "resource_id": "123e4567-e89b-12d3-a456-426614174000",
            "timestamp": "2024-01-01T00:00:00Z",
            "data": {"key": "value"},
        }
        result = self.business_rules.validate(payload=payload, validation_type="payload")
        self.assertTrue(result.is_valid)
        self.assertIn("payload", result.details.get("validated_items", []))

    def test_validate_payload_with_delivery_via_validate(self):
        """Test payload validation with delivery via main validate method"""
        payload = {
            "event_type": "asset.created",
            "resource_type": "ASSET",
            "resource_id": "123e4567-e89b-12d3-a456-426614174000",
            "timestamp": "2024-01-01T00:00:00Z",
            "data": {"key": "value"},
        }
        delivery = WebhookDelivery.objects.create(
            webhook=self.webhook,
            event_type=WebhookEventType.ASSET_CREATED,
            payload=payload,
            signature="test-signature",
        )
        result = self.business_rules.validate(delivery=delivery, validation_type="all")
        self.assertTrue(result.is_valid)
        validated_items = result.details.get("validated_items", [])
        self.assertIn("delivery", validated_items)
        # Payload should be validated as part of delivery validation

    def test_validate_payload_boundary_at_max_size(self):
        """Payload exactly at MAX_PAYLOAD_SIZE passes; MAX_PAYLOAD_SIZE+1 fails."""
        import json

        # Build a payload that is precisely MAX_PAYLOAD_SIZE bytes when serialized.
        base = {
            "event_type": "asset.created",
            "resource_type": "ASSET",
            "resource_id": "123e4567-e89b-12d3-a456-426614174000",
            "timestamp": "2024-01-01T00:00:00Z",
            "data": {},
        }
        base_size = len(json.dumps(base, sort_keys=True).encode("utf-8"))
        # Pad the data field to hit exactly MAX_PAYLOAD_SIZE.
        padding_needed = MAX_PAYLOAD_SIZE - base_size - 2  # account for {}
        base["data"] = {"pad": "x" * max(0, padding_needed)}
        payload_json = json.dumps(base, sort_keys=True)
        actual_size = len(payload_json.encode("utf-8"))

        # Slight adjustment: if we overshot, trim.
        if actual_size > MAX_PAYLOAD_SIZE:
            trim = actual_size - MAX_PAYLOAD_SIZE
            base["data"] = {"pad": "x" * max(0, padding_needed - trim)}
            payload_json = json.dumps(base, sort_keys=True)
            actual_size = len(payload_json.encode("utf-8"))

        payload = json.loads(payload_json)

        # At exactly MAX_PAYLOAD_SIZE, validation passes.
        result_valid = self.business_rules._validate_payload(payload)
        self.assertTrue(result_valid.is_valid)

        # At MAX_PAYLOAD_SIZE + 1, validation fails.
        base["data"] = {"pad": "x" * (max(0, padding_needed) + 1)}
        oversize_json = json.dumps(base, sort_keys=True)
        oversize_payload = json.loads(oversize_json)
        result_invalid = self.business_rules._validate_payload(oversize_payload)
        self.assertFalse(result_invalid.is_valid)
        self.assertGreater(len(result_invalid.errors), 0)

    def test_validate_payload_error_handling_invalid_structure_returns_false(self):
        """Error handling: _validate_payload with non-dict returns is_valid False and expected errors."""
        result = self.business_rules._validate_payload("not a dict")
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("payload_structure_validation", result.details)

    def test_validate_payload_error_handling_oversized_returns_false(self):
        """Error handling: _validate_payload with payload exceeding MAX_PAYLOAD_SIZE returns is_valid False."""
        large_data = {"data": "x" * (2 * 1024 * 1024)}
        payload = {
            "event_type": "asset.created",
            "resource_type": "ASSET",
            "resource_id": "123e4567-e89b-12d3-a456-426614174000",
            "timestamp": "2024-01-01T00:00:00Z",
            "data": large_data,
        }
        result = self.business_rules._validate_payload(payload)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("payload_size_validation", result.details)

    def test_validate_payload_missing_required_field_event_type(self):
        """Payload missing the 'event_type' key returns is_valid=False."""
        payload = {
            "resource_type": "ASSET",
            "resource_id": "123e4567-e89b-12d3-a456-426614174000",
            "timestamp": "2024-01-01T00:00:00Z",
            "data": {},
        }
        result = self.business_rules._validate_payload(payload)
        self.assertFalse(result.is_valid)
        self.assertGreater(len(result.errors), 0)
        self.assertIn("payload_content_validation", result.details)
        self.assertIn("missing_fields", result.details)
        self.assertIn("event_type", result.details["missing_fields"])
