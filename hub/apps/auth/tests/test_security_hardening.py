"""
Tests for auth security hardening — glittery-herding-graham.md.

Phase 1A — B2: Replay detection grace period for concurrent tabs
Phase 1B — F4: Rate limit on /auth/refresh/
Phase 2A — B2a: Cookie precedence in body mode
Phase 3A — B4: Logout race condition (select_for_update)

All tests use real DB state and real auth flows (no mocks).
"""

import uuid
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TransactionTestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from hub.apps.auth.models import RefreshToken
from hub.apps.tenants.models import Tenant
from hub.apps.users.models import Role, UserRole, UserStatus

pytestmark = pytest.mark.django_db(transaction=True)
User = get_user_model()


def _create_user(password="testpass123"):
    """Create a user with a tenant for testing."""
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
    )
    role, _ = Role.objects.get_or_create(
        tenant=tenant,
        name="DATA_PRODUCT_OWNER",
        defaults={"description": "DPO"},
    )
    UserRole.objects.get_or_create(user=user, tenant=tenant, role=role)
    return user, password


def _login(client, email, password):
    """Login and return the response data (access_token, refresh_token)."""
    resp = client.post(
        "/api/v1/auth/login/",
        {"email": email, "password": password},
        format="json",
    )
    assert resp.status_code == 200, f"Login failed: {resp.data}"
    return resp.data


def _create_token_family(user, family_id=None, count=1, seq_start=0, revoke_all_but_last=False):
    """Create a family of refresh tokens for testing.

    Returns list of (raw_token_str, RefreshToken object) tuples.
    """
    fid = family_id or uuid.uuid4()
    expires_at = timezone.now() + timedelta(hours=24)
    tokens = []
    for i in range(count):
        raw = RefreshToken.generate_token()
        token_hash = RefreshToken.hash_token(raw)
        obj = RefreshToken.objects.create(
            user=user,
            token_hash=token_hash,
            family_id=fid,
            sequence_number=seq_start + i,
            expires_at=expires_at,
        )
        tokens.append((raw, obj))
    if revoke_all_but_last and len(tokens) > 1:
        for raw, obj in tokens[:-1]:
            obj.revoke()
    return tokens


# ======================================================================
# Phase 1A — B2: Replay detection grace period for concurrent tabs
# ======================================================================


