"""
Unit tests for JWT utilities.
"""

import time
import uuid

import jwt as pyjwt
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
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(name=f"Test Tenant {uid}", slug=f"test-tenant-{uid}")
        self.user = User.objects.create_user(
            email=f"test-{uid}@example.com", password="testpass123", tenant=self.tenant
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

    def test_get_user_from_token_nonexistent_user_returns_none(self):
        """get_user_from_token with a sub pointing to a deleted user."""
        payload = {"sub": str(uuid.uuid4())}
        user = JWTTokenGenerator.get_user_from_token(payload)
        self.assertIsNone(user)

    def test_get_user_from_token_missing_sub_returns_none(self):
        """get_user_from_token with payload missing 'sub' claim."""
        payload = {"email": "test@example.com"}
        user = JWTTokenGenerator.get_user_from_token(payload)
        self.assertIsNone(user)


class JWTSecurityTest(TestCase):
    """Tests for JWT security properties: expiration, audience,
    signature, and token-version validation paths."""

    def setUp(self):
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"JWT Sec {uid}",
            slug=f"jwt-sec-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"jwtsec-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
        )

    # ── Expiration ────────────────────────────────────────────

    def test_expired_token_returns_none(self):
        """A token whose exp is in the past must be rejected."""
        _sign_key = (
            settings.JWT_PRIVATE_KEY
            if settings.JWT_ALGORITHM == "RS256"
            else settings.JWT_SECRET_KEY
        )
        payload = {
            "sub": str(self.user.id),
            "email": self.user.email,
            "tenant_id": str(self.tenant.id),
            "aud": ["idh-api-v1"],
            "iss": "hub",
            "exp": int(time.time()) - 60,  # 1 min ago
            "iat": int(time.time()) - 120,
            "nbf": int(time.time()) - 120,
            "authz_version": self.user.token_version,
        }
        token = pyjwt.encode(
            payload,
            _sign_key,
            algorithm=settings.JWT_ALGORITHM,
        )
        result = JWTTokenGenerator.decode_access_token(token)
        self.assertIsNone(result)

    # ── Audience ──────────────────────────────────────────────

    def test_wrong_audience_rejected(self):
        """Token with a different audience must be rejected."""
        _sign_key = (
            settings.JWT_PRIVATE_KEY
            if settings.JWT_ALGORITHM == "RS256"
            else settings.JWT_SECRET_KEY
        )
        payload = {
            "sub": str(self.user.id),
            "email": self.user.email,
            "aud": ["wrong-audience"],
            "iss": "hub",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "nbf": int(time.time()),
            "authz_version": self.user.token_version,
        }
        token = pyjwt.encode(
            payload,
            _sign_key,
            algorithm=settings.JWT_ALGORITHM,
        )
        result = JWTTokenGenerator.decode_access_token(token)
        self.assertIsNone(result)

    # ── Signature ─────────────────────────────────────────────

    def test_wrong_secret_rejected(self):
        """Token signed with a different secret must be rejected."""
        payload = {
            "sub": str(self.user.id),
            "email": self.user.email,
            "aud": ["idh-api-v1"],
            "iss": "hub",
            "exp": int(time.time()) + 3600,
            "iat": int(time.time()),
            "nbf": int(time.time()),
            "authz_version": self.user.token_version,
        }
        token = pyjwt.encode(
            payload,
            "attacker-secret-with-sufficient-length-for-hs256",
            algorithm="HS256",
        )
        result = JWTTokenGenerator.decode_access_token(token)
        self.assertIsNone(result)

    def test_tampered_payload_rejected(self):
        """Modifying a token's payload after signing invalidates it."""
        token = JWTTokenGenerator.generate_access_token(
            user=self.user,
            tenant_id=str(self.tenant.id),
        )
        # Tamper: flip a character in the payload section
        parts = token.split(".")
        self.assertEqual(len(parts), 3)
        tampered = list(parts[1])
        tampered[0] = "A" if tampered[0] != "A" else "B"
        parts[1] = "".join(tampered)
        tampered_token = ".".join(parts)
        result = JWTTokenGenerator.decode_access_token(tampered_token)
        self.assertIsNone(result)

    # ── Token version (production path) ───────────────────────

    def test_decode_with_verify_version_true_rejects_stale(self):
        """decode_access_token(verify_version=True) rejects tokens
        whose authz_version is older than the DB value."""
        token = JWTTokenGenerator.generate_access_token(
            user=self.user,
            tenant_id=str(self.tenant.id),
        )
        # Bump DB version after token was issued
        self.user.token_version += 1
        self.user.save(update_fields=["token_version"])

        result = JWTTokenGenerator.decode_access_token(
            token,
            verify_version=True,
        )
        self.assertIsNone(result)

    def test_decode_with_verify_version_false_allows_stale(self):
        """decode_access_token(verify_version=False) returns payload
        even when authz_version is stale (used for tenant scoping)."""
        token = JWTTokenGenerator.generate_access_token(
            user=self.user,
            tenant_id=str(self.tenant.id),
        )
        self.user.token_version += 1
        self.user.save(update_fields=["token_version"])

        result = JWTTokenGenerator.decode_access_token(
            token,
            verify_version=False,
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["sub"], str(self.user.id))

    # ── Payload claims completeness ───────────────────────────

    def test_token_contains_standard_claims(self):
        """Generated tokens include all required standard claims."""
        token = JWTTokenGenerator.generate_access_token(
            user=self.user,
            tenant_id=str(self.tenant.id),
        )
        payload = JWTTokenGenerator.decode_access_token(token)
        self.assertIsNotNone(payload)
        for claim in ("iss", "sub", "aud", "exp", "iat", "jti"):
            self.assertIn(claim, payload, f"Missing claim: {claim}")

    def test_token_contains_custom_claims(self):
        """Generated tokens include project-specific custom claims."""
        token = JWTTokenGenerator.generate_access_token(
            user=self.user,
            tenant_id=str(self.tenant.id),
        )
        payload = JWTTokenGenerator.decode_access_token(token)
        self.assertIsNotNone(payload)
        self.assertEqual(payload["tenant_id"], str(self.tenant.id))
        self.assertEqual(payload["email"], self.user.email)
        self.assertIn("authz_version", payload)
