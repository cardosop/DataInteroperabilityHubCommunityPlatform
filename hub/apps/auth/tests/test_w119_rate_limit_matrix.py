"""W11.9 (oss-release-remediation) — the auth-surface rate-limit matrix
(ASVS V13, register row 12).

One named endpoint-level test per surface: the 429 FIRES and — per the
Phase 273 contract — the per-surface audit row lands.  Real DRF stack,
real DB, no mocks (rates are shrunk via override_settings, the repo's
established throttle-pin pattern).

Cells:
* login IP rate → 429 + LOGIN_RATE_LIMIT_EXCEEDED (the pre-fix 429
  emitted only a metric);
* login account lockout → 429 + LOGIN_LOCKOUT_EXCEEDED;
* password-reset request → 429 + PASSWORD_RESET_RATE_LIMIT_EXCEEDED
  (endpoint-level — the pre-fix pins were function-level only);
* password-reset CONFIRM → throttled at all (the pre-fix gap: no
  throttle existed on the confirmation surface);
* SSO → 429 + SSO_RATE_LIMIT_EXCEEDED (the emission existed, zero
  assertions);
* register (cited — test_register_me.py pins the 429 + audit);
* API-key / BaaS / SPARQL (cited — the contract suite, now green).
"""

import uuid

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient, APIRequestFactory

from hub.apps.audit.models import AuditEvent
from hub.apps.auth.tests.test_security_hardening import _create_user

pytestmark = pytest.mark.django_db(transaction=True)

User = get_user_model()


def _audit_count(action: str) -> int:
    return AuditEvent.objects.filter(action=action).count()


class LoginRateLimitMatrixTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user, self.password = _create_user()

    def tearDown(self):
        # The shrunk rate overrides accumulate login_ip_rate entries —
        # clear them so later suites in the same process see a clean
        # bucket (the combined-run order dependence).
        cache.clear()

    @override_settings(RATE_LIMIT_ENABLED=True, LOGIN_IP_RATE_PER_MINUTE=2)
    def test_login_ip_rate_429_emits_login_rate_limit_audit(self):
        before = _audit_count("LOGIN_RATE_LIMIT_EXCEEDED")
        for _ in range(3):
            resp = self.client.post(
                "/api/v1/auth/login/",
                {"email": self.user.email, "password": "wrong"},
                format="json",
            )
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(_audit_count("LOGIN_RATE_LIMIT_EXCEEDED"), before + 1)

    @override_settings(RATE_LIMIT_ENABLED=True, LOGIN_MAX_ATTEMPTS=2, LOGIN_LOCKOUT_WINDOW_MINUTES=15)
    def test_login_lockout_429_emits_lockout_audit(self):
        before = _audit_count("LOGIN_LOCKOUT_EXCEEDED")
        for _ in range(3):
            resp = self.client.post(
                "/api/v1/auth/login/",
                {"email": self.user.email, "password": "wrong"},
                format="json",
            )
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(_audit_count("LOGIN_LOCKOUT_EXCEEDED"), before + 1)


class PasswordResetRateLimitMatrixTest(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.user, _password = _create_user()

    def tearDown(self):
        cache.clear()

    @override_settings(RATE_LIMIT_ENABLED=True)
    def test_reset_request_429_emits_audit_at_the_endpoint(self):
        """Six requests for the same email exceed the 5/hour per-email
        window — the SIXTH is the 429 (endpoint-level, the pre-fix pins
        were function-level only)."""
        before = _audit_count("PASSWORD_RESET_RATE_LIMIT_EXCEEDED")
        resp = None
        for _ in range(6):
            resp = self.client.post(
                "/api/v1/auth/password-reset/",
                {"email": self.user.email},
                format="json",
            )
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(
            _audit_count("PASSWORD_RESET_RATE_LIMIT_EXCEEDED"), before + 1
        )

    @override_settings(AUTH_PASSWORD_RESET_CONFIRM_RATE_LIMIT="2/hour")
    def test_reset_confirm_is_throttled(self):
        """The pre-fix gap: the confirmation endpoint had NO throttle —
        an unauthenticated caller could brute-force it freely.  The
        third confirm within the window is now 429."""
        resp = None
        for _ in range(3):
            resp = self.client.post(
                "/api/v1/auth/password-reset/confirm/",
                {"token": str(uuid.uuid4()), "new_password": "Str0ngPass!1"},
                format="json",
            )
        self.assertEqual(resp.status_code, status.HTTP_429_TOO_MANY_REQUESTS)


class SSOThrottleAuditTest(TestCase):
    def tearDown(self):
        cache.clear()
    """The SSO throttle's 429 audit emission (the code emitted it since
    W1.5 — zero test assertions existed until this cell)."""

    def test_sso_throttle_exhaustion_emits_sso_audit(self):
        from hub.apps.auth.throttles import SSOThrottle

        request = APIRequestFactory().post("/api/v1/auth/sso/oidc/callback/")
        request.META["REMOTE_ADDR"] = "127.0.0.1"
        from django.contrib.auth.models import AnonymousUser

        request.user = AnonymousUser()
        # The rate must be set BEFORE construction: SimpleRateThrottle
        # parses num_requests/duration in __init__ (the post-init
        # assignment in the first draft left the test-env default
        # parsed — RED-caught, the same class as the BaaS throttle).
        with override_settings(AUTH_SSO_RATE_LIMIT="2/min"):
            throttle = SSOThrottle()
        before = _audit_count("SSO_RATE_LIMIT_EXCEEDED")
        throttle.allow_request(request, None)
        throttle.allow_request(request, None)
        allowed = throttle.allow_request(request, None)
        self.assertFalse(allowed)
        self.assertEqual(_audit_count("SSO_RATE_LIMIT_EXCEEDED"), before + 1)


class W102ThrottleNoneKeySurvivalTest(TestCase):
    """W10.2 (oss-release-remediation) — the live staging soak found
    every SSO login-url 500ing with
    ``'SSOThrottle' object has no attribute 'history'``: DRF 3.16's
    SimpleRateThrottle.allow_request sets ``self.history`` ONLY on the
    cached-key path — a None cache key returns early without the
    attribute and the mixin's header math crashed.

    The mixin must degrade (empty bucket, no headers) instead of
    raising — pinned through the real throttle class with a None-key
    subclass (no mocks)."""

    def test_none_cache_key_does_not_crash(self):
        from hub.apps.auth.throttles import SSOThrottle

        class _NoKeySSOThrottle(SSOThrottle):
            def get_cache_key(self, request, view):
                return None  # the DRF 3.16 early-return path

        request = self.client.request().wsgi_request
        throttle = _NoKeySSOThrottle()
        allowed = throttle.allow_request(request, None)

        self.assertTrue(allowed)
        self.assertFalse(hasattr(throttle, "history"))

    def test_cached_key_path_still_emits_headers(self):
        from hub.apps.auth.throttles import SSOThrottle

        request = self.client.request().wsgi_request
        request.META["REMOTE_ADDR"] = "203.0.113.42"
        throttle = SSOThrottle()
        allowed = throttle.allow_request(request, None)

        self.assertTrue(allowed)
        self.assertIn("_ratelimit_limit", request.META)