class ReplayDetectionGracePeriodTest(TransactionTestCase):
    """Concurrent tab refresh must NOT kill the family within the grace period.

    Scenario: Tab A refreshes, rotating token_old→token_new. Tab B presents
    token_old (now revoked) within 5 seconds. Instead of revoking the entire
    family (killing Tab A's session), the system should detect the concurrent
    rotation and allow Tab B to piggyback by rotating from token_new.
    """

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user, self.password = _create_user()

    @override_settings(REFRESH_TOKEN_GRACE_PERIOD_SECONDS=5)
    def test_revoked_token_within_grace_period_rotates_from_latest_sibling(self):
        """Tab B presenting a recently-revoked token should get a valid
        access_token instead of a 401 (family NOT revoked)."""
        family_id = uuid.uuid4()
        # Simulate Tab A's rotation: token_old is revoked, token_new is valid.
        token_old_raw = RefreshToken.generate_token()
        token_new_raw = RefreshToken.generate_token()

        RefreshToken.objects.create(
            user=self.user,
            token_hash=RefreshToken.hash_token(token_old_raw),
            family_id=family_id,
            sequence_number=0,
            expires_at=timezone.now() + timedelta(hours=24),
            revoked_at=timezone.now() - timedelta(seconds=2),  # revoked 2s ago
        )
        token_new = RefreshToken.objects.create(
            user=self.user,
            token_hash=RefreshToken.hash_token(token_new_raw),
            family_id=family_id,
            sequence_number=1,
            expires_at=timezone.now() + timedelta(hours=24),
            # created_at is auto_now_add, so it's "just now" (within grace)
        )

        # Tab B presents the revoked token_old
        resp = self.client.post(
            "/api/v1/auth/refresh/",
            {"refresh_token": token_old_raw},
            format="json",
        )

        self.assertEqual(
            resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.data}"
        )
        self.assertIn("access_token", resp.data)

        # token_new should now be revoked (it was rotated from)
        token_new.refresh_from_db()
        self.assertIsNotNone(
            token_new.revoked_at, "token_new should be revoked after grace rotation"
        )

        # A new seq=2 token should exist in the same family
        latest = (
            RefreshToken.objects.filter(family_id=family_id).order_by("-sequence_number").first()
        )
        self.assertEqual(latest.sequence_number, 2)
        self.assertIsNone(latest.revoked_at, "Latest token should be active")

    @override_settings(REFRESH_TOKEN_GRACE_PERIOD_SECONDS=5)
    def test_revoked_token_outside_grace_period_revokes_family(self):
        """A revoked token presented after the grace window should still
        trigger full family revocation (existing security behavior)."""
        family_id = uuid.uuid4()

        token_old_raw = RefreshToken.generate_token()
        token_new_raw = RefreshToken.generate_token()

        RefreshToken.objects.create(
            user=self.user,
            token_hash=RefreshToken.hash_token(token_old_raw),
            family_id=family_id,
            sequence_number=0,
            expires_at=timezone.now() + timedelta(hours=24),
            revoked_at=timezone.now() - timedelta(seconds=30),  # revoked 30s ago
        )
        # token_new was created 30s ago — outside the 5s grace window
        token_new = RefreshToken.objects.create(
            user=self.user,
            token_hash=RefreshToken.hash_token(token_new_raw),
            family_id=family_id,
            sequence_number=1,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        # Backdate created_at to 30s ago (outside grace)
        RefreshToken.objects.filter(pk=token_new.pk).update(
            created_at=timezone.now() - timedelta(seconds=30)
        )

        resp = self.client.post(
            "/api/v1/auth/refresh/",
            {"refresh_token": token_old_raw},
            format="json",
        )

        self.assertEqual(
            resp.status_code, 401, f"Expected 401, got {resp.status_code}: {resp.data}"
        )

        # Entire family should be revoked
        token_new.refresh_from_db()
        self.assertIsNotNone(token_new.revoked_at, "token_new should be revoked (family killed)")

    @override_settings(REFRESH_TOKEN_GRACE_PERIOD_SECONDS=0)
    def test_grace_period_zero_disables_grace(self):
        """When grace period is 0, even a fresh sibling triggers family revocation."""
        family_id = uuid.uuid4()

        token_old_raw = RefreshToken.generate_token()
        token_new_raw = RefreshToken.generate_token()

        RefreshToken.objects.create(
            user=self.user,
            token_hash=RefreshToken.hash_token(token_old_raw),
            family_id=family_id,
            sequence_number=0,
            expires_at=timezone.now() + timedelta(hours=24),
            revoked_at=timezone.now() - timedelta(seconds=1),
        )
        token_new = RefreshToken.objects.create(
            user=self.user,
            token_hash=RefreshToken.hash_token(token_new_raw),
            family_id=family_id,
            sequence_number=1,
            expires_at=timezone.now() + timedelta(hours=24),
        )

        resp = self.client.post(
            "/api/v1/auth/refresh/",
            {"refresh_token": token_old_raw},
            format="json",
        )

        self.assertEqual(resp.status_code, 401)
        token_new.refresh_from_db()
        self.assertIsNotNone(token_new.revoked_at, "Family should be revoked when grace=0")


# ======================================================================
# Phase 1B — F4: Rate limit on /auth/refresh/
# ======================================================================


class RefreshRateLimitTest(TransactionTestCase):
    """The /auth/refresh/ endpoint must enforce IP-level rate limiting."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user, self.password = _create_user()

    @override_settings(REFRESH_IP_RATE_PER_MINUTE=5, RATE_LIMIT_ENABLED=True)
    def test_refresh_rate_limited_after_threshold(self):
        """Requests beyond the threshold return 429."""
        # Login to get a valid refresh token
        login_data = _login(self.client, self.user.email, self.password)
        refresh_token_str = login_data["refresh_token"]

        # Create enough tokens for the test (each refresh rotates the token)
        tokens = [refresh_token_str]
        for i in range(5):
            raw = RefreshToken.generate_token()
            RefreshToken.objects.create(
                user=self.user,
                token_hash=RefreshToken.hash_token(raw),
                family_id=uuid.uuid4(),
                sequence_number=0,
                expires_at=timezone.now() + timedelta(hours=24),
            )
            tokens.append(raw)

        # Send 5 requests (should all succeed — at or under limit)
        for i in range(5):
            resp = self.client.post(
                "/api/v1/auth/refresh/",
                {"refresh_token": tokens[i]},
                format="json",
            )
            # Some may fail with 400 (invalid token from rotation), but none should be 429
            self.assertNotEqual(
                resp.status_code, 429, f"Request {i + 1} should not be rate-limited"
            )

        # 6th request should be rate-limited
        resp = self.client.post(
            "/api/v1/auth/refresh/",
            {"refresh_token": tokens[5]},
            format="json",
        )
        self.assertEqual(resp.status_code, 429, f"Expected 429, got {resp.status_code}")

    @override_settings(REFRESH_IP_RATE_PER_MINUTE=3, RATE_LIMIT_ENABLED=True)
    def test_different_ips_get_independent_limits(self):
        """Two different IPs should each get their own rate limit budget."""
        tokens = []
        for _ in range(4):
            raw = RefreshToken.generate_token()
            RefreshToken.objects.create(
                user=self.user,
                token_hash=RefreshToken.hash_token(raw),
                family_id=uuid.uuid4(),
                sequence_number=0,
                expires_at=timezone.now() + timedelta(hours=24),
            )
            tokens.append(raw)

        # 3 requests from IP-A (exhausts limit)
        for i in range(3):
            self.client.post(
                "/api/v1/auth/refresh/",
                {"refresh_token": tokens[i]},
                format="json",
                HTTP_X_FORWARDED_FOR="10.0.0.1",
            )

        # 4th from IP-A should be rate-limited
        resp_a = self.client.post(
            "/api/v1/auth/refresh/",
            {"refresh_token": tokens[3]},
            format="json",
            HTTP_X_FORWARDED_FOR="10.0.0.1",
        )
        self.assertEqual(resp_a.status_code, 429)

        # 1st from IP-B should NOT be rate-limited
        extra_raw = RefreshToken.generate_token()
        RefreshToken.objects.create(
            user=self.user,
            token_hash=RefreshToken.hash_token(extra_raw),
            family_id=uuid.uuid4(),
            sequence_number=0,
            expires_at=timezone.now() + timedelta(hours=24),
        )
        resp_b = self.client.post(
            "/api/v1/auth/refresh/",
            {"refresh_token": extra_raw},
            format="json",
            HTTP_X_FORWARDED_FOR="10.0.0.2",
        )
        self.assertNotEqual(resp_b.status_code, 429, "IP-B should not be rate-limited")


# ======================================================================
# Phase 2A — B2a: Cookie precedence in body mode
# ======================================================================


class CookiePrecedenceTest(TransactionTestCase):
    """In body mode, body token should take precedence over stale cookie."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user, self.password = _create_user()

    @override_settings(USE_HTTPONLY_AUTH_COOKIES=False)
    def test_body_mode_prefers_body_over_stale_cookie(self):
        """When USE_HTTPONLY_AUTH_COOKIES=False, body token should be used
        even when a stale cookie is present."""
        # Create a valid body token
        body_raw = RefreshToken.generate_token()
        RefreshToken.objects.create(
            user=self.user,
            token_hash=RefreshToken.hash_token(body_raw),
            family_id=uuid.uuid4(),
            sequence_number=0,
            expires_at=timezone.now() + timedelta(hours=24),
        )

        # Create a stale cookie token (expired)
        stale_raw = RefreshToken.generate_token()
        RefreshToken.objects.create(
            user=self.user,
            token_hash=RefreshToken.hash_token(stale_raw),
            family_id=uuid.uuid4(),
            sequence_number=0,
            expires_at=timezone.now() - timedelta(hours=1),  # expired
        )

        # Send request with BOTH cookie and body — body should win
        self.client.cookies["refresh_token"] = stale_raw
        resp = self.client.post(
            "/api/v1/auth/refresh/",
            {"refresh_token": body_raw},
            format="json",
        )

        # Should succeed (body token used, not stale cookie)
        self.assertEqual(
            resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.data}"
        )

    @override_settings(USE_HTTPONLY_AUTH_COOKIES=True)
    def test_cookie_mode_prefers_cookie(self):
        """When USE_HTTPONLY_AUTH_COOKIES=True, cookie should take precedence."""
        cookie_raw = RefreshToken.generate_token()
        RefreshToken.objects.create(
            user=self.user,
            token_hash=RefreshToken.hash_token(cookie_raw),
            family_id=uuid.uuid4(),
            sequence_number=0,
            expires_at=timezone.now() + timedelta(hours=24),
        )

        self.client.cookies["refresh_token"] = cookie_raw
        resp = self.client.post(
            "/api/v1/auth/refresh/",
            {"refresh_token": "this-should-be-ignored"},
            format="json",
        )

        self.assertEqual(
            resp.status_code, 200, f"Expected 200, got {resp.status_code}: {resp.data}"
        )


