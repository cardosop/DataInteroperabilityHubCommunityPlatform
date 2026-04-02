"""Phase 87: Password reset rate limiting tests."""
from django.test import TestCase
from django.core.cache import cache
from hub.apps.auth.views import _check_password_reset_rate_limit


class TestPasswordResetRateLimit(TestCase):
    def setUp(self):
        cache.clear()

    def tearDown(self):
        cache.clear()

    def test_first_five_requests_allowed(self):
        for i in range(5):
            self.assertTrue(
                _check_password_reset_rate_limit("user@example.com"),
                f"Request {i+1} should be allowed",
            )

    def test_sixth_request_blocked(self):
        for _ in range(5):
            _check_password_reset_rate_limit("user@example.com")
        self.assertFalse(
            _check_password_reset_rate_limit("user@example.com"),
        )

    def test_different_emails_independent(self):
        for _ in range(5):
            _check_password_reset_rate_limit("a@example.com")
        # Different email should still be allowed
        self.assertTrue(
            _check_password_reset_rate_limit("b@example.com"),
        )

    def test_cache_key_format(self):
        _check_password_reset_rate_limit("test@example.com")
        self.assertEqual(
            cache.get("password_reset_email:test@example.com"), 1,
        )
