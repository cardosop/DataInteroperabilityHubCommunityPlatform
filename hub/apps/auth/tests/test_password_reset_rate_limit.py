"""Phase 87: Password reset rate limiting tests."""
from django.test import TestCase, override_settings
from django.core.cache import cache
from hub.apps.auth.views import _check_password_reset_rate_limit


class TestPasswordResetRateLimit(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(RATE_LIMIT_ENABLED=True)
    def test_first_five_requests_allowed(self):
        for i in range(5):
            self.assertTrue(
                _check_password_reset_rate_limit("user@example.com"),
                f"Request {i+1} should be allowed",
            )

    @override_settings(RATE_LIMIT_ENABLED=True)
    def test_sixth_request_blocked(self):
        for _ in range(5):
            _check_password_reset_rate_limit("user@example.com")
        self.assertFalse(
            _check_password_reset_rate_limit("user@example.com"),
        )

    @override_settings(RATE_LIMIT_ENABLED=True)
    def test_different_emails_independent(self):
        for _ in range(5):
            _check_password_reset_rate_limit("a@example.com")
        # Different email should still be allowed
        self.assertTrue(
            _check_password_reset_rate_limit("b@example.com"),
        )

    @override_settings(RATE_LIMIT_ENABLED=True)
    def test_cache_key_format(self):
        _check_password_reset_rate_limit("test@example.com")
        # The sliding-window rate limiter stores a list of timestamps,
        # not a counter.  Verify the cache key is populated with at
        # least one entry.
        timestamps = cache.get("password_reset_email:test@example.com")
        self.assertIsNotNone(timestamps)
        self.assertIsInstance(timestamps, list)
        self.assertGreaterEqual(len(timestamps), 1)

    def tearDown(self):
        cache.clear()
