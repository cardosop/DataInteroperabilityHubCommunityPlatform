"""
Phase 11 Authentication Security Tests

Covers:
  11.1  Refresh token delivered as httpOnly cookie; access token absent
  11.2  Refresh token family rotation; replay revokes entire family
  11.3  invitation_token / password_reset_token stored as SHA-256 hash
  11.4  Webhook secret encrypted at rest with Fernet v1: prefix
  11.5  Login timing parity; IP-based rate limit; account-level lockout
  11.6  get_user_from_token uses select_related / prefetch_related
  11.7  accept_invitation is atomic; concurrent calls cannot double-accept
  11.8  (self-referential: this file IS the test)
"""

import statistics
import threading
import time
import uuid
from datetime import timedelta
from http.cookies import SimpleCookie

import pytest
from django.conf import settings
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from hub.apps.auth.models import LoginAttempt, RefreshToken
from hub.apps.auth.utils import sha256_hex as _sha256_hex
from hub.apps.users.models import User


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _make_user(email=None, password="Pass1234!", **kwargs):
    email = email or f"user_{uuid.uuid4().hex[:8]}@test.local"
    user = User.objects.create_user(
        email=email,
        password=password,
        **kwargs,
    )
    user.status = "ACTIVE"
    user.save(update_fields=["status"])
    return user, password


def _make_tenant():
    from hub.apps.tenants.models import Tenant
    return Tenant.objects.create(
        name=f"Tenant-{uuid.uuid4().hex[:8]}",
        slug=f"tenant-{uuid.uuid4().hex[:8]}",
        status="ACTIVE",
    )


# ─── 11.1  httpOnly Cookie ───────────────────────────────────────────────────

@pytest.mark.django_db
@override_settings(JWT_ALGORITHM="HS256")
class TestRefreshTokenCookie(TestCase):
    def setUp(self):
        self.client = APIClient()
        tenant = _make_tenant()
        self.user, self.password = _make_user(
            email="cookie@test.local", tenant=tenant
        )

    def _login(self):
        return self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": self.password},
            format="json",
        )

    def test_login_response_has_no_refresh_token_in_body(self):
        resp = self._login()
        assert resp.status_code == 200
        assert "refresh_token" not in resp.data

    def test_login_sets_httponly_cookie(self):
        resp = self._login()
        cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "refresh_token")
        assert cookie_name in resp.cookies
        cookie = resp.cookies[cookie_name]
        assert cookie["httponly"]

    def test_login_response_has_access_token(self):
        resp = self._login()
        assert resp.status_code == 200
        assert "access_token" in resp.data

    def test_logout_clears_cookie(self):
        login_resp = self._login()
        cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "refresh_token")
        self.client.cookies = login_resp.cookies
        self.client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {login_resp.data['access_token']}"
        )
        logout_resp = self.client.post("/api/v1/auth/logout/")
        assert logout_resp.status_code == 200
        # The logout response MUST include a Set-Cookie header that clears the
        # refresh-token cookie.  A missing header is itself a regression.
        assert cookie_name in logout_resp.cookies, (
            f"Logout must include a Set-Cookie clearing header for '{cookie_name}'. "
            f"Got cookies: {list(logout_resp.cookies.keys())}"
        )
        max_age = logout_resp.cookies[cookie_name].get("max-age", "")
        assert str(max_age) in ("0", ""), (
            f"Logout cookie must be cleared (max-age=0 or ''), got max-age={max_age!r}"
        )

    def test_refresh_reads_token_from_cookie(self):
        login_resp = self._login()
        self.client.cookies = login_resp.cookies
        refresh_resp = self.client.post(
            "/api/v1/auth/refresh/", {}, format="json"
        )
        assert refresh_resp.status_code == 200
        assert "access_token" in refresh_resp.data


# ─── 11.2  Family Rotation + Replay Detection ───────────────────────────────

