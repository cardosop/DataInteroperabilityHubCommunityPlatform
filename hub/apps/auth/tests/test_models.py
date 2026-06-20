"""
Unit tests for Auth models (APIKey).
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.auth.models import APIKey
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class APIKeyModelTest(TestCase):
    """Test APIKey model"""

    def setUp(self):
        """Set up test fixtures"""
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
        )

    def test_create_api_key_sets_tenant(self):
        """Test API key creation sets tenant."""
        key = APIKey.generate_key()
        key_hash = APIKey.hash_key(key)

        api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Test API Key",
            key_hash=key_hash,
        )

        self.assertEqual(api_key.tenant, self.tenant)

    def test_create_api_key_sets_user(self):
        """Test API key creation sets user."""
        key = APIKey.generate_key()
        key_hash = APIKey.hash_key(key)

        api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Test API Key",
            key_hash=key_hash,
        )

        self.assertEqual(api_key.user, self.user)

    def test_create_api_key_sets_name(self):
        """Test API key creation sets name."""
        key = APIKey.generate_key()
        key_hash = APIKey.hash_key(key)

        api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Test API Key",
            key_hash=key_hash,
        )

        self.assertEqual(api_key.name, "Test API Key")

    def test_create_api_key_sets_key_hash(self):
        """Test API key creation sets key_hash."""
        key = APIKey.generate_key()
        key_hash = APIKey.hash_key(key)

        api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Test API Key",
            key_hash=key_hash,
        )

        self.assertIsNotNone(api_key.key_hash)

    def test_api_key_generate_returns_string(self):
        """Test API key generation returns string."""
        key = APIKey.generate_key()
        self.assertIsInstance(key, str)

    def test_api_key_generate_returns_non_empty(self):
        """Test API key generation returns non-empty key."""
        key = APIKey.generate_key()
        self.assertGreater(len(key), 0)

    def test_api_key_hash_returns_string(self):
        """Test API key hashing returns string."""
        key = APIKey.generate_key()
        key_hash = APIKey.hash_key(key)
        self.assertIsInstance(key_hash, str)

    def test_api_key_hash_returns_sha256_length(self):
        """Test API key hashing returns SHA-256 hex digest length."""
        key = APIKey.generate_key()
        key_hash = APIKey.hash_key(key)
        self.assertEqual(len(key_hash), 64)  # SHA-256 hex digest length

    def test_api_key_is_expired_none_expires_at_returns_false(self):
        """Test API key expiration check with None expires_at returns False."""

        key = APIKey.generate_key()
        key_hash = APIKey.hash_key(key)

        # Non-expiring key
        api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Test API Key",
            key_hash=key_hash,
            expires_at=None,
        )
        self.assertFalse(api_key.is_expired())

    def test_api_key_is_expired_past_date_returns_true(self):
        """Test API key expiration check with past date returns True."""
        from datetime import timedelta

        from django.utils import timezone

        key = APIKey.generate_key()
        key_hash = APIKey.hash_key(key)

        api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Test API Key",
            key_hash=key_hash,
        )

        # Expired key
        api_key.expires_at = timezone.now() - timedelta(days=1)
        api_key.save()
        self.assertTrue(api_key.is_expired())

    # ========== SUCCESS SCENARIOS ==========

    def test_api_key_generate_creates_unique_keys(self):
        """Test API key generation creates unique keys."""
        key1 = APIKey.generate_key()
        key2 = APIKey.generate_key()
        self.assertNotEqual(key1, key2)

    # ========== FAILURE SCENARIOS ==========

    def test_api_key_hash_same_key_produces_same_hash(self):
        """Test API key hashing same key produces same hash."""
        key = APIKey.generate_key()
        hash1 = APIKey.hash_key(key)
        hash2 = APIKey.hash_key(key)
        self.assertEqual(hash1, hash2)

    # ========== EDGE CASES ==========

    def test_api_key_hash_empty_string(self):
        """Test API key hashing empty string (edge case)."""
        key_hash = APIKey.hash_key("")
        # Should handle gracefully
        self.assertIsInstance(key_hash, str)

    def test_api_key_is_expired_future_date_returns_false(self):
        """Test API key expiration check with future date returns False."""
        from datetime import timedelta

        from django.utils import timezone

        key = APIKey.generate_key()
        key_hash = APIKey.hash_key(key)

        api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Test API Key",
            key_hash=key_hash,
            expires_at=timezone.now() + timedelta(days=1),
        )
        self.assertFalse(api_key.is_expired())

    # ========== ERROR HANDLING ==========

    def test_api_key_hash_none_raises_attribute_error(self):
        """hash_key(None) raises AttributeError — None has no .encode()."""
        with self.assertRaises(AttributeError):
            APIKey.hash_key(None)


class APIKeyModelMethodTests(TestCase):
    """Dedicated tests for APIKey model lifecycle methods."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"Method Test {uid}",
            slug=f"method-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.user = User.objects.create_user(
            email=f"method-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )
        plain_key = APIKey.generate_key()
        self.plain_key = plain_key
        self.api_key = APIKey.objects.create(
            tenant=self.tenant,
            user=self.user,
            name="Method Test Key",
            key_hash=APIKey.hash_key(plain_key),
        )

    def test_verify_key_with_correct_key_returns_true(self):
        self.assertTrue(self.api_key.verify_key(self.plain_key))

    def test_verify_key_with_wrong_key_returns_false(self):
        self.assertFalse(self.api_key.verify_key("wrong-key-123456"))

    def test_verify_key_with_empty_string_returns_false(self):
        self.assertFalse(self.api_key.verify_key(""))

    def test_update_last_used_sets_timestamp(self):
        from django.utils import timezone

        self.assertIsNone(self.api_key.last_used_at)
        self.api_key.update_last_used()
        self.api_key.refresh_from_db()
        self.assertIsNotNone(self.api_key.last_used_at)
        self.assertLess(
            (timezone.now() - self.api_key.last_used_at).total_seconds(), 5,
        )

    def test_revoke_sets_revoked_at(self):
        self.assertIsNone(self.api_key.revoked_at)
        self.api_key.revoke()
        self.api_key.refresh_from_db()
        self.assertIsNotNone(self.api_key.revoked_at)
        self.assertTrue(self.api_key.is_revoked())

    def test_revoke_on_already_revoked_key_is_idempotent(self):
        self.api_key.revoke()
        self.api_key.refresh_from_db()
        first_revoked_at = self.api_key.revoked_at
        # revoke again — should not change revoked_at
        self.api_key.revoke()
        self.api_key.refresh_from_db()
        self.assertEqual(self.api_key.revoked_at, first_revoked_at)
