"""
W11.2 (oss-release-remediation) — ASVS V2/V3 auth & session adversarial
matrix suite.

The vibe-code register rows 6 (broken authentication) and 8 (scopes/roles
as decoration) get ONE named test per matrix cell, live against the real
stack — no mocks:

* **SSO forged-token matrix** — the cells W1.5's battery did not carry:
  a well-formed token signed with an ATTACKER's RSA key that claims the
  IdP's ``kid`` (key-substitution / confused-kid), and the ES256 EC
  positive control (the JWK→public-key EC branch). The remaining cells
  (unsigned / alg-none / RS256→HS256 confusion / unknown-kid / wrong-aud
  / wrong-iss / expired / missing-sub / role-forgery / state-binding)
  live in ``test_sso_security_tokens.py`` + ``test_sso_state_binding.py``
  and are cited from the matrix doc.

* **JWT lifecycle matrix** — rotation (old revoked, tenant-pinned sibling,
  same family), grace (the W1.10 retry-only contract — pinned in
  ``test_refresh_grace_w110.py``), revocation (logout-all version bump,
  theft family-revoke, session listing ``is_current``), versioning
  (REST ``TOKEN_INVALIDATED``, GraphQL 401 — pinned in
  ``test_authentication_edge_cases.py`` / ``test_graphql_auth.py``).
  The new cells here: plain rotation, SSO-originated sessions carrying a
  refresh family, and the sessions-listing current-session identification.

* **API-key matrix (scope x endpoint x role)** — real keys minted against
  the real DB, real DRF endpoints (assets / transformation / integrations
  marketplace connections), covering: scope-gated writes, scope-gated
  reads, empty-scope keys, wildcard keys, role+scope interaction on the
  integrations write gate, platform-admin-owned keys (scope gate still
  applies), the cross-tenant X-Tenant-Id contract, and the minting
  escalation cells (API-key-authenticated mint bounded by the OWNER's
  live roles; worker-internal scopes unmintable; ``HasAnyScope`` wildcard).

Matrix doc: ``docs/security/adversarial-matrices/w112-auth-session-matrix.md``
(verified mechanically by ``scripts/tests/test_w112_matrix_veracity.py``).
"""

import time
import uuid
from datetime import timedelta

import jwt as pyjwt
import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory

from hub.apps.auth.jwt_utils import JWTTokenGenerator
from hub.apps.auth.models import APIKey, RefreshToken
from hub.apps.auth.permissions import HasAnyScope
from hub.apps.auth.tests.test_security_hardening import _create_user
from hub.apps.auth.tests.test_sso_security_tokens import (
    _b64u,
    _generated_rsa_keypair,
    _ScriptedIdP,
)
from hub.apps.tenants.models import KYCStatus, Tenant, TenantConfig
from hub.apps.testing.billing_support import ensure_tenant_has_active_subscription
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.security,
]

User = get_user_model()

REFRESH_URL = "/api/v1/auth/refresh/"
SESSIONS_URL = "/api/v1/auth/sessions/"
API_KEYS_URL = "/api/v1/auth/api-keys/"
SSO_CALLBACK_URL = "/api/v1/auth/sso/oidc/callback/"