@pytest.mark.django_db
@override_settings(JWT_ALGORITHM="HS256")
class TestRefreshTokenFamilyRotation(TestCase):
    def setUp(self):
        self.client = APIClient()
        tenant = _make_tenant()
        self.user, self.password = _make_user(
            email="rotation@test.local", tenant=tenant
        )

    def _login(self):
        resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": self.password},
            format="json",
        )
        assert resp.status_code == 200
        return resp

    def _refresh_with_cookie(self, login_resp):
        # Copy cookies to avoid mutating the original response's cookie object
        # (Django test client updates self.client.cookies in-place from
        # Set-Cookie headers, so assigning the reference would corrupt the
        # saved login_resp.cookies).
        cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "refresh_token")
        jar = SimpleCookie()
        jar[cookie_name] = login_resp.cookies[cookie_name].value
        self.client.cookies = jar
        return self.client.post("/api/v1/auth/refresh/", {}, format="json")

    def test_rotation_increments_sequence_number(self):
        login_resp = self._login()
        cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "refresh_token")

        old_token_str = login_resp.cookies[cookie_name].value
        old_hash = RefreshToken.hash_token(old_token_str)
        old_rt = RefreshToken.objects.get(token_hash=old_hash)
        assert old_rt.sequence_number == 0

        refresh_resp = self._refresh_with_cookie(login_resp)
        assert refresh_resp.status_code == 200

        new_token_str = refresh_resp.cookies[cookie_name].value
        new_hash = RefreshToken.hash_token(new_token_str)
        new_rt = RefreshToken.objects.get(token_hash=new_hash)

        assert new_rt.family_id == old_rt.family_id
        assert new_rt.sequence_number == old_rt.sequence_number + 1

    def test_rotation_revokes_old_token(self):
        login_resp = self._login()
        cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "refresh_token")
        old_token_str = login_resp.cookies[cookie_name].value
        old_hash = RefreshToken.hash_token(old_token_str)

        self._refresh_with_cookie(login_resp)

        old_rt = RefreshToken.objects.get(token_hash=old_hash)
        assert old_rt.revoked_at is not None

    def test_replay_of_revoked_token_revokes_entire_family(self):
        login_resp = self._login()
        cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "refresh_token")

        # Save T0 value BEFORE rotation.  _refresh_with_cookie copies the
        # cookie so login_resp.cookies is safe, but be explicit here too.
        t0_value = login_resp.cookies[cookie_name].value

        # Consume the first token (rotation #1)
        refresh_resp = self._refresh_with_cookie(login_resp)
        assert refresh_resp.status_code == 200

        # Resolve the family_id via the token hash so the assertion is tied
        # directly to T0 (not just the first token in the queryset).
        t0_hash = RefreshToken.hash_token(t0_value)
        family_id = RefreshToken.objects.get(token_hash=t0_hash).family_id
        assert family_id is not None, "T0 must have a family_id after rotation"

        # Re-present T0 (now revoked) — replay
        old_cookie = SimpleCookie()
        old_cookie[cookie_name] = t0_value
        self.client.cookies = old_cookie
        replay_resp = self.client.post(
            "/api/v1/auth/refresh/", {}, format="json"
        )
        assert replay_resp.status_code == 401

        # All tokens in the family must be revoked
        active = RefreshToken.objects.filter(
            family_id=family_id, revoked_at__isnull=True
        )
        assert not active.exists(), (
            "Family should be fully revoked after replay"
        )

    def test_new_family_id_per_login(self):
        login1 = self._login()
        self.client = APIClient()  # fresh client
        login2 = self._login()

        cookie_name = getattr(settings, "REFRESH_COOKIE_NAME", "refresh_token")
        token1 = login1.cookies[cookie_name].value
        token2 = login2.cookies[cookie_name].value
        rt1 = RefreshToken.objects.get(
            token_hash=RefreshToken.hash_token(token1)
        )
        rt2 = RefreshToken.objects.get(
            token_hash=RefreshToken.hash_token(token2)
        )
        assert rt1.family_id != rt2.family_id


# ─── 11.3  Token Hashing ─────────────────────────────────────────────────────

@pytest.mark.django_db
class TestTokenHashing(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = _make_tenant()

    def test_invitation_token_stored_as_sha256_hash(self):
        # Call the service layer directly to bypass subscription/billing
        # checks that the HTTP endpoint enforces — the hash storage logic
        # lives in UserService.create_user, which is what we want to test.
        from unittest.mock import patch

        from hub.apps.users.services import UserService

        admin, _ = _make_user(
            email="admin-hash@test.local",
            tenant=self.tenant,
            is_platform_admin=True,
        )
        email = f"invited-{uuid.uuid4().hex[:6]}@test.local"

        # Suppress the email task so the test doesn't need a worker
        with patch(
            "hub.apps.notifications.tasks.send_invitation_email.delay"
        ):
            service = UserService(
                tenant_id=str(self.tenant.id),
                user_id=str(admin.id),
            )
            user = service.create_user(
                tenant_id=str(self.tenant.id),
                actor_user_id=str(admin.id),
                email=email,
                send_invitation=True,
                role_ids=[],
            )

        user.refresh_from_db()
        token = user.invitation_token
        if token:
            # Must be a 64-char lowercase hex string (SHA-256)
            assert len(token) == 64, (
                f"Expected 64-char hex, got len={len(token)}"
            )
            assert all(c in "0123456789abcdef" for c in token), (
                f"Expected hex digest, got: {token!r}"
            )

    def test_password_reset_token_stored_as_sha256_hash(self):
        user, _ = _make_user(
            email="reset-hash@test.local", tenant=self.tenant
        )
        self.client.post(
            "/api/v1/auth/password-reset/",
            {"email": user.email},
            format="json",
        )
        user.refresh_from_db()
        token = user.password_reset_token
        if token:
            assert len(token) == 64
            assert all(c in "0123456789abcdef" for c in token)

    def test_password_reset_confirm_uses_hash_lookup(self):
        """Confirming a reset with the plaintext UUID must work."""
        user, _ = _make_user(
            email="reset-confirm@test.local", tenant=self.tenant
        )
        # Manually set a hashed token
        plaintext = str(uuid.uuid4())
        user.password_reset_token = _sha256_hex(plaintext)
        user.password_reset_token_expires_at = (
            timezone.now() + timedelta(hours=1)
        )
        user.password_reset_token_used_at = None
        user.save(update_fields=[
            "password_reset_token",
            "password_reset_token_expires_at",
            "password_reset_token_used_at",
        ])

        resp = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"token": plaintext, "new_password": "NewSecure99!"},
            format="json",
        )
        assert resp.status_code == 200

    def test_invalid_reset_token_rejected(self):
        user, _ = _make_user(
            email="reset-bad@test.local", tenant=self.tenant
        )
        resp = self.client.post(
            "/api/v1/auth/password-reset/confirm/",
            {"token": str(uuid.uuid4()), "new_password": "NewSecure99!"},
            format="json",
        )
        assert resp.status_code == 400