# ======================================================================
# Phase 3A — B4: Logout race condition
# ======================================================================


class LogoutAtomicTest(TransactionTestCase):
    """Logout should use select_for_update to prevent race conditions."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user, self.password = _create_user()

    def test_logout_revokes_specific_token(self):
        """Logout with a specific refresh token revokes only that token."""
        login_data = _login(self.client, self.user.email, self.password)
        access_token = login_data["access_token"]
        refresh_token_str = login_data["refresh_token"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        resp = self.client.post(
            "/api/v1/auth/logout/",
            {"refresh_token": refresh_token_str},
            format="json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data["revoked_sessions"], 1)

        # The token should now be revoked
        token_hash = RefreshToken.hash_token(refresh_token_str)
        token = RefreshToken.objects.get(token_hash=token_hash)
        self.assertIsNotNone(token.revoked_at)

    def test_logout_idempotent(self):
        """Logging out twice with the same token should not error."""
        login_data = _login(self.client, self.user.email, self.password)
        access_token = login_data["access_token"]
        refresh_token_str = login_data["refresh_token"]

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
        # First logout
        resp1 = self.client.post(
            "/api/v1/auth/logout/",
            {"refresh_token": refresh_token_str},
            format="json",
        )
        self.assertEqual(resp1.status_code, 200)

        # Second logout — same token, should be idempotent
        resp2 = self.client.post(
            "/api/v1/auth/logout/",
            {"refresh_token": refresh_token_str},
            format="json",
        )
        self.assertEqual(resp2.status_code, 200)
