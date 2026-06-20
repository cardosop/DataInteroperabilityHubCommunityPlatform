"""
Tests for MVP audit fixes — glittery-dreaming-micali.md verified items.

B3  — token_version incremented on user disable
B5  — accept_invitation returns refresh_token in body mode
G2.2 — UserCreateSerializer rejects client-supplied status
NEW-1 — production settings guard for SECURE_SSL_REDIRECT

All tests use real DB state and real auth flows (no mocks).
"""

import hashlib
import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _seed(password="testpass123", **extra):
    uid = uuid.uuid4().hex[:8]
    tenant = Tenant.objects.create(
        name=f"t-{uid}",
        slug=f"t-{uid}",
        status="ACTIVE",
        kyc_status="UNVERIFIED",
    )
    user = User.objects.create_user(
        email=f"u-{uid}@example.com",
        password=password,
        tenant=tenant,
        status=UserStatus.ACTIVE,
        **extra,
    )
    return user, tenant


def _grant(user, tenant, role_name):
    role, _ = Role.objects.get_or_create(
        tenant=tenant, name=role_name, defaults={"description": role_name}
    )
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)


# ------------------------------------------------------------------
# B3 — token_version must be incremented when a user is disabled
# ------------------------------------------------------------------


class TokenVersionOnDisableTest(TestCase):
    """Disabling a user must invalidate existing JWTs by bumping
    token_version. Before the fix, disabled users' sessions stayed
    alive until natural token expiry."""

    def test_soft_delete_increments_token_version(self):
        user, tenant = _seed()
        admin, _ = _seed()
        admin.tenant = tenant
        admin.save(update_fields=["tenant"])
        _grant(admin, tenant, "TENANT_ADMIN")

        old_version = user.token_version

        # Give user a resource so delete_user does a soft-delete (DISABLED)
        from hub.apps.assets.models import Asset

        Asset.objects.create(
            tenant=tenant,
            key=f"res-{uuid.uuid4().hex[:8]}",
            name="Blocker",
            created_by=user,
        )

        from hub.apps.users.services import UserService

        svc = UserService()
        result = svc.delete_user(
            user_id=str(user.id),
            actor_user_id=str(admin.id),
            tenant_id=str(tenant.id),
        )
        assert result is True  # soft-delete path

        user.refresh_from_db()
        assert user.status == UserStatus.DISABLED
        assert user.token_version > old_version, (
            "token_version must be incremented on disable so existing JWTs "
            "are rejected by the auth middleware"
        )

    def test_hard_delete_does_not_need_version_bump(self):
        """Hard-deleted users are gone entirely — no version to check."""
        user, tenant = _seed()
        admin, _ = _seed()
        admin.tenant = tenant
        admin.save(update_fields=["tenant"])
        _grant(admin, tenant, "TENANT_ADMIN")

        from hub.apps.users.services import UserService

        svc = UserService()
        result = svc.delete_user(
            user_id=str(user.id),
            actor_user_id=str(admin.id),
            tenant_id=str(tenant.id),
        )
        assert result is False  # hard-delete path
        assert not User.objects.filter(id=user.id).exists()


# ------------------------------------------------------------------
# B5 — accept_invitation must return refresh_token in body mode
# ------------------------------------------------------------------