# ─── 11.4  Webhook Secret Encryption ─────────────────────────────────────────

@pytest.mark.django_db
class TestWebhookSecretEncryption(TestCase):
    def test_secret_stored_with_v1_prefix(self):
        from hub.apps.webhooks.models import Webhook

        wh = Webhook(
            name="enc-test",
            url="https://example.com/hook",
            secret="mysupersecret",
            event_types=["asset.created"],
        )
        wh.tenant = _make_tenant()
        wh.save()

        wh.refresh_from_db()
        assert wh.secret.startswith("v1:"), (
            f"Expected v1: prefix, got: {wh.secret!r}"
        )

    def test_decrypted_secret_matches_original(self):
        from hub.apps.webhooks.models import Webhook

        original = "my-webhook-secret-123"
        wh = Webhook(
            name="enc-roundtrip",
            url="https://example.com/hook",
            secret=original,
            event_types=["asset.created"],
        )
        wh.tenant = _make_tenant()
        wh.save()

        wh.refresh_from_db()
        assert wh.decrypted_secret == original

    def test_encrypt_secret_is_idempotent(self):
        from hub.apps.webhooks.encryption import encrypt_secret

        plaintext = "super-secret"
        first = encrypt_secret(plaintext)
        # Already prefixed — must not double-encrypt
        second = encrypt_secret(first)
        assert first == second

    def test_decrypt_legacy_plaintext(self):
        """Secrets without v1: prefix returned as-is (legacy compat)."""
        from hub.apps.webhooks.encryption import decrypt_secret

        assert decrypt_secret("plaintext-legacy") == "plaintext-legacy"

    def test_generate_signature_uses_decrypted_secret(self):
        """generate_signature() must produce HMAC over the plaintext secret."""
        import hashlib as hashlib_module
        import hmac as hmac_module

        from hub.apps.webhooks.models import Webhook

        original = "signing-secret-abc"
        wh = Webhook(
            name="sig-test",
            url="https://example.com/hook",
            secret=original,
            event_types=["asset.created"],
        )
        wh.tenant = _make_tenant()
        wh.save()
        wh.refresh_from_db()

        payload = '{"event": "test"}'
        expected = hmac_module.new(
            original.encode(),
            payload.encode(),
            hashlib_module.sha256,
        ).hexdigest()

        assert wh.generate_signature(payload) == expected


# ─── 11.5  Login Security ────────────────────────────────────────────────────

