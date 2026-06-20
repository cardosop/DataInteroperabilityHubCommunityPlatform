"""
Tests verifying that hub/apps/contracts/ref_resolver.py raises
ODPSRefResolutionError (with ERROR_CODE_SECURITY_VIOLATION) for
localhost and private-IP $ref URLs instead of just logging a warning.

These tests use Django's TestCase so the ORM is available (RefResolver
touches SecurityAuditLog).  We mock the *outbound* HTTP call and the
socket-level resolution so no real network traffic is needed.
"""

import socket
from unittest.mock import patch

import pytest
from django.test import TestCase

from hub.apps.contracts.odps_errors import ODPSRefResolutionError
from hub.apps.contracts.ref_resolver import RefResolver


def _make_resolver(tenant_id="test-tenant", user_id="test-user"):
    return RefResolver(tenant_id=tenant_id, user_id=user_id)


# ---------------------------------------------------------------------------
# Helper: mock getaddrinfo inside ref_resolver to return a specific IP
# ---------------------------------------------------------------------------


def _mock_dns_in_resolver(ip: str):
    result = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, 0))]
    return patch(
        "hub.apps.webhooks.ssrf_guard.socket.getaddrinfo",
        return_value=result,
    )


def _mock_dns_ipv6_in_resolver(ip: str):
    """Return a context manager that makes getaddrinfo return an IPv6 result."""
    result = [(socket.AF_INET6, socket.SOCK_STREAM, 0, "", (ip, 0, 0, 0))]
    return patch(
        "hub.apps.webhooks.ssrf_guard.socket.getaddrinfo",
        return_value=result,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRefResolverSSRF(TestCase):
    def _validate_url(self, url: str):
        """Call the private _validate_external_url helper with SSRF enabled."""
        # Use a context-manager override instead of class-level so the override
        # is guaranteed to take effect regardless of setUpClass / test-runner
        # lifecycle details.
        from django.test import override_settings as _override_settings

        with _override_settings(WEBHOOK_SSRF_ENABLED=True):
            resolver = _make_resolver()
            resolver._validate_external_url(url)

    # --- localhost -----------------------------------------------------------

    def test_localhost_ref_raises_not_warns(self):
        """$ref to http://localhost/… must raise, never just log a warning."""
        with _mock_dns_in_resolver("127.0.0.1"):
            with self.assertRaises(ODPSRefResolutionError) as ctx:
                self._validate_url("http://localhost/schema.json")
        self.assertEqual(
            ctx.exception.error_code,
            ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
        )

    def test_127_0_0_1_ref_raises(self):
        """Direct loopback IP literal in $ref must raise."""
        with self.assertRaises(ODPSRefResolutionError) as ctx:
            self._validate_url("http://127.0.0.1/schema.json")
        self.assertEqual(
            ctx.exception.error_code,
            ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
        )

    def test_0_0_0_0_ref_raises(self):
        """0.0.0.0 in $ref must raise."""
        with self.assertRaises(ODPSRefResolutionError) as ctx:
            self._validate_url("http://0.0.0.0/schema.json")
        self.assertEqual(
            ctx.exception.error_code,
            ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
        )

    # --- RFC-1918 private IPs ------------------------------------------------

    def test_private_ip_10_x_ref_raises_not_warns(self):
        """$ref to 10.x.x.x must raise with SECURITY_VIOLATION."""
        with self.assertRaises(ODPSRefResolutionError) as ctx:
            self._validate_url("http://10.0.0.1/schema.json")
        self.assertEqual(
            ctx.exception.error_code,
            ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
        )

    def test_private_ip_172_16_ref_raises(self):
        with self.assertRaises(ODPSRefResolutionError) as ctx:
            self._validate_url("http://172.16.0.1/schema.json")
        self.assertEqual(
            ctx.exception.error_code,
            ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
        )

    def test_private_ip_192_168_ref_raises(self):
        with self.assertRaises(ODPSRefResolutionError) as ctx:
            self._validate_url("http://192.168.1.1/schema.json")
        self.assertEqual(
            ctx.exception.error_code,
            ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
        )

    # --- AWS IMDS / link-local -----------------------------------------------

    def test_aws_imds_ref_raises(self):
        with self.assertRaises(ODPSRefResolutionError) as ctx:
            self._validate_url("http://169.254.169.254/latest/meta-data/")
        self.assertEqual(
            ctx.exception.error_code,
            ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
        )

    # --- DNS resolution to private range -------------------------------------

    def test_hostname_resolving_to_private_ip_raises(self):
        """A public-looking hostname that resolves to a private IP must be blocked."""
        with _mock_dns_in_resolver("10.0.0.5"):
            with self.assertRaises(ODPSRefResolutionError) as ctx:
                self._validate_url("https://internal.corp/schema.json")
        self.assertEqual(
            ctx.exception.error_code,
            ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
        )

    # --- Public URLs must still work -----------------------------------------

    def test_public_https_url_passes_validation(self):
        """A genuine public URL must pass _validate_external_url without raising."""
        with _mock_dns_in_resolver("93.184.216.34"):  # example.com public IP
            # Should not raise — if it does, the test fails naturally
            self._validate_url("https://example.com/schema.json")

    def test_public_http_url_passes_validation(self):
        with _mock_dns_in_resolver("1.2.3.4"):
            self._validate_url("http://schema.example.org/odps.json")

    # --- IPv6-mapped IPv4 bypass (::ffff:x.x.x.x) ---------------------------

    def test_ipv6_mapped_rfc1918_10x_raises(self):
        """::ffff:10.0.0.1 is an IPv4-mapped address for a private range."""
        with _mock_dns_ipv6_in_resolver("::ffff:10.0.0.1"):
            with self.assertRaises(ODPSRefResolutionError) as ctx:
                self._validate_url("https://example.com/schema.json")
        self.assertEqual(
            ctx.exception.error_code,
            ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
        )

    def test_ipv6_mapped_rfc1918_192168_raises(self):
        """::ffff:192.168.1.1 is an IPv4-mapped address for a private range."""
        with _mock_dns_ipv6_in_resolver("::ffff:192.168.1.1"):
            with self.assertRaises(ODPSRefResolutionError) as ctx:
                self._validate_url("https://example.com/schema.json")
        self.assertEqual(
            ctx.exception.error_code,
            ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
        )

    def test_ipv6_mapped_imds_raises(self):
        """::ffff:169.254.169.254 maps to the AWS IMDS address."""
        with _mock_dns_ipv6_in_resolver("::ffff:169.254.169.254"):
            with self.assertRaises(ODPSRefResolutionError) as ctx:
                self._validate_url("https://example.com/schema.json")
        self.assertEqual(
            ctx.exception.error_code,
            ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
        )

    def test_ipv6_mapped_public_ip_passes(self):
        """::ffff:93.184.216.34 maps to a public IP and must not be blocked."""
        with _mock_dns_ipv6_in_resolver("::ffff:93.184.216.34"):
            self._validate_url("https://example.com/schema.json")

    # ── SSRF toggle (disabled) ────────────────────────────────────────

    def test_private_url_passes_when_ssrf_disabled(self):
        """When WEBHOOK_SSRF_ENABLED=False, private IPs must NOT be blocked."""
        from django.test import override_settings as _override_settings

        with _override_settings(WEBHOOK_SSRF_ENABLED=False):
            resolver = _make_resolver()
            # Must not raise — the SSRF guard is disabled.
            resolver._validate_external_url("http://127.0.0.1/schema.json")
            resolver._validate_external_url("http://10.0.0.1/schema.json")
            resolver._validate_external_url("http://169.254.169.254/latest/meta-data/")