class AcceptInvitationRefreshTokenTest(TestCase):
    """When USE_HTTPONLY_AUTH_COOKIES is False (body mode, production
    default), the /auth/accept-invitation/ response must include
    refresh_token in the JSON body so the SPA can store and rotate it."""

    def setUp(self):
        self.client = APIClient()
        self.user, self.tenant = _seed()
        # Set user as INVITED with a valid invitation token
        plaintext = str(uuid.uuid4())
        self.user.status = UserStatus.INVITED
        self.user.invitation_token = hashlib.sha256(plaintext.encode()).hexdigest()
        self.user.invitation_token_expires_at = timezone.now() + timedelta(hours=24)
        self.user.invitation_token_used_at = None
        self.user.save()
        self.plaintext_token = plaintext

    @override_settings(USE_HTTPONLY_AUTH_COOKIES=False)
    def test_body_mode_response_contains_refresh_token(self):
        resp = self.client.post(
            "/api/v1/auth/accept-invitation/",
            {
                "token": self.plaintext_token,
                "password": "NewStrongPass99!",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK, resp.content
        body = resp.json()
        assert "access_token" in body, "body-mode response must include access_token"
        assert "refresh_token" in body, (
            "body-mode response must include refresh_token so the SPA can "
            "store and rotate it — otherwise the session dies at access_token "
            "expiry with no way to refresh"
        )

    @override_settings(USE_HTTPONLY_AUTH_COOKIES=True)
    def test_cookie_mode_does_not_leak_tokens_in_body(self):
        resp = self.client.post(
            "/api/v1/auth/accept-invitation/",
            {
                "token": self.plaintext_token,
                "password": "NewStrongPass99!",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK, resp.content
        body = resp.json()
        # In cookie mode tokens must NOT appear in the body
        assert "access_token" not in body
        assert "refresh_token" not in body


# ------------------------------------------------------------------
# G2.2 — UserCreateSerializer must not let clients set status
# ------------------------------------------------------------------


class UserCreateSerializerStatusTest(TestCase):
    """A client sending 'status': 'ACTIVE' on user creation must not
    bypass the invitation workflow."""

    def setUp(self):
        self.client = APIClient()
        self.admin, self.tenant = _seed()
        _grant(self.admin, self.tenant, "TENANT_ADMIN")
        self.client.force_authenticate(user=self.admin)

        from hub.apps.testing.billing_support import (
            ensure_tenant_has_active_subscription,
        )

        ensure_tenant_has_active_subscription(self.tenant)

    def test_client_cannot_override_status_to_active(self):
        resp = self.client.post(
            "/api/v1/users/",
            {
                "email": f"victim-{uuid.uuid4().hex[:8]}@example.com",
                "tenant": str(self.tenant.id),
                "status": "ACTIVE",
                "send_invitation": True,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        created = User.objects.get(id=resp.json()["id"])
        # With send_invitation=True the status MUST be INVITED,
        # regardless of what the client sent.
        self.assertEqual(created.status, UserStatus.INVITED)

    def test_default_invitation_flow_sets_invited_status(self):
        resp = self.client.post(
            "/api/v1/users/",
            {
                "email": f"norm-{uuid.uuid4().hex[:8]}@example.com",
                "tenant": str(self.tenant.id),
                "send_invitation": True,
            },
            format="json",
        )
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED)
        created = User.objects.get(id=resp.json()["id"])
        self.assertEqual(created.status, UserStatus.INVITED)


# ------------------------------------------------------------------
# NEW-1 — production settings must fail fast without SSL guards
# ------------------------------------------------------------------


class ProductionSSLGuardTest(TestCase):
    """Production must fail to start if critical HTTPS settings are
    not explicitly enabled — same pattern as CORS_ALLOWED_ORIGINS.

    The guards must run BEFORE any unconditional `= True` override so
    that an env-var like `SESSION_COOKIE_SECURE=false` causes an
    immediate ImproperlyConfigured rather than being silently
    overwritten. We verify this structurally: the guard text must
    appear BEFORE any `SESSION_COOKIE_SECURE = True` line in the
    production block."""

    def test_production_block_guards_run_before_overrides(self):
        import re
        from pathlib import Path

        settings_path = Path(__file__).resolve().parents[3] / "settings.py"
        source = settings_path.read_text()

        # Find ALL production blocks — ``re.search`` picks the first one
        # (BaaS SSL at ~line 730), NOT the security-cookie guard block
        # at ~line 2540.  We iterate every block and select the one that
        # contains the security guards.
        prod_blocks = list(
            re.finditer(
                r'if ENVIRONMENT\s*==\s*["\']production["\']\s*:\s*\n'
                r"((?:\s+.+\n)+)",
                source,
            )
        )
        assert prod_blocks, "Production settings block not found"

        security_block = None
        for m in prod_blocks:
            candidate = m.group(1)
            if "SESSION_COOKIE_SECURE" in candidate and "ImproperlyConfigured" in candidate:
                security_block = candidate
                break
        assert security_block, (
            "Security guard production block not found — "
            "expected a production block containing both "
            "SESSION_COOKIE_SECURE and ImproperlyConfigured"
        )
        block = security_block

        # Guards must be present.
        assert "ImproperlyConfigured" in block, (
            "Production block must contain ImproperlyConfigured guards"
        )
        assert "SESSION_COOKIE_SECURE" in block
        assert "CSRF_COOKIE_SECURE" in block
        assert "SECURE_SSL_REDIRECT" in block

        # Guards must NOT be preceded by unconditional `= True` for the
        # same variable — that would make the guard dead code (the
        # original bug caught in 225.5.review).
        guard_pos = block.index("ImproperlyConfigured")
        for var in (
            "SESSION_COOKIE_SECURE = True",
            "CSRF_COOKIE_SECURE = True",
        ):
            if var in block:
                assert block.index(var) > guard_pos, (
                    f"Guard for {var.split('=')[0].strip()} is dead code: "
                    f"'{var}' appears BEFORE the ImproperlyConfigured check. "
                    f"The guard must run first."
                )

        # HSTS should still be set unconditionally (not env-gated).
        assert "SECURE_HSTS_SECONDS" in block