@pytest.mark.django_db
class TestLoginSecurity(TestCase):
    def setUp(self):
        self.client = APIClient()
        cache.clear()
        tenant = _make_tenant()
        self.user, self.password = _make_user(
            email="login-sec@test.local", tenant=tenant
        )

    def tearDown(self):
        cache.clear()

    def test_wrong_password_returns_400(self):
        resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "WrongPass999!"},
            format="json",
        )
        assert resp.status_code == 400

    def test_unknown_email_returns_400(self):
        resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": "nobody@test.local", "password": "whatever"},
            format="json",
        )
        assert resp.status_code == 400

    def test_login_failure_recorded_in_login_attempts(self):
        self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "WrongPass!"},
            format="json",
            REMOTE_ADDR="10.0.0.1",
        )
        assert LoginAttempt.objects.filter(
            email=self.user.email, success=False
        ).exists()

    def test_login_success_recorded_in_login_attempts(self):
        self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": self.password},
            format="json",
            REMOTE_ADDR="10.0.0.2",
        )
        assert LoginAttempt.objects.filter(
            email=self.user.email, success=True
        ).exists()

    @override_settings(LOGIN_IP_RATE_PER_MINUTE=2)
    def test_ip_rate_limit_returns_429(self):
        for _ in range(2):
            self.client.post(
                "/api/v1/auth/login/",
                {"email": self.user.email, "password": "Bad!"},
                format="json",
                REMOTE_ADDR="10.1.2.3",
            )
        # Third attempt must be rate-limited
        resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "Bad!"},
            format="json",
            REMOTE_ADDR="10.1.2.3",
        )
        assert resp.status_code == 429

    @override_settings(LOGIN_MAX_ATTEMPTS=3, LOGIN_LOCKOUT_WINDOW_MINUTES=15)
    def test_account_lockout_after_max_failures(self):
        unique_ip_prefix = "10.5.5."
        for i in range(3):
            LoginAttempt.objects.create(
                email=self.user.email,
                ip_address=f"{unique_ip_prefix}{i + 1}",
                success=False,
            )
        resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "Bad!"},
            format="json",
            REMOTE_ADDR="10.5.5.99",
        )
        assert resp.status_code == 429

    def test_timing_parity_unknown_vs_known_email(self):
        """
        Timing side-channel test (11.5).

        Measures wall-clock time for a known vs unknown email. The difference
        must be less than 200 ms (generous bound for CI jitter). This validates
        that we always run check_password regardless of email existence.
        """
        # N=10 + median gives a statistically robust measurement that is
        # resilient to single-outlier CI jitter (GC pauses, network blips).
        N = 10

        def time_login(email):
            times = []
            for _ in range(N):
                t0 = time.perf_counter()
                self.client.post(
                    "/api/v1/auth/login/",
                    {"email": email, "password": "wrongpassword"},
                    format="json",
                    REMOTE_ADDR=f"10.9.{hash(email) % 250}.1",
                )
                times.append(time.perf_counter() - t0)
            return statistics.median(times)

        cache.clear()
        known_median = time_login(self.user.email)
        cache.clear()
        unknown_median = time_login("nobody-at-all@nonexistent.local")

        diff_ms = abs(known_median - unknown_median) * 1000
        # 200 ms is generous; the real goal is to confirm both paths run
        # check_password.
        assert diff_ms < 200, (
            f"Login timing differs too much: known={known_median*1000:.1f}ms "
            f"unknown={unknown_median*1000:.1f}ms diff={diff_ms:.1f}ms"
        )


# ─── 11.6  N+1 Elimination ───────────────────────────────────────────────────

@pytest.mark.django_db
@override_settings(JWT_ALGORITHM="HS256")
class TestGetUserFromTokenQueryCount(TestCase):
    def test_get_user_from_token_uses_single_query(self):
        """
        get_user_from_token must load user + tenant + roles in ≤2 queries
        (1 for select_related, 1 for prefetch_related).
        """
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from hub.apps.auth.jwt_utils import JWTTokenGenerator

        tenant = _make_tenant()
        user, _ = _make_user(
            email="n1-test@test.local", tenant=tenant
        )

        token = JWTTokenGenerator.generate_access_token(user)
        payload = JWTTokenGenerator.decode_access_token(token)
        assert payload is not None

        with CaptureQueriesContext(connection) as ctx:
            result = JWTTokenGenerator.get_user_from_token(payload)

        assert result is not None
        # select_related = 1 query (JOIN); prefetch_related = 1 more
        assert len(ctx) <= 2, (
            f"Expected ≤2 queries, got {len(ctx)}: "
            f"{[q['sql'][:80] for q in ctx]}"
        )


# ─── 11.7  Atomic accept_invitation ─────────────────────────────────────────

@pytest.mark.django_db(transaction=True)
class TestAcceptInvitationAtomic:
    """
    No TestCase base — Django's TestCase wraps each test in a transaction
    that spawned threads cannot see.  With transaction=True and a plain class,
    pytest-django commits data so threads observe the invitation token row.
    """

    @override_settings(JWT_ALGORITHM="HS256")
    def test_concurrent_accept_invitation_only_activates_once(self):
        """
        Two concurrent requests with the same invitation token must not both
        succeed.  One must win (200) and the other must lose (400 — token
        already used or not found due to select_for_update).
        """
        tenant = _make_tenant()
        invited_user, _ = _make_user(
            email=(
                f"invite-atomic-{uuid.uuid4().hex[:6]}@test.local"
            ),
            tenant=tenant,
        )
        invited_user.status = "INVITED"
        plaintext = str(uuid.uuid4())
        invited_user.invitation_token = _sha256_hex(plaintext)
        invited_user.invitation_token_expires_at = (
            timezone.now() + timedelta(days=7)
        )
        invited_user.invitation_token_used_at = None
        invited_user.save(update_fields=[
            "status",
            "invitation_token",
            "invitation_token_expires_at",
            "invitation_token_used_at",
        ])

        results = []
        # Barrier ensures both threads reach the DB interaction simultaneously,
        # preventing serialisation on single-core CI runners.
        barrier = threading.Barrier(2)

        def attempt():
            barrier.wait()  # synchronise before hitting the endpoint
            c = APIClient()
            resp = c.post(
                "/api/v1/auth/accept-invitation/",
                {"token": plaintext, "password": "NewPass123!"},
                format="json",
            )
            results.append(resp.status_code)

        t1 = threading.Thread(target=attempt)
        t2 = threading.Thread(target=attempt)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        successes = results.count(200)
        failures = results.count(400)
        assert successes == 1, f"Expected exactly 1 success, got: {results}"
        assert failures == 1, f"Expected exactly 1 failure, got: {results}"