def _generated_ec_keypair():
    """A REAL P-256 keypair (the ES256 JWK path control)."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1())
    numbers = private_key.private_numbers().public_numbers
    public_jwk = {
        "alg": "ES256",
        "crv": "P-256",
        "kid": "scripted-ec-key",
        "kty": "EC",
        "x": _b64u(numbers.x.to_bytes(32, "big")),
        "y": _b64u(numbers.y.to_bytes(32, "big")),
        "use": "sig",
    }
    private_pem = private_key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return private_pem, public_jwk


class SSOForgedTokenMatrixExtensionTest(TestCase):
    """The forged-token cells the W1.5 battery did not carry.

    A real scripted IdP over TCP (the W1.5 pattern) — the callback
    fetches the JWKS, so an attacker key not in the document MUST fail
    signature verification even when the token claims the IdP's ``kid``.
    """

    def setUp(self):
        cache.clear()
        self._private, self._public = _generated_rsa_keypair()
        self._idp = _ScriptedIdP({"keys": [self._public]})
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"W112 SSO Tenant {uid}",
            slug=f"w112-sso-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.issuer = f"{self._idp.base}/oidc"
        self.client_id = "w112-test-client"
        TenantConfig.objects.create(
            tenant=self.tenant,
            sso_config={
                "oidc": {
                    "authorization_endpoint": f"{self._idp.base}/oidc/v1/authorize",
                    "client_id": self.client_id,
                    "issuer": self.issuer,
                    "jwks_uri": self._idp.jwks_uri,
                }
            },
        )

    def tearDown(self):
        self._idp.close()

    def _issue_state(self):
        from hub.apps.auth import sso_state

        return sso_state.issue_state(str(self.tenant.id), "private")

    def _callback(self, id_token):
        client = APIClient()
        return client.post(
            SSO_CALLBACK_URL,
            {"id_token": id_token, "state": self._issue_state()},
            format="json",
        )

    def test_attacker_rsa_key_signed_token_400s(self):
        """A well-formed token signed with an attacker's RSA key that
        claims the IdP's ``kid`` (key substitution) — signature check
        fails, 400 classified, no user created."""
        attacker_private, _attacker_public = _generated_rsa_keypair()
        email = f"attacker-{uuid.uuid4().hex[:8]}@example.com"
        now = int(time.time())
        token = pyjwt.encode(
            {
                "iss": self.issuer,
                "aud": self.client_id,
                "sub": f"sub-{uuid.uuid4().hex[:8]}",
                "email": email,
                "exp": now + 300,
                "iat": now,
            },
            attacker_private,
            algorithm="RS256",
            headers={"kid": "scripted-idp-key"},  # the IdP's kid, the attacker's key
        )

        response = self._callback(token)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json()["error"], "OIDC_TOKEN_SIGNATURE_INVALID")
        self.assertFalse(User.objects.filter(email=email).exists())


class SSOES256PositiveControlTest(TestCase):
    """The EC half of the JWK→public-key conversion (ES256 accepted).

    W1.5 shipped RS/ES-only verification; the EC branch of
    ``_jwk_to_public_key`` had no live coverage — this cell proves an
    ES256-signed ID token over an EC JWKS authenticates end-to-end.
    """

    def setUp(self):
        cache.clear()
        self._private, self._public = _generated_ec_keypair()
        self._idp = _ScriptedIdP({"keys": [self._public]})
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"W112 EC Tenant {uid}",
            slug=f"w112-ec-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.issuer = f"{self._idp.base}/oidc"
        self.client_id = "w112-ec-client"
        TenantConfig.objects.create(
            tenant=self.tenant,
            sso_config={
                "oidc": {
                    "authorization_endpoint": f"{self._idp.base}/oidc/v1/authorize",
                    "client_id": self.client_id,
                    "issuer": self.issuer,
                    "jwks_uri": self._idp.jwks_uri,
                }
            },
        )

    def tearDown(self):
        self._idp.close()

    def test_es256_id_token_authenticates(self):
        from hub.apps.auth import sso_state

        email = f"ec-{uuid.uuid4().hex[:8]}@example.com"
        now = int(time.time())
        token = pyjwt.encode(
            {
                "iss": self.issuer,
                "aud": self.client_id,
                "sub": f"sub-{uuid.uuid4().hex[:8]}",
                "email": email,
                "exp": now + 300,
                "iat": now,
            },
            self._private,
            algorithm="ES256",
            headers={"kid": "scripted-ec-key"},
        )
        state = sso_state.issue_state(str(self.tenant.id), "private")

        response = APIClient().post(
            SSO_CALLBACK_URL,
            {"id_token": token, "state": state},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.json()["user"]["email"], email)
        self.assertTrue(User.objects.filter(email=email).exists())


class JWTLifecycleMatrixTest(TestCase):
    """Rotation / session-identification cells on the real refresh stack."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user, _password = _create_user()
        self.tenant = self.user.tenant

    def _refresh(self, token_str):
        return self.client.post(
            REFRESH_URL, {"refresh_token": token_str}, format="json"
        )

    def test_refresh_rotation_revokes_old_and_mints_tenant_pinned_sibling(self):
        """The plain rotation cell: presenting the CURRENT token revokes
        it, mints a same-family sibling (seq+1), and pins the tenant."""
        family_id = uuid.uuid4()
        old_raw = RefreshToken.generate_token()
        old = RefreshToken.objects.create(
            user=self.user,
            token_hash=RefreshToken.hash_token(old_raw),
            family_id=family_id,
            sequence_number=0,
            expires_at=timezone.now() + timedelta(hours=24),
            tenant_id=self.tenant.id,
        )

        response = self._refresh(old_raw)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.data)

        old.refresh_from_db()
        self.assertIsNotNone(old.revoked_at)

        sibling = RefreshToken.objects.get(family_id=family_id, sequence_number=1)
        self.assertIsNone(sibling.revoked_at)
        self.assertEqual(sibling.user, self.user)
        # AUTH-007 — the sibling stays pinned to the old row's tenant.
        self.assertEqual(sibling.tenant_id, old.tenant_id)

        # Exactly one new sibling — the family is 2 rows.
        seqs = list(
            RefreshToken.objects.filter(family_id=family_id)
            .order_by("sequence_number")
            .values_list("sequence_number", flat=True)
        )
        self.assertEqual(seqs, [0, 1])

    def test_list_sessions_marks_bearer_session_current(self):
        """The bearer's access JWT carries ``refresh_token_id`` — the
        sessions listing must mark THAT session ``is_current`` (not the
        most-recently-created fallback)."""
        older = RefreshToken.objects.create(
            user=self.user,
            token_hash=RefreshToken.hash_token(RefreshToken.generate_token()),
            family_id=uuid.uuid4(),
            sequence_number=0,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        newer = RefreshToken.objects.create(
            user=self.user,
            token_hash=RefreshToken.hash_token(RefreshToken.generate_token()),
            family_id=uuid.uuid4(),
            sequence_number=0,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        # The older row is the session that minted the bearer token.
        RefreshToken.objects.filter(pk=older.pk).update(
            created_at=timezone.now() - timedelta(hours=2)
        )
        token = JWTTokenGenerator.generate_access_token(
            self.user, refresh_token_id=str(older.id)
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = client.get(SESSIONS_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sessions = {s["id"]: s for s in response.json()}
        self.assertIn(str(older.id), sessions)
        self.assertIn(str(newer.id), sessions)
        self.assertTrue(sessions[str(older.id)]["is_current"])
        self.assertFalse(sessions[str(newer.id)]["is_current"])


class SSOSessionLifecycleTest(TestCase):
    """SSO-originated sessions are first-class lifecycle citizens: the
    callback mints a refresh family (rotation/revocation/sessions
    listing all work for SSO logins — parity with password login)."""

    def setUp(self):
        cache.clear()
        self._private, self._public = _generated_rsa_keypair()
        self._idp = _ScriptedIdP({"keys": [self._public]})
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"W112 Lifecycle Tenant {uid}",
            slug=f"w112-lifecycle-tenant-{uid}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        self.issuer = f"{self._idp.base}/oidc"
        self.client_id = "w112-lifecycle-client"
        TenantConfig.objects.create(
            tenant=self.tenant,
            sso_config={
                "oidc": {
                    "authorization_endpoint": f"{self._idp.base}/oidc/v1/authorize",
                    "client_id": self.client_id,
                    "issuer": self.issuer,
                    "jwks_uri": self._idp.jwks_uri,
                }
            },
        )

    def tearDown(self):
        self._idp.close()

    def test_sso_login_mints_refresh_family_and_links_session(self):
        from hub.apps.auth import sso_state

        email = f"lifecycle-{uuid.uuid4().hex[:8]}@example.com"
        now = int(time.time())
        token = pyjwt.encode(
            {
                "iss": self.issuer,
                "aud": self.client_id,
                "sub": f"sub-{uuid.uuid4().hex[:8]}",
                "email": email,
                "exp": now + 300,
                "iat": now,
            },
            self._private,
            algorithm="RS256",
            headers={"kid": "scripted-idp-key"},
        )
        state = sso_state.issue_state(str(self.tenant.id), "private")

        response = APIClient().post(
            SSO_CALLBACK_URL,
            {"id_token": token, "state": state},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)

        user = User.objects.get(email=email)
        rows = list(RefreshToken.objects.filter(user=user))
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertIsNone(row.revoked_at)
        self.assertEqual(row.sequence_number, 0)
        self.assertEqual(row.tenant_id, self.tenant.id)

        # The access JWT links the refresh row (the sessions-listing and
        # end-all-other-sessions contract), and the refresh cookie is set.
        access_token = response.json()["access_token"]
        payload = pyjwt.decode(access_token, options={"verify_signature": False})
        self.assertEqual(payload["refresh_token_id"], str(row.id))
        self.assertIn("refresh_token", response.cookies)
        # Non-cookie mode (test default): the refresh token also rides in
        # the body, exactly like password login.
        self.assertIn("refresh_token", response.json())

    def test_sso_session_rotates_via_refresh_endpoint(self):
        """The SSO-minted family participates in the normal rotation
        chain — refresh revokes the presented row and mints seq+1."""
        from hub.apps.auth import sso_state

        email = f"rotate-{uuid.uuid4().hex[:8]}@example.com"
        now = int(time.time())
        token = pyjwt.encode(
            {
                "iss": self.issuer,
                "aud": self.client_id,
                "sub": f"sub-{uuid.uuid4().hex[:8]}",
                "email": email,
                "exp": now + 300,
                "iat": now,
            },
            self._private,
            algorithm="RS256",
            headers={"kid": "scripted-idp-key"},
        )
        state = sso_state.issue_state(str(self.tenant.id), "private")
        login_response = APIClient().post(
            SSO_CALLBACK_URL,
            {"id_token": token, "state": state},
            format="json",
        )
        self.assertEqual(login_response.status_code, status.HTTP_200_OK)
        refresh_token_str = login_response.json()["refresh_token"]

        response = APIClient().post(
            REFRESH_URL, {"refresh_token": refresh_token_str}, format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access_token", response.json())
        user = User.objects.get(email=email)
        family_rows = list(
            RefreshToken.objects.filter(user=user).order_by("sequence_number")
        )
        self.assertEqual(len(family_rows), 2)
        self.assertIsNotNone(family_rows[0].revoked_at)
        self.assertIsNone(family_rows[1].revoked_at)
        self.assertEqual(family_rows[1].sequence_number, 1)


class APIKeyScopeEndpointRoleMatrixTest(TestCase):
    """Register row 8 — the scope x endpoint x role matrix against real
    DRF endpoints (assets / transformation / integrations)."""

    def setUp(self):
        cache.clear()
        uid = uuid.uuid4().hex[:8]
        self.tenant = Tenant.objects.create(
            name=f"W112 Matrix Tenant {uid}",
            slug=f"w112-matrix-tenant-{uid}",
            status="ACTIVE",
            kyc_status=KYCStatus.VERIFIED,
            transformation_enabled=True,
            marketplace_integrations_enabled=True,
        )
        ensure_tenant_has_active_subscription(self.tenant)
        self.roles = {}
        for name in ("DATA_PROVIDER", "DATA_CONSUMER", "TENANT_ADMIN"):
            self.roles[name], _created = Role.objects.get_or_create(
                tenant=self.tenant,
                name=name,
                defaults={"description": f"{name} fixture role"},
            )

    def _user(self, role=None, platform_admin=False):
        user = User.objects.create_user(
            email=f"matrix-{uuid.uuid4().hex[:8]}@example.com",
            password="testpass123",
            tenant=self.tenant,
            status=UserStatus.ACTIVE,
            is_platform_admin=platform_admin,
        )
        if role:
            UserRole.objects.create(user=user, tenant=self.tenant, role=self.roles[role])
        return user

    def _key(self, user, scopes):
        """A real DB API key owned by ``user`` (returns the plaintext)."""
        plaintext = APIKey.generate_key()
        APIKey.objects.create(
            tenant=self.tenant,
            user=user,
            key_hash=APIKey.hash_key(plaintext),
            name=f"matrix-key-{uuid.uuid4().hex[:8]}",
            scopes=list(scopes),
        )
        return plaintext

    @staticmethod
    def _key_client(plaintext):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"ApiKey {plaintext}")
        return client

    def _asset_payload(self):
        return {
            "key": f"matrix-asset-{uuid.uuid4().hex[:8]}",
            "name": "Matrix Asset",
            "description": "adversarial matrix cell",
            "domain": "marketing",
        }

    def _pipeline_payload(self):
        return {
            "name": f"Matrix Pipeline {uuid.uuid4().hex[:8]}",
            "description": "adversarial matrix cell",
            "pipeline_definition": {
                "version": "1.0.0",
                "steps": [
                    {
                        "name": "filter_step",
                        "type": "filter",
                        "config": {"filter_expression": "status == 'active'"},
                    }
                ],
            },
            "version": "1.0.0",
            "status": "DRAFT",
            "metadata": {"tags": ["matrix"]},
        }

    def _connection_payload(self):
        from hub.apps.integrations.base import MarketplaceType

        return {
            "marketplace_type": MarketplaceType.SNOWFLAKE_DATA_MARKETPLACE.value,
            "name": f"Matrix Connection {uuid.uuid4().hex[:8]}",
            "config": {"api_key": "test_key", "api_secret": "test_secret"},
            "is_active": True,
        }

    # ── assets: writes scope-gated, reads IsAuthenticated-only ───────────

    def test_key_assets_read_cannot_create_asset(self):
        user = self._user("DATA_PROVIDER")
        client = self._key_client(self._key(user, ["assets:read"]))

        response = client.post("/api/v1/assets/", self._asset_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_key_assets_write_creates_asset(self):
        user = self._user("DATA_PROVIDER")
        client = self._key_client(self._key(user, ["assets:write"]))

        response = client.post("/api/v1/assets/", self._asset_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_key_empty_scopes_denied_asset_create(self):
        user = self._user("DATA_PROVIDER")
        client = self._key_client(self._key(user, []))

        response = client.post("/api/v1/assets/", self._asset_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_key_wildcard_creates_asset(self):
        user = self._user("DATA_PROVIDER")
        client = self._key_client(self._key(user, ["*"]))

        response = client.post("/api/v1/assets/", self._asset_payload(), format="json")

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_key_assets_read_can_list_assets(self):
        """Reads are IsAuthenticated-only on assets (the designed
        posture) — the read-scoped key can list."""
        user = self._user("DATA_PROVIDER")
        client = self._key_client(self._key(user, ["assets:read"]))

        response = client.get("/api/v1/assets/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ── transformation: reads AND writes scope-gated ─────────────────────

    def test_key_unrelated_scope_denied_transformation_read(self):
        user = self._user("DATA_PROVIDER")
        client = self._key_client(self._key(user, ["assets:read"]))

        response = client.get("/api/v1/transformation/pipelines/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_key_transformation_read_lists_pipelines(self):
        user = self._user("DATA_PROVIDER")
        client = self._key_client(self._key(user, ["transformation:read"]))

        response = client.get("/api/v1/transformation/pipelines/")

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_key_transformation_read_cannot_create_pipeline(self):
        user = self._user("DATA_PROVIDER")
        client = self._key_client(self._key(user, ["transformation:read"]))

        response = client.post(
            "/api/v1/transformation/pipelines/", self._pipeline_payload(), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_key_transformation_write_creates_pipeline(self):
        user = self._user("DATA_PROVIDER")
        client = self._key_client(self._key(user, ["transformation:write"]))

        response = client.post(
            "/api/v1/transformation/pipelines/", self._pipeline_payload(), format="json"
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    # ── integrations: role + scope interact on the write gate ────────────

    def test_key_integrations_write_without_role_denied(self):
        """Scope alone is not enough: the owner's role must also satisfy
        HasAnyRole([DATA_PROVIDER, TENANT_ADMIN]) — a DATA_CONSUMER-owned
        key with integrations:write is denied."""
        user = self._user("DATA_CONSUMER")
        client = self._key_client(self._key(user, ["integrations:write"]))

        response = client.post(
            "/api/v1/integrations/marketplace/connections/",
            self._connection_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_key_integrations_read_with_role_denied(self):
        """Role alone is not enough either: a DATA_PROVIDER-owned key
        without the write scope is denied the write."""
        user = self._user("DATA_PROVIDER")
        client = self._key_client(self._key(user, ["integrations:read"]))

        response = client.post(
            "/api/v1/integrations/marketplace/connections/",
            self._connection_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_key_integrations_write_with_role_allowed(self):
        user = self._user("DATA_PROVIDER")
        client = self._key_client(self._key(user, ["integrations:write"]))

        response = client.post(
            "/api/v1/integrations/marketplace/connections/",
            self._connection_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_platform_admin_key_without_scope_denied(self):
        """The API-key scope gate has NO platform-admin bypass: a
        platform-admin-owned key without integrations:write is denied
        the role-gated write (the role check passes — the scope one
        does not)."""
        user = self._user(platform_admin=True)
        client = self._key_client(self._key(user, ["assets:read"]))

        response = client.post(
            "/api/v1/integrations/marketplace/connections/",
            self._connection_payload(),
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ── cross-tenant contract ────────────────────────────────────────────

    def test_key_with_foreign_xtenant_header_403(self):
        """A key for tenant A presented with X-Tenant-Id: tenant B is
        rejected (the middleware membership check) — no cross-tenant
        scoping through the header."""
        other = Tenant.objects.create(
            name=f"W112 Other {uuid.uuid4().hex[:8]}",
            slug=f"w112-other-{uuid.uuid4().hex[:8]}",
            status="ACTIVE",
            kyc_status="UNVERIFIED",
        )
        user = self._user("DATA_PROVIDER")
        plaintext = self._key(user, ["assets:read"])
        # NOTE: APIClient.credentials() REPLACES the set — both headers
        # go in ONE call (a second call wipes the Authorization header).
        client = APIClient()
        client.credentials(
            HTTP_AUTHORIZATION=f"ApiKey {plaintext}",
            HTTP_X_TENANT_ID=str(other.id),
        )

        response = client.get("/api/v1/auth/me/")

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    # ── minting escalation cells (register row 8) ────────────────────────

    def test_api_key_authenticated_mint_cannot_exceed_owner_roles(self):
        """A key minted while the owner held DATA_PROVIDER cannot mint
        sibling keys beyond the owner's LIVE roles after a downgrade —
        the allowlist comes from the owner's roles, never the presented
        key's own scopes."""
        user = self._user("DATA_PROVIDER")
        plaintext = self._key(user, ["assets:write", "assets:read"])
        # Downgrade: the owner no longer holds DATA_PROVIDER.
        UserRole.objects.filter(user=user).delete()
        UserRole.objects.create(
            user=user, tenant=self.tenant, role=self.roles["DATA_CONSUMER"]
        )

        client = self._key_client(plaintext)
        response = client.post(
            API_KEYS_URL,
            {"name": f"mint-{uuid.uuid4().hex[:8]}", "scopes": ["assets:write"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json().get("code"), "API_KEY_SCOPE_MINT_DENIED")

    def test_api_key_authenticated_mint_within_owner_roles_succeeds(self):
        """Control: the same key, while the owner's roles are intact,
        mints a subset of the role allowlist."""
        user = self._user("DATA_PROVIDER")
        plaintext = self._key(user, ["assets:write", "assets:read"])

        client = self._key_client(plaintext)
        response = client.post(
            API_KEYS_URL,
            {"name": f"mint-{uuid.uuid4().hex[:8]}", "scopes": ["assets:read"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_platform_admin_cannot_mint_scheduled_export_internal(self):
        """The worker-internal scopes are unmintable through the public
        API for EVERYONE — including the wildcard-holding platform admin
        (the same contract as ``scheduled_ingestion:internal``)."""
        admin = self._user(platform_admin=True)
        client = APIClient()
        client.force_authenticate(user=admin)

        response = client.post(
            API_KEYS_URL,
            {"name": f"mint-{uuid.uuid4().hex[:8]}", "scopes": ["scheduled_export:internal"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.json().get("code"), "API_KEY_SCOPE_MINT_DENIED")

    def test_has_any_scope_wildcard_covers_api_key(self):
        """HasAnyScope's API-key branch honors the wildcard exactly like
        the JWT branch — a ``*`` key satisfies any required scope set."""
        user = self._user("DATA_PROVIDER")
        request = APIRequestFactory().get("/")
        request.user = user
        request.api_key_scopes = ["*"]

        allowed = HasAnyScope(["assets:read"]).has_permission(request, None)

        self.assertTrue(allowed)

    def test_has_any_scope_limited_key_misses(self):
        """Control: a key without any required scope (and no wildcard)
        is denied by HasAnyScope."""
        user = self._user("DATA_PROVIDER")
        request = APIRequestFactory().get("/")
        request.user = user
        request.api_key_scopes = ["files:read"]

        allowed = HasAnyScope(["assets:read"]).has_permission(request, None)

        self.assertFalse(allowed)
