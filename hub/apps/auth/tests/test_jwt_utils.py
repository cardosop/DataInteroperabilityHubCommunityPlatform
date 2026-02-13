"""
Unit tests for JWT utilities.
"""

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase

from hub.apps.auth.jwt_utils import JWTTokenGenerator
from hub.apps.tenants.models import Tenant

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


class JWTUtilsTest(TestCase):
    """Test JWT utilities"""

    def setUp(self):
        """Set up test fixtures"""
        self.tenant = Tenant.objects.create(name="Test Tenant", slug="test-tenant")
        self.user = User.objects.create_user(
            email="test@example.com", password="testpass123", tenant=self.tenant
        )

    def test_generate_access_token_returns_string(self):
        """Test generate_access_token returns string."""
        token = JWTTokenGenerator.generate_access_token(
            user=self.user, tenant_id=str(self.tenant.id)
        )

        self.assertIsInstance(token, str)

    def test_generate_access_token_returns_non_empty(self):
        """Test generate_access_token returns non-empty token."""
        token = JWTTokenGenerator.generate_access_token(
            user=self.user, tenant_id=str(self.tenant.id)
        )

        self.assertGreater(len(token), 0)

    def test_decode_access_token_returns_payload(self):
        """Test decode_access_token returns payload."""
        token = JWTTokenGenerator.generate_access_token(
            user=self.user, tenant_id=str(self.tenant.id)
        )

        payload = JWTTokenGenerator.decode_access_token(token)

        self.assertIsNotNone(payload)

    def test_decode_access_token_has_correct_sub(self):
        """Test decode_access_token has correct sub."""
        token = JWTTokenGenerator.generate_access_token(
            user=self.user, tenant_id=str(self.tenant.id)
        )

        payload = JWTTokenGenerator.decode_access_token(token)

        self.assertEqual(payload["sub"], str(self.user.id))

    def test_decode_access_token_has_correct_tenant_id(self):
        """Test decode_access_token has correct tenant_id."""
        token = JWTTokenGenerator.generate_access_token(
            user=self.user, tenant_id=str(self.tenant.id)
        )

        payload = JWTTokenGenerator.decode_access_token(token)

        self.assertEqual(payload["tenant_id"], str(self.tenant.id))

    def test_decode_access_token_has_correct_email(self):
        """Test decode_access_token has correct email."""
        token = JWTTokenGenerator.generate_access_token(
            user=self.user, tenant_id=str(self.tenant.id)
        )

        payload = JWTTokenGenerator.decode_access_token(token)

        self.assertEqual(payload["email"], self.user.email)

    def test_decode_invalid_token_returns_none(self):
        """Test decode_access_token with invalid token returns None."""
        payload = JWTTokenGenerator.decode_access_token("invalid.token.here")
        self.assertIsNone(payload)

    def test_validate_token_version_valid_token_returns_true(self):
        """Test validate_token_version with valid token returns True."""
        token = JWTTokenGenerator.generate_access_token(
            user=self.user, tenant_id=str(self.tenant.id)
        )

        payload = JWTTokenGenerator.decode_access_token(token)
        is_valid = JWTTokenGenerator.validate_token_version(payload, self.user)

        self.assertTrue(is_valid)

    def test_validate_token_version_invalid_version_returns_false(self):
        """Test validate_token_version with invalid version returns False."""
        token = JWTTokenGenerator.generate_access_token(
            user=self.user, tenant_id=str(self.tenant.id)
        )

        payload = JWTTokenGenerator.decode_access_token(token)

        # Invalidate token version
        self.user.token_version += 1
        self.user.save()
        is_valid = JWTTokenGenerator.validate_token_version(payload, self.user)
        self.assertFalse(is_valid)

    def test_get_user_from_token_returns_correct_user(self):
        """Test get_user_from_token returns correct user."""
        token = JWTTokenGenerator.generate_access_token(
            user=self.user, tenant_id=str(self.tenant.id)
        )

        payload = JWTTokenGenerator.decode_access_token(token)
        user = JWTTokenGenerator.get_user_from_token(payload)

        self.assertEqual(user, self.user)

    # ========== EDGE CASES ==========

    def test_generate_access_token_with_none_tenant_id(self):
        """Test generate_access_token with None tenant_id (edge case)."""
        token = JWTTokenGenerator.generate_access_token(user=self.user, tenant_id=None)

        # Should handle gracefully
        self.assertIsInstance(token, str)

    def test_decode_access_token_empty_string_returns_none(self):
        """Test decode_access_token with empty string returns None."""
        payload = JWTTokenGenerator.decode_access_token("")
        self.assertIsNone(payload)

    def test_decode_access_token_malformed_token_returns_none(self):
        """Test decode_access_token with malformed token returns None."""
        payload = JWTTokenGenerator.decode_access_token("not.a.valid.jwt.token")
        self.assertIsNone(payload)

    # ========== ERROR HANDLING ==========

    def test_validate_token_version_with_none_payload_handles_gracefully(self):
        """Test validate_token_version with None payload handles gracefully."""
        is_valid = JWTTokenGenerator.validate_token_version(None, self.user)
        # Should return False or handle gracefully
        self.assertFalse(is_valid)

    def test_get_user_from_token_with_none_payload_handles_gracefully(self):
        """Test get_user_from_token with None payload handles gracefully."""
        user = JWTTokenGenerator.get_user_from_token(None)
        # Should return None or handle gracefully
        self.assertIsNone(user)