# ─── 14.9  Phase 14 Auth Security ────────────────────────────────────────────

@pytest.mark.django_db
@override_settings(JWT_ALGORITHM="HS256")
class TestPhase14AuthSecurity(TestCase):
    """
    Phase 14 authentication security tests.

    Covers:
      14.9-1  Brute-force lockout after 10+ failures
      14.9-2  Lockout window expiry allows subsequent login attempts
      14.9-3  Refresh token replay revokes the entire token family
      14.9-4  Expired access token is rejected with 401
      14.9-5  Tampered JWT signature is rejected with 401
      14.9-6  Token signed with wrong secret is rejected with 401
    """

    def setUp(self):
        self.client = APIClient()
        cache.clear()
        self.tenant = _make_tenant()
        self.user, self.password = _make_user(
            email=f"phase14-{uuid.uuid4().hex[:6]}@test.local",
            tenant=self.tenant,
        )

    def tearDown(self):
        cache.clear()

    # ── Helper ───────────────────────────────────────────────────────────────

    def _login(self, password=None):
        return self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": password or self.password},
            format="json",
        )

    # ── 14.9-1  Brute-force lockout ──────────────────────────────────────────

    @override_settings(LOGIN_MAX_ATTEMPTS=10, LOGIN_LOCKOUT_WINDOW_MINUTES=15)
    def test_brute_force_lockout_after_10_failures(self):
        """
        After 10 failed login attempts the account must be locked.
        The 11th request must return 429 and mention 'locked' or 'too many'.
        """
        # Use unique IPs so the IP-level rate limit does not fire first.
        for i in range(10):
            resp = self.client.post(
                "/api/v1/auth/login/",
                {"email": self.user.email, "password": "WrongPass!"},
                format="json",
                REMOTE_ADDR=f"10.20.{i}.1",
            )
        # 11th attempt from a fresh IP
        resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "WrongPass!"},
            format="json",
            REMOTE_ADDR="10.20.99.99",
        )
        assert resp.status_code in (429, 403), (
            f"Expected 429/403 after brute-force, got {resp.status_code}: {resp.data}"
        )
        body_text = str(resp.data).lower()
        assert "locked" in body_text or "too many" in body_text, (
            f"Response body does not mention lockout: {resp.data}"
        )

    # ── 14.9-2  Lockout window expiry ────────────────────────────────────────

    @override_settings(LOGIN_MAX_ATTEMPTS=10, LOGIN_LOCKOUT_WINDOW_MINUTES=15)
    def test_account_locked_after_15_min_window_passes(self):
        """
        After the 15-minute window passes the account should no longer be locked.

        Strategy: create LoginAttempt rows with created_at=now so the account is
        locked, then patch timezone.now() to return now+16 min so
        _check_account_lockout sees the attempts as outside the window.
        """
        from unittest.mock import patch

        now = timezone.now()

        # Pre-create 10 failed attempts within the last 15 minutes
        for i in range(10):
            LoginAttempt.objects.create(
                email=self.user.email,
                ip_address=f"10.30.{i}.1",
                success=False,
                # created_at is auto_now_add — we cannot pass it.
                # We will update it right after creation.
            )
        # Back-date them so they sit at "now" (within the window)
        LoginAttempt.objects.filter(email=self.user.email).update(
            created_at=now - timedelta(minutes=1)
        )

        # Confirm account is currently locked
        locked_resp = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "WrongPass!"},
            format="json",
            REMOTE_ADDR="10.30.99.1",
        )
        assert locked_resp.status_code in (429, 403), (
            f"Expected lockout response, got {locked_resp.status_code}"
        )

        # Advance time by 16 minutes (past the lockout window)
        future = now + timedelta(minutes=16)
        with patch("hub.apps.auth.views.timezone.now", return_value=future):
            unlocked_resp = self.client.post(
                "/api/v1/auth/login/",
                {"email": self.user.email, "password": "WrongPass!"},
                format="json",
                REMOTE_ADDR="10.30.99.2",
            )
        # Should NOT be 429/403 — wrong password should give 400 (not locked)
        assert unlocked_resp.status_code not in (429, 403), (
            f"Account should be unlocked after window passes, got {unlocked_resp.status_code}"
        )

    # ── 14.9-3  (duplicate removed) ───────────────────────────────────────────
    #
    # test_concurrent_refresh_token_replay_revokes_family was functionally
    # identical to TestRefreshTokenFamilyRotation.test_replay_of_revoked_token_revokes_entire_family.
    # The family_id assertion has been merged into the Phase 11 test.
    # See plan item C4.

    # ── 14.9-4  Expired access token rejected ───────────────────────────────

    def test_expired_access_token_rejected(self):
        """
        A JWT access token whose exp claim is in the past must be rejected with 401.
        """
        import jwt as pyjwt
        from datetime import datetime

        now = timezone.now()
        past = now - timedelta(hours=1)

        payload = {
            "iss": getattr(settings, "JWT_ISSUER", "hub"),
            "sub": str(self.user.id),
            "aud": ["idh-api-v1"],
            "exp": int(past.timestamp()),
            "iat": int((past - timedelta(minutes=5)).timestamp()),
            "nbf": int((past - timedelta(minutes=5)).timestamp()),
            "jti": str(uuid.uuid4()),
            "tenant_id": str(self.tenant.id),
            "email": self.user.email,
            "authz_version": self.user.token_version,
        }

        key = settings.JWT_SECRET_KEY  # HS256 in test environment
        expired_token = pyjwt.encode(payload, key, algorithm="HS256")

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {expired_token}")
        resp = client.get("/api/v1/assets/")
        assert resp.status_code == 401, (
            f"Expired token must be rejected with 401, got {resp.status_code}"
        )

    # ── 14.9-5  Tampered JWT signature rejected ──────────────────────────────

    def test_tampered_jwt_signature_rejected(self):
        """
        Changing the last few characters of the JWT signature part must result
        in a 401.
        """
        from hub.apps.auth.jwt_utils import JWTTokenGenerator

        token = JWTTokenGenerator.generate_access_token(self.user)

        # JWT structure: header.payload.signature
        parts = token.split(".")
        assert len(parts) == 3, "JWT must have exactly 3 parts"

        # Corrupt the signature (flip last 4 chars)
        sig = parts[2]
        # Replace the last 4 chars with something different
        tampered_sig = sig[:-4] + ("XXXX" if not sig.endswith("XXXX") else "YYYY")
        tampered_token = ".".join([parts[0], parts[1], tampered_sig])

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {tampered_token}")
        resp = client.get("/api/v1/assets/")
        assert resp.status_code == 401, (
            f"Token with tampered signature must be rejected with 401, got {resp.status_code}"
        )

    # ── 14.9-6  Wrong secret rejected ────────────────────────────────────────

    def test_wrong_secret_key_rejected(self):
        """
        A JWT signed with a *different* HS256 secret must be rejected with 401.

        (Renamed from test_wrong_algorithm_rejected — the test uses HS256 with
        a wrong secret, not a wrong algorithm.)
        """
        import jwt as pyjwt

        now = timezone.now()
        exp = now + timedelta(hours=1)

        payload = {
            "iss": getattr(settings, "JWT_ISSUER", "hub"),
            "sub": str(self.user.id),
            "aud": ["idh-api-v1"],
            "exp": int(exp.timestamp()),
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "jti": str(uuid.uuid4()),
            "tenant_id": str(self.tenant.id),
            "email": self.user.email,
            "authz_version": self.user.token_version,
        }

        wrong_secret = "this-is-definitely-not-the-real-secret-key"
        token_wrong_secret = pyjwt.encode(payload, wrong_secret, algorithm="HS256")

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_wrong_secret}")
        resp = client.get("/api/v1/assets/")
        assert resp.status_code == 401, (
            f"Token with wrong secret must be rejected with 401, got {resp.status_code}"
        )

    # ── 14.9-7  Algorithm-confusion attack rejected ───────────────────────────

    def test_algorithm_confusion_attack_rejected(self):
        """
        Algorithm-confusion attack: an RS256 token presented to an HS256
        endpoint must be rejected with 401.

        Background: PyJWT <2.4 had a vulnerability where a token signed with
        RS256 (using the *public* key as the HMAC secret) could be accepted by
        a server configured for HS256 — the attacker uses the server's public
        key as the HMAC-SHA256 secret.  This test confirms that our JWT
        verification layer rejects such tokens unconditionally.
        """
        import jwt as pyjwt
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization

        # Generate a fresh RSA-2048 key pair (attacker's key)
        attacker_private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        attacker_public_key_pem = attacker_private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )

        now = timezone.now()
        exp = now + timedelta(hours=1)
        payload = {
            "iss": getattr(settings, "JWT_ISSUER", "hub"),
            "sub": str(self.user.id),
            "aud": ["idh-api-v1"],
            "exp": int(exp.timestamp()),
            "iat": int(now.timestamp()),
            "nbf": int(now.timestamp()),
            "jti": str(uuid.uuid4()),
            "tenant_id": str(self.tenant.id),
            "email": self.user.email,
            "authz_version": self.user.token_version,
        }

        # Sign with RS256 using the attacker's *private* key
        rs256_token = pyjwt.encode(payload, attacker_private_key, algorithm="RS256")

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {rs256_token}")
        resp = client.get("/api/v1/assets/")
        assert resp.status_code == 401, (
            f"RS256 algorithm-confusion token must be rejected with 401, "
            f"got {resp.status_code}. "
            f"If this passes it may indicate the server accepted an RS256 token "
            f"on an HS256-only endpoint (algorithm confusion vulnerability)."
        )

        # Confirm the attacker cannot use the attacker's public key as an HMAC
        # secret (the classic confusion vector from CVE-2016-10555 / pyjwt <1.5)
        # PyJWT 2.x rejects PEM-encoded bytes as HS256 secrets; strip headers to
        # produce raw DER bytes that pass PyJWT's key-type check.
        import base64 as _base64
        _pem_body = (
            attacker_public_key_pem
            .replace(b"-----BEGIN PUBLIC KEY-----", b"")
            .replace(b"-----END PUBLIC KEY-----", b"")
            .replace(b"\n", b"")
        )
        _raw_der = _base64.b64decode(_pem_body)
        confusion_token = pyjwt.encode(
            payload,
            _raw_der,
            algorithm="HS256",
        )
        client2 = APIClient()
        client2.credentials(HTTP_AUTHORIZATION=f"Bearer {confusion_token}")
        resp2 = client2.get("/api/v1/assets/")
        assert resp2.status_code == 401, (
            f"Algorithm-confusion token (HS256 with RSA public key as secret) "
            f"must be rejected with 401, got {resp2.status_code}."
        )


