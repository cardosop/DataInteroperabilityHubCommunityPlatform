"""
Unit tests for JWT utilities.
"""

import time
import uuid

import jwt as pyjwt
import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

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


class JWTMutationCoverageTests(TestCase):
    """Detector tests for the W16 mutation run on jwt_utils.

    Each test pins behaviour that a specific mutant of the first run
    (2026-08-30, mutmut-security-money.yml baseline) silently broke —
    the suite survived 32 mutants, every one of them an unobserved branch
    or an unasserted claim. Re-running mutmut must show these killed.
    """

    def setUp(self):
        from hub.apps.users.models import Role, UserRole

        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"JWT Mut {uid}",
            slug=f"jwt-mut-{uid}",
        )
        self.user = User.objects.create_user(
            email=f"jwtmut-{uid}@example.com",
            password="testpass123",
            tenant=self.tenant,
            display_name="Mutation Hunter",
        )
        self.role = Role.objects.create(name=f"data-engineer-{uid}")
        UserRole.objects.create(user=self.user, role=self.role)

    # ── tenant derivation (mutants: `tenant_id is not None` flip, constant-None) ──

    def test_tenant_id_derived_from_user_when_not_passed(self):
        token = JWTTokenGenerator.generate_access_token(user=self.user, tenant_id=None)
        payload = JWTTokenGenerator.decode_access_token(token)
        assert payload["tenant_id"] == str(self.user.tenant.id)

    def test_tenantless_user_produces_no_tenant_claim(self):
        loner = User.objects.create_user(
            email=f"loner-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=None,
        )
        token = JWTTokenGenerator.generate_access_token(user=loner)
        payload = JWTTokenGenerator.decode_access_token(token)
        assert "tenant_id" not in payload

    def test_tenant_slug_claim_matches_user_tenant(self):
        token = JWTTokenGenerator.generate_access_token(user=self.user)
        payload = JWTTokenGenerator.decode_access_token(token)
        assert payload["tenant_slug"] == self.tenant.slug

    # ── roles derivation (mutants: roles-None default, attr string, list→None) ──

    def test_roles_derived_from_user_roles(self):
        token = JWTTokenGenerator.generate_access_token(user=self.user)
        payload = JWTTokenGenerator.decode_access_token(token)
        assert payload["roles"] == [self.role.name]

    def test_explicit_roles_override_derived(self):
        token = JWTTokenGenerator.generate_access_token(user=self.user, roles=["explicit-role"])
        payload = JWTTokenGenerator.decode_access_token(token)
        assert payload["roles"] == ["explicit-role"]

    # ── display_name / scopes / refresh_token_id claims (string + constant mutants) ──

    def test_display_name_claim_present_when_set(self):
        token = JWTTokenGenerator.generate_access_token(user=self.user)
        payload = JWTTokenGenerator.decode_access_token(token)
        assert payload["name"] == "Mutation Hunter"

    def test_scopes_claim_round_trips(self):
        token = JWTTokenGenerator.generate_access_token(
            user=self.user, scopes=["read:assets", "write:assets"]
        )
        payload = JWTTokenGenerator.decode_access_token(token)
        assert payload["scopes"] == ["read:assets", "write:assets"]

    def test_refresh_token_id_claim_round_trips(self):
        token = JWTTokenGenerator.generate_access_token(
            user=self.user, refresh_token_id="refresh-abc-123"
        )
        payload = JWTTokenGenerator.decode_access_token(token)
        assert payload["refresh_token_id"] == "refresh-abc-123"

    def test_nbf_claim_present_and_numeric(self):
        token = JWTTokenGenerator.generate_access_token(user=self.user)
        payload = JWTTokenGenerator.decode_access_token(token)
        assert isinstance(payload["nbf"], int)

    # ── issuer (attr-string + fallback-string mutants) ──

    def test_iss_uses_configured_issuer(self):
        with override_settings(JWT_ISSUER="test-issuer-w16"):
            token = JWTTokenGenerator.generate_access_token(user=self.user)
            payload = JWTTokenGenerator.decode_access_token(token)
        assert payload["iss"] == "test-issuer-w16"

    def test_iss_falls_back_to_hub_when_unset(self):
        original = getattr(settings, "JWT_ISSUER", None)
        try:
            if hasattr(settings, "JWT_ISSUER"):
                delattr(settings, "JWT_ISSUER")
            token = JWTTokenGenerator.generate_access_token(user=self.user)
            payload = JWTTokenGenerator.decode_access_token(token)
            assert payload["iss"] == "hub"
        finally:
            if original is not None:
                settings.JWT_ISSUER = original

    # ── algorithm branch strings (RS256 mutants) ──

    def test_rs256_round_trip_uses_keypair(self):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa

        private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode()
        public_pem = (
            private_key.public_key()
            .public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            .decode()
        )
        with override_settings(
            JWT_ALGORITHM="RS256",
            JWT_PRIVATE_KEY=private_pem,
            JWT_PUBLIC_KEY=public_pem,
        ):
            token = JWTTokenGenerator.generate_access_token(user=self.user)
            payload = JWTTokenGenerator.decode_access_token(token)
        assert payload["sub"] == str(self.user.id)

    # ── verify_version default + private validator branches (bool-flip mutants) ──

    def test_decode_default_rejects_stale_token(self):
        token = JWTTokenGenerator.generate_access_token(user=self.user)
        self.user.token_version += 1
        self.user.save(update_fields=["token_version"])
        payload = JWTTokenGenerator.decode_access_token(token)
        assert payload is None

    def test_validate_token_version_none_payload_is_false(self):
        assert not JWTTokenGenerator._validate_token_version(None)

    def test_validate_token_version_missing_sub_is_false(self):
        assert not JWTTokenGenerator._validate_token_version({"email": "x@y.z"})

    def test_validate_token_version_unknown_user_is_false(self):
        assert not JWTTokenGenerator._validate_token_version({"sub": str(uuid.uuid4())})

    def test_validate_token_version_missing_authz_version_defaults_to_zero(self):
        # payload without authz_version → default 0, but user.token_version
        # defaults to 1 on this model — so the check must reject. A mutant
        # flipping the default to 1 would silently accept the token.
        assert not JWTTokenGenerator._validate_token_version({"sub": str(self.user.id)})
        assert not JWTTokenGenerator.validate_token_version({"sub": str(self.user.id)}, self.user)

    # ── staticmethod contract (decorator-removal mutants) ──

    def test_generate_access_token_callable_positionally_on_class(self):
        token = JWTTokenGenerator.generate_access_token(self.user)
        assert isinstance(token, str)

    def test_decode_callable_positionally_on_class(self):
        token = JWTTokenGenerator.generate_access_token(self.user)
        payload = JWTTokenGenerator.decode_access_token(token)
        assert payload["sub"] == str(self.user.id)
