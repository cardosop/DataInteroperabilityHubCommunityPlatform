"""
Unit tests for rate limit key generation and hierarchy.

Tests key generation for tenant, user, and API-key levels, and key hierarchy.
"""

from django.test import TestCase

from hub.apps.rate_limiting.utils import EndpointCategory, TimeWindow, generate_rate_limit_key


class RateLimitKeyGenerationTest(TestCase):
    """Tests for rate limit key generation"""

    def test_tenant_key_generation(self):
        """Test tenant-level key generation"""
        key = generate_rate_limit_key(
            tenant_id="test-tenant-id",
            endpoint_category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )
        self.assertEqual(key, "rate_limit:tenant:test-tenant-id:dq_run:60")

    def test_user_key_generation(self):
        """Test user-level key generation"""
        key = generate_rate_limit_key(
            tenant_id="test-tenant-id",
            user_id="test-user-id",
            endpoint_category=EndpointCategory.FILE_UPLOAD,
            window=TimeWindow.BURST,
        )
        self.assertEqual(key, "rate_limit:tenant:test-tenant-id:user:test-user-id:file_upload:10")

    def test_api_key_generation(self):
        """Test API-key-level key generation"""
        key = generate_rate_limit_key(
            tenant_id="test-tenant-id",
            api_key_id="test-api-key-id",
            endpoint_category=EndpointCategory.CATALOG_READ,
            window=TimeWindow.DAILY,
        )
        self.assertEqual(
            key, "rate_limit:tenant:test-tenant-id:apikey:test-api-key-id:catalog_read:86400"
        )

    def test_key_generation_requires_tenant(self):
        """Test that tenant_id is required"""
        with self.assertRaises(ValueError):
            generate_rate_limit_key(
                endpoint_category=EndpointCategory.GENERAL, window=TimeWindow.SUSTAINED
            )

    def test_key_hierarchy_tenant_only(self):
        """Test key hierarchy for tenant-only keys"""
        key = generate_rate_limit_key(
            tenant_id="tenant-123",
            endpoint_category=EndpointCategory.GENERAL,
            window=TimeWindow.SUSTAINED,
        )

        # Should not contain user or api_key
        self.assertNotIn("user", key)
        self.assertNotIn("apikey", key)
        self.assertIn("tenant:tenant-123", key)

    def test_key_hierarchy_api_key_overrides_user(self):
        """Test that api_key_id takes precedence over user_id"""
        # If both user_id and api_key_id are provided, api_key_id should be used
        key = generate_rate_limit_key(
            tenant_id="tenant-123",
            user_id="user-456",
            api_key_id="api-key-789",
            endpoint_category=EndpointCategory.GENERAL,
            window=TimeWindow.SUSTAINED,
        )

        # Should use api_key, not user
        self.assertIn("apikey:api-key-789", key)
        self.assertNotIn("user:user-456", key)

    def test_key_includes_endpoint_category(self):
        """Test that key includes endpoint category"""
        categories = [
            EndpointCategory.DQ_RUN,
            EndpointCategory.COMPLIANCE_RUN,
            EndpointCategory.FILE_UPLOAD,
            EndpointCategory.FILE_DOWNLOAD,
            EndpointCategory.CONTRACT_VALIDATION,
            EndpointCategory.CATALOG_READ,
            EndpointCategory.SPARQL_QUERY,
            EndpointCategory.GENERAL,
        ]

        for category in categories:
            key = generate_rate_limit_key(
                tenant_id="test-tenant", endpoint_category=category, window=TimeWindow.SUSTAINED
            )
            self.assertIn(category, key)

    def test_key_includes_time_window(self):
        """Test that key includes time window"""
        windows = [
            (TimeWindow.BURST, "10"),
            (TimeWindow.SUSTAINED, "60"),
            (TimeWindow.DAILY, "86400"),
        ]

        for window, expected_value in windows:
            key = generate_rate_limit_key(
                tenant_id="test-tenant", endpoint_category=EndpointCategory.GENERAL, window=window
            )
            self.assertIn(expected_value, key)

    def test_key_uniqueness_per_tenant(self):
        """Test that keys are unique per tenant"""
        key1 = generate_rate_limit_key(
            tenant_id="tenant-1",
            endpoint_category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )
        key2 = generate_rate_limit_key(
            tenant_id="tenant-2",
            endpoint_category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )

        self.assertNotEqual(key1, key2)
        self.assertIn("tenant-1", key1)
        self.assertIn("tenant-2", key2)

    def test_key_uniqueness_per_user(self):
        """Test that keys are unique per user"""
        key1 = generate_rate_limit_key(
            tenant_id="tenant-1",
            user_id="user-1",
            endpoint_category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )
        key2 = generate_rate_limit_key(
            tenant_id="tenant-1",
            user_id="user-2",
            endpoint_category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )

        self.assertNotEqual(key1, key2)
        self.assertIn("user-1", key1)
        self.assertIn("user-2", key2)

    def test_key_uniqueness_per_api_key(self):
        """Test that keys are unique per API key"""
        key1 = generate_rate_limit_key(
            tenant_id="tenant-1",
            api_key_id="api-key-1",
            endpoint_category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )
        key2 = generate_rate_limit_key(
            tenant_id="tenant-1",
            api_key_id="api-key-2",
            endpoint_category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )

        self.assertNotEqual(key1, key2)
        self.assertIn("api-key-1", key1)
        self.assertIn("api-key-2", key2)

    def test_key_uniqueness_per_category(self):
        """Test that keys are unique per endpoint category"""
        key1 = generate_rate_limit_key(
            tenant_id="tenant-1",
            endpoint_category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )
        key2 = generate_rate_limit_key(
            tenant_id="tenant-1",
            endpoint_category=EndpointCategory.COMPLIANCE_RUN,
            window=TimeWindow.SUSTAINED,
        )

        self.assertNotEqual(key1, key2)
        self.assertIn("dq_run", key1)
        self.assertIn("compliance_run", key2)

    def test_key_uniqueness_per_window(self):
        """Test that keys are unique per time window"""
        key1 = generate_rate_limit_key(
            tenant_id="tenant-1", endpoint_category=EndpointCategory.DQ_RUN, window=TimeWindow.BURST
        )
        key2 = generate_rate_limit_key(
            tenant_id="tenant-1",
            endpoint_category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )
        key3 = generate_rate_limit_key(
            tenant_id="tenant-1", endpoint_category=EndpointCategory.DQ_RUN, window=TimeWindow.DAILY
        )

        self.assertNotEqual(key1, key2)
        self.assertNotEqual(key2, key3)
        self.assertNotEqual(key1, key3)
        self.assertIn("10", key1)  # BURST
        self.assertIn("60", key2)  # SUSTAINED
        self.assertIn("86400", key3)  # DAILY

    def test_key_format_consistency(self):
        """Test that key format is consistent"""
        key = generate_rate_limit_key(
            tenant_id="tenant-123",
            user_id="user-456",
            endpoint_category=EndpointCategory.DQ_RUN,
            window=TimeWindow.SUSTAINED,
        )

        # Should follow pattern: rate_limit:tenant:{tenant_id}:user:{user_id}:{category}:{window}
        parts = key.split(":")
        self.assertEqual(parts[0], "rate_limit")
        self.assertEqual(parts[1], "tenant")
        self.assertEqual(parts[2], "tenant-123")
        self.assertEqual(parts[3], "user")
        self.assertEqual(parts[4], "user-456")
        self.assertEqual(parts[5], "dq_run")
        self.assertEqual(parts[6], "60")

    def test_key_special_characters_handled(self):
        """Test that special characters in IDs are handled correctly"""
        # UUIDs and other IDs may contain hyphens, which should be preserved
        tenant_id = "550e8400-e29b-41d4-a716-446655440000"
        user_id = "6ba7b810-9dad-11d1-80b4-00c04fd430c8"

        key = generate_rate_limit_key(
            tenant_id=tenant_id,
            user_id=user_id,
            endpoint_category=EndpointCategory.GENERAL,
            window=TimeWindow.SUSTAINED,
        )

        # Should preserve hyphens
        self.assertIn(tenant_id, key)
        self.assertIn(user_id, key)