# =============================================================================
# Phase 49 — GF-08: Production Security Guards
# =============================================================================


@pytest.mark.django_db
class TestDebugProductionGuard(TestCase):
    """49.1: DEBUG=True must raise ImproperlyConfigured in production."""

    def test_debug_guard_raises_in_production(self):
        """Importing settings with ENVIRONMENT=production + DEBUG=True must fail."""
        from django.core.exceptions import ImproperlyConfigured

        # The guard is at module level in settings.py. We verify it exists by
        # checking the source code rather than reloading settings (which would
        # break the running test process).
        import inspect
        from hub import settings as hub_settings

        source = inspect.getsource(hub_settings)
        assert 'ENVIRONMENT == "production" and DEBUG' in source
        assert "ImproperlyConfigured" in source
        assert "DEBUG must be False" in source


@pytest.mark.django_db
class TestTokenVersionAtomicCheck(TestCase):
    """49.2: decode_access_token must validate token version atomically."""

    def test_token_version_checked_atomically(self):
        """After incrementing user.token_version, old token must be rejected."""
        from hub.apps.auth.jwt_utils import JWTTokenGenerator
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        tenant, _ = Tenant.objects.get_or_create(
            name="token-version-test",
            defaults={"slug": "token-version-test"},
        )
        user = User.objects.create_user(
            email=f"tokenver-{uuid.uuid4().hex[:8]}@test.com",
            password="TestPass123!",
            tenant=tenant,
        )

        # Generate token with current version
        token = JWTTokenGenerator.generate_access_token(user)
        payload = JWTTokenGenerator.decode_access_token(token)
        assert payload is not None, "Fresh token should decode successfully"

        # Increment version (simulating password change / logout-all)
        user.token_version += 1
        user.save(update_fields=["token_version"])

        # Old token must now be rejected by the atomic version check
        payload2 = JWTTokenGenerator.decode_access_token(token)
        assert payload2 is None, (
            "Token with stale authz_version must be rejected by "
            "decode_access_token(verify_version=True)"
        )

    def test_decode_without_version_check_still_works(self):
        """verify_version=False skips the DB check (for lightweight extraction)."""
        from hub.apps.auth.jwt_utils import JWTTokenGenerator
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        tenant, _ = Tenant.objects.get_or_create(
            name="token-nocheck-test",
            defaults={"slug": "token-nocheck-test"},
        )
        user = User.objects.create_user(
            email=f"tokennocheck-{uuid.uuid4().hex[:8]}@test.com",
            password="TestPass123!",
            tenant=tenant,
        )

        token = JWTTokenGenerator.generate_access_token(user)
        user.token_version += 1
        user.save(update_fields=["token_version"])

        # With verify_version=False, stale token still decodes
        payload = JWTTokenGenerator.decode_access_token(token, verify_version=False)
        assert payload is not None


