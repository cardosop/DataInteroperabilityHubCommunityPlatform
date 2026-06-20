"""
Phase 121G — Platform & Developer Error Tests

Negative cases for platform settings and developer plugin errors.
"""

import hashlib
import uuid
from datetime import timedelta

from django.test import TestCase
from django.utils import timezone


class TestPlatformErrorCases(TestCase):
    """Verify platform handles invalid states correctly."""

    def test_tenant_without_plan_is_still_functional(self):
        """Tenant without plan can still operate (activate, suspend)."""
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.create(
            name=f"no-plan-{uuid.uuid4().hex[:8]}",
            slug=f"noplan-{uuid.uuid4().hex[:8]}",
            plan=None,
        )
        self.assertIsNone(tenant.plan)
        # Tenant with no plan should still be active and suspendable
        self.assertTrue(tenant.is_active())
        tenant.suspend()
        self.assertTrue(tenant.is_suspended())

    def test_suspended_tenant_cannot_publish(self):
        """Suspended tenant cannot publish to marketplace."""
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.create(
            name=f"suspended-{uuid.uuid4().hex[:8]}",
            slug=f"susp-{uuid.uuid4().hex[:8]}",
            status="SUSPENDED",
            kyc_status="VERIFIED",
        )
        self.assertFalse(tenant.can_publish_to_marketplace())

    def test_deleted_tenant_cannot_be_suspended(self):
        """Deleted tenant raises ValueError on suspend."""
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.create(
            name=f"deleted-{uuid.uuid4().hex[:8]}",
            slug=f"del-{uuid.uuid4().hex[:8]}",
            status="DELETED",
        )
        with self.assertRaises(ValueError):
            tenant.suspend()

    def test_invalid_kyc_status_blocks_publish(self):
        """Unverified KYC blocks marketplace publishing."""
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.create(
            name=f"unverified-{uuid.uuid4().hex[:8]}",
            slug=f"unver-{uuid.uuid4().hex[:8]}",
            kyc_status="UNVERIFIED",
        )
        self.assertFalse(tenant.can_publish_to_marketplace())


class TestDeveloperErrorCases(TestCase):
    """Verify developer-facing error paths."""

    def _create_tenant(self):
        from hub.apps.tenants.models import Tenant

        return Tenant.objects.create(
            name=f"dev-test-{uuid.uuid4().hex[:8]}",
            slug=f"devt-{uuid.uuid4().hex[:8]}",
        )

    def test_api_key_create_and_lookup(self):
        """APIKey can be created in DB and looked up by key_hash."""
        from hub.apps.auth.models import APIKey

        tenant = self._create_tenant()
        raw_key = APIKey.generate_key()
        key_hash = APIKey.hash_key(raw_key)
        api_key = APIKey.objects.create(
            tenant=tenant,
            name="test-key",
            key_hash=key_hash,
        )
        fetched = APIKey.objects.get(key_hash=key_hash)
        self.assertEqual(fetched.pk, api_key.pk)

    def test_api_key_hash_is_deterministic_sha256(self):
        """hash_key produces a deterministic SHA-256 hex digest different from input."""
        from hub.apps.auth.models import APIKey

        raw_key = "test-known-input-1234"
        hashed = APIKey.hash_key(raw_key)
        expected = hashlib.sha256(raw_key.encode()).hexdigest()
        self.assertEqual(hashed, expected)
        self.assertNotEqual(hashed, raw_key)
        self.assertEqual(len(hashed), 64)  # SHA-256 hex length

    def test_api_key_expiration_check(self):
        """is_expired returns True for past expiry, False for future expiry."""
        from hub.apps.auth.models import APIKey

        tenant = self._create_tenant()
        expired_key = APIKey.objects.create(
            tenant=tenant,
            name="expired-key",
            key_hash=APIKey.hash_key(APIKey.generate_key()),
            expires_at=timezone.now() - timedelta(hours=1),
        )
        self.assertTrue(expired_key.is_expired())

        valid_key = APIKey.objects.create(
            tenant=tenant,
            name="valid-key",
            key_hash=APIKey.hash_key(APIKey.generate_key()),
            expires_at=timezone.now() + timedelta(hours=1),
        )
        self.assertFalse(valid_key.is_expired())

        no_expiry_key = APIKey.objects.create(
            tenant=tenant,
            name="no-expiry-key",
            key_hash=APIKey.hash_key(APIKey.generate_key()),
            expires_at=None,
        )
        self.assertFalse(no_expiry_key.is_expired())

    def test_api_key_revocation(self):
        """Revoking an APIKey sets revoked_at and is_revoked returns True."""
        from hub.apps.auth.models import APIKey

        tenant = self._create_tenant()
        api_key = APIKey.objects.create(
            tenant=tenant,
            name="revoke-test",
            key_hash=APIKey.hash_key(APIKey.generate_key()),
        )
        self.assertFalse(api_key.is_revoked())
        self.assertTrue(api_key.is_active())

        api_key.revoke()
        api_key.refresh_from_db()
        self.assertTrue(api_key.is_revoked())
        self.assertFalse(api_key.is_active())
        self.assertIsNotNone(api_key.revoked_at)
