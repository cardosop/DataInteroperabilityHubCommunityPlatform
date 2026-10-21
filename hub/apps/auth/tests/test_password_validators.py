"""
Phase 277.B.065 — Password validator unit tests.

Covers: PasswordComplexityValidator, CommonPasswordDenyListValidator,
and HaveIBeenPwnedValidator.
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings

from hub.apps.auth.password_validators import (
    CommonPasswordDenyListValidator,
    HaveIBeenPwnedValidator,
    PasswordComplexityValidator,
)

User = get_user_model()


class PasswordComplexityValidatorTests(TestCase):
    def setUp(self):
        self.validator = PasswordComplexityValidator(min_length=10)

    def test_accepts_strong_password(self):
        result = self.validator.validate("Str0ng!Pass")
        self.assertIsNone(result, f"Expected None, got {result!r}")

    def test_accepts_password_with_multiple_specials(self):
        result = self.validator.validate("C0mpl3x!!@#Pass")
        self.assertIsNone(result, f"Expected None, got {result!r}")

    def test_rejects_short_password(self):
        with self.assertRaises(ValidationError) as ctx:
            self.validator.validate("Abc1!")
        self.assertIn("short", str(ctx.exception).lower())

    def test_rejects_missing_uppercase(self):
        with self.assertRaises(ValidationError) as ctx:
            self.validator.validate("alllowercase1!")
        self.assertIn("uppercase", str(ctx.exception).lower())

    def test_rejects_missing_lowercase(self):
        with self.assertRaises(ValidationError) as ctx:
            self.validator.validate("ALLUPPERCASE1!")
        self.assertIn("lowercase", str(ctx.exception).lower())

    def test_rejects_missing_digit(self):
        with self.assertRaises(ValidationError) as ctx:
            self.validator.validate("NoDigitsHere!")
        self.assertIn("digit", str(ctx.exception).lower())

    def test_rejects_missing_special(self):
        with self.assertRaises(ValidationError) as ctx:
            self.validator.validate("NoSpecial1")
        self.assertIn("special character", str(ctx.exception).lower())

    def test_multiple_errors_reported(self):
        """All failing rules should be reported in a single ValidationError."""
        with self.assertRaises(ValidationError) as ctx:
            self.validator.validate("a")
        # Should have multiple error messages (short + missing upper + missing digit + missing special)
        self.assertGreaterEqual(len(ctx.exception.messages), 2)

    def test_help_text_includes_min_length(self):
        text = self.validator.get_help_text()
        self.assertIn("10", text)

    def test_custom_min_length(self):
        v = PasswordComplexityValidator(min_length=12)
        with self.assertRaises(ValidationError):
            v.validate("Abcdef1!")  # 8 chars — should fail with min_length=12
        # 12 chars (meets the custom min_length), has upper, lower, digit, special
        v.validate("Abcdefgh1!23")


class CommonPasswordDenyListValidatorTests(TestCase):
    def setUp(self):
        self.validator = CommonPasswordDenyListValidator()

    def test_rejects_common_password(self):
        with self.assertRaises(ValidationError) as ctx:
            self.validator.validate("password")
        self.assertIn("common", str(ctx.exception).lower())

    def test_rejects_common_password_case_insensitive(self):
        with self.assertRaises(ValidationError):
            self.validator.validate("PassWord")

    def test_rejects_common_password_123456(self):
        with self.assertRaises(ValidationError):
            self.validator.validate("123456")

    def test_accepts_uncommon_password(self):
        # A random strong password should not be in any common list
        result = self.validator.validate("XyZ!9kLm2#QwR5p")
        self.assertIsNone(result, f"Expected None, got {result!r}")

    def test_help_text_present(self):
        text = self.validator.get_help_text()
        self.assertTrue(len(text) > 0)


class HaveIBeenPwnedValidatorTests(TestCase):
    def setUp(self):
        self.validator = HaveIBeenPwnedValidator(timeout=2.0)

    def _mock_urlopen(self, body=""):
        """Return a mock that simulates a urllib response."""
        import io

        resp = io.BytesIO(body.encode("utf-8"))
        resp.url = "https://api.pwnedpasswords.com/range/XXXXX"
        resp.status = 200
        resp.reason = "OK"
        resp.getcode = lambda: 200
        resp.read = resp.read  # already a method
        return resp

    @override_settings(HIBP_VALIDATOR_ENABLED=True)
    @patch("urllib.request.urlopen")
    def test_rejects_pwned_password(self, mock_urlopen):
        """Password 'password123' is in the HIBP corpus."""
        mock_urlopen.return_value = self._mock_urlopen(
            "CBFDAC6008F9CAB4083784CBD1874F76618D2A97:3730471\r\n"
            "E6B6CBD782F380A973FA9C0E7A99D57D1B2EBB0F:123456\r\n"
        )
        # SHA1('password123') = CBFDAC6008F9CAB4083784CBD1874F76618D2A97
        # The prefix CBFDA would be in the URL; suffix is C6008F9CAB4083784CBD1874F76618D2A97
        # Wait — we need to compute the real SHA1 to construct the proper mock
        # Let's just test the reject path with a known match
        import hashlib

        sha1 = hashlib.sha1(b"password123").hexdigest().upper()
        _prefix, suffix = sha1[:5], sha1[5:]
        # Construct response that includes our suffix
        mock_urlopen.return_value = self._mock_urlopen(
            f"00112233445566778899AABBCCDDEEFF00112233:1\r\n"
            f"{suffix}:3730471\r\n"
            f"FFEEDDCCBBAA99887766554433221100FFEEDDCC:99\r\n"
        )
        with self.assertRaises(ValidationError) as ctx:
            self.validator.validate("password123")
        self.assertIn("breach", str(ctx.exception).lower())

    @override_settings(HIBP_VALIDATOR_ENABLED=True)
    @patch("urllib.request.urlopen")
    def test_accepts_non_pwned_password(self, mock_urlopen):
        """A password not in the HIBP corpus should pass."""
        mock_urlopen.return_value = self._mock_urlopen(
            "00112233445566778899AABBCCDDEEFF00112233:1\r\n"
            "FFEEDDCCBBAA99887766554433221100FFEEDDCC:99\r\n"
        )
        # This password's SHA1 prefix will NOT match the mock's response
        # so it should pass
        result = self.validator.validate("Un1qu3!P@ssphr4s3-that-is-not-pwned")
        self.assertIsNone(result, f"Expected None, got {result!r}")

    @patch("urllib.request.urlopen")
    def test_network_failure_does_not_block(self, mock_urlopen):
        """A network error is best-effort — password should still pass."""
        import urllib.error

        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        result = self.validator.validate("DoesNotMatter123!")
        self.assertIsNone(result, f"Expected None on network failure, got {result!r}")

    @patch("urllib.request.urlopen")
    def test_timeout_does_not_block(self, mock_urlopen):
        """A timeout should not block password acceptance."""

        mock_urlopen.side_effect = TimeoutError("timed out")
        result = self.validator.validate("DoesNotMatter123!")
        self.assertIsNone(result, f"Expected None on timeout, got {result!r}")

    def test_help_text_present(self):
        text = self.validator.get_help_text()
        self.assertTrue(len(text) > 0)