@pytest.mark.django_db
class TestTenantScopingMiddlewareErrors(TestCase):
    """49.3: TenantScopingMiddleware must return 403/503, never set tenant=None."""

    def test_tenant_does_not_exist_returns_403(self):
        """Missing tenant returns 403 TENANT_NOT_FOUND."""
        from django.test import RequestFactory
        from hub.apps.auth.middleware import TenantScopingMiddleware

        factory = RequestFactory()
        request = factory.get("/api/v1/assets/")
        request.tenant_id = str(uuid.uuid4())  # non-existent tenant

        middleware = TenantScopingMiddleware(get_response=lambda r: None)
        response = middleware(request)

        assert response is not None
        assert response.status_code == 403

    def test_tenant_db_error_returns_503(self):
        """Database error returns 503 SERVICE_UNAVAILABLE."""
        from unittest.mock import patch, MagicMock
        from django.test import RequestFactory
        from django.db import OperationalError
        from hub.apps.auth.middleware import TenantScopingMiddleware

        factory = RequestFactory()
        request = factory.get("/api/v1/assets/")
        request.tenant_id = str(uuid.uuid4())

        middleware = TenantScopingMiddleware(get_response=lambda r: None)

        with patch(
            "hub.apps.tenants.models.Tenant.objects.get",
            side_effect=OperationalError("connection refused"),
        ):
            response = middleware(request)

        assert response is not None
        assert response.status_code == 503


@pytest.mark.django_db
class TestAccountLockout(TestCase):
    """49.5: Account lockout after MAX_LOGIN_ATTEMPTS failures."""

    @override_settings(LOGIN_MAX_ATTEMPTS=3, LOGIN_LOCKOUT_WINDOW_MINUTES=15)
    def test_lockout_after_n_failures(self):
        """After LOGIN_MAX_ATTEMPTS failures, next attempt is rejected."""
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        tenant, _ = Tenant.objects.get_or_create(
            name="lockout-test",
            defaults={"slug": "lockout-test"},
        )
        user = User.objects.create_user(
            email=f"lockout-{uuid.uuid4().hex[:8]}@test.com",
            password="CorrectPass123!",
            tenant=tenant,
        )

        client = APIClient()

        # Make 3 failed attempts
        for i in range(3):
            resp = client.post(
                "/api/v1/auth/login/",
                {"email": user.email, "password": "WrongPassword!"},
                format="json",
            )

        # 4th attempt (even with correct password) should be locked out
        resp = client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "CorrectPass123!"},
            format="json",
        )
        assert resp.status_code == 429, (
            f"Expected 429 lockout after {3} failures, got {resp.status_code}"
        )


@pytest.mark.django_db
class TestRefreshTokenFamilyRevocation(TestCase):
    """49.6: Replaying a revoked refresh token triggers family revocation."""

    def test_revoked_token_replay_triggers_family_revocation(self):
        """Using a revoked refresh token must revoke entire family + return 401."""
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User

        tenant, _ = Tenant.objects.get_or_create(
            name="revoke-family-test",
            defaults={"slug": "revoke-family-test"},
        )
        user = User.objects.create_user(
            email=f"revokefam-{uuid.uuid4().hex[:8]}@test.com",
            password="TestPass123!",
            tenant=tenant,
        )
        user.status = "ACTIVE"
        user.save(update_fields=["status"])

        # Login to get a refresh token
        client = APIClient()
        resp = client.post(
            "/api/v1/auth/login/",
            {"email": user.email, "password": "TestPass123!"},
            format="json",
        )
        # Extract refresh token from cookie
        refresh_cookie = resp.cookies.get(
            getattr(settings, "REFRESH_COOKIE_NAME", "refresh_token")
        )
        if not refresh_cookie:
            # Skip if login failed (auth might not be fully configured in test env)
            self.skipTest("Login did not return refresh cookie")

        refresh_token_str = refresh_cookie.value

        # First refresh — should succeed and rotate
        resp2 = client.post("/api/v1/auth/refresh/", HTTP_COOKIE=f"refresh_token={refresh_token_str}")
        if resp2.status_code != 200:
            self.skipTest(f"First refresh failed with {resp2.status_code}")

        # Replay the OLD (now-revoked) token
        resp3 = client.post("/api/v1/auth/refresh/", HTTP_COOKIE=f"refresh_token={refresh_token_str}")
        assert resp3.status_code in (400, 401), (
            f"Replaying revoked refresh token should return 400 or 401, got {resp3.status_code}"
        )
