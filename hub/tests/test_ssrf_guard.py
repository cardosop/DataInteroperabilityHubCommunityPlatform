"""
Tests for hub/apps/webhooks/ssrf_guard.py

All tests exercise the real guard with actual DNS resolution mocked at the
socket layer so the suite runs offline and deterministically.
"""

import socket
from unittest.mock import patch

import pytest
from rest_framework import serializers as drf_serializers

from hub.apps.webhooks.ssrf_guard import (
    SSRFViolationError,
    validate_webhook_url,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_dns(ip: str):
    """Return a context manager that makes getaddrinfo always resolve to *ip*."""
    fake_result = [(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, 0))]
    return patch("hub.apps.webhooks.ssrf_guard.socket.getaddrinfo", return_value=fake_result)


def _mock_dns_ipv6(ip: str):
    fake_result = [(socket.AF_INET6, socket.SOCK_STREAM, 0, "", (ip, 0, 0, 0))]
    return patch("hub.apps.webhooks.ssrf_guard.socket.getaddrinfo", return_value=fake_result)


# ---------------------------------------------------------------------------
# Scheme validation
# ---------------------------------------------------------------------------


class TestNonHttpSchemeBlocked:
    def test_file_scheme_raises_validation_error(self):
        with pytest.raises(drf_serializers.ValidationError, match="scheme"):
            validate_webhook_url("file:///etc/passwd", raise_as_validation_error=True)

    def test_ftp_scheme_raises_validation_error(self):
        with pytest.raises(drf_serializers.ValidationError, match="scheme"):
            validate_webhook_url("ftp://example.com/data", raise_as_validation_error=True)

    def test_file_scheme_raises_ssrf_error(self):
        with pytest.raises(SSRFViolationError, match="scheme"):
            validate_webhook_url("file:///etc/passwd", raise_as_validation_error=False)

    def test_ftp_scheme_raises_ssrf_error(self):
        with pytest.raises(SSRFViolationError, match="scheme"):
            validate_webhook_url("ftp://example.com/data", raise_as_validation_error=False)


# ---------------------------------------------------------------------------
# Loopback
# ---------------------------------------------------------------------------


class TestLoopbackBlocked:
    def test_loopback_127_0_0_1(self):
        with pytest.raises(SSRFViolationError):
            validate_webhook_url("http://127.0.0.1/hook", raise_as_validation_error=False)

    def test_loopback_127_0_0_1_validation_error(self):
        with pytest.raises(drf_serializers.ValidationError):
            validate_webhook_url("http://127.0.0.1/hook", raise_as_validation_error=True)

    def test_loopback_127_1_2_3(self):
        with pytest.raises(SSRFViolationError):
            validate_webhook_url("http://127.1.2.3/hook", raise_as_validation_error=False)

    def test_localhost_hostname(self):
        """'localhost' resolves to 127.0.0.1 — must be blocked via DNS check."""
        with _mock_dns("127.0.0.1"), pytest.raises(SSRFViolationError):
            validate_webhook_url("http://localhost/hook", raise_as_validation_error=False)


class TestIPv6LoopbackBlocked:
    def test_ipv6_loopback_literal(self):
        with pytest.raises(SSRFViolationError):
            validate_webhook_url("http://[::1]/hook", raise_as_validation_error=False)

    def test_ipv6_loopback_via_dns(self):
        with _mock_dns_ipv6("::1"), pytest.raises(SSRFViolationError):
            validate_webhook_url("http://example.com/hook", raise_as_validation_error=False)


# ---------------------------------------------------------------------------
# IPv6-mapped IPv4 addresses  (::ffff:x.x.x.x)
#
# These look like IPv6 addresses at the socket level but map to IPv4 ranges
# that must be blocked.  A naive guard that only checks IPv4 dotted notation
# would miss them.
# ---------------------------------------------------------------------------


class TestIPv6MappedIPv4Blocked:
    """
    ::ffff:x.x.x.x is the IPv4-mapped IPv6 format returned by getaddrinfo on
    dual-stack hosts.  ssrf_guard.py uses ipaddress.ip_address() which handles
    these correctly; these tests confirm the mapping is not bypassed.
    """

    def test_ipv6_mapped_loopback_blocked(self):
        """::ffff:127.0.0.1 maps to 127.0.0.1 (loopback) and must be blocked."""
        with _mock_dns_ipv6("::ffff:127.0.0.1"), pytest.raises(SSRFViolationError):
            validate_webhook_url(
                "http://example.com/hook",
                raise_as_validation_error=False,
            )

    def test_ipv6_mapped_rfc1918_10x_blocked(self):
        """::ffff:10.0.0.1 maps to a private RFC-1918 address and must be blocked."""
        with _mock_dns_ipv6("::ffff:10.0.0.1"), pytest.raises(SSRFViolationError):
            validate_webhook_url(
                "http://example.com/hook",
                raise_as_validation_error=False,
            )

    def test_ipv6_mapped_rfc1918_192168_blocked(self):
        """::ffff:192.168.1.1 maps to a private RFC-1918 address and must be blocked."""
        with _mock_dns_ipv6("::ffff:192.168.1.1"), pytest.raises(SSRFViolationError):
            validate_webhook_url(
                "http://example.com/hook",
                raise_as_validation_error=False,
            )

    def test_ipv6_mapped_imds_blocked(self):
        """::ffff:169.254.169.254 maps to the AWS IMDS address and must be blocked."""
        with _mock_dns_ipv6("::ffff:169.254.169.254"), pytest.raises(SSRFViolationError):
            validate_webhook_url(
                "http://example.com/hook",
                raise_as_validation_error=False,
            )

    def test_ipv6_mapped_public_ip_allowed(self):
        """::ffff:93.184.216.34 maps to a public IP and must NOT be blocked."""
        with _mock_dns_ipv6("::ffff:93.184.216.34"):
            # Must not raise — public mapped address is legitimate
            validate_webhook_url(
                "http://example.com/hook",
                raise_as_validation_error=False,
            )


# ---------------------------------------------------------------------------
# RFC-1918
# ---------------------------------------------------------------------------


class TestRFC1918Blocked:
    def test_10_x_blocked(self):
        with pytest.raises(SSRFViolationError):
            validate_webhook_url("http://10.0.0.1/hook", raise_as_validation_error=False)

    def test_172_16_x_blocked(self):
        with pytest.raises(SSRFViolationError):
            validate_webhook_url("http://172.16.0.1/hook", raise_as_validation_error=False)

    def test_172_31_x_blocked(self):
        with pytest.raises(SSRFViolationError):
            validate_webhook_url("http://172.31.255.1/hook", raise_as_validation_error=False)

    def test_192_168_x_blocked(self):
        with pytest.raises(SSRFViolationError):
            validate_webhook_url("http://192.168.1.100/hook", raise_as_validation_error=False)

    def test_rfc1918_via_dns(self):
        with _mock_dns("10.0.0.5"), pytest.raises(SSRFViolationError):
            validate_webhook_url("http://internal.corp/hook", raise_as_validation_error=False)


# ---------------------------------------------------------------------------
# AWS IMDS / Link-local
# ---------------------------------------------------------------------------


class TestAWSIMDSBlocked:
    def test_aws_imds_direct_ip(self):
        with pytest.raises(SSRFViolationError):
            validate_webhook_url(
                "http://169.254.169.254/latest/meta-data/", raise_as_validation_error=False
            )

    def test_link_local_via_dns(self):
        with _mock_dns("169.254.1.1"), pytest.raises(SSRFViolationError):
            validate_webhook_url(
                "http://metadata.example.com/hook", raise_as_validation_error=False
            )


# ---------------------------------------------------------------------------
# DNS rebinding
# ---------------------------------------------------------------------------


class TestDNSRebindingBlocked:
    """
    At delivery time, validate_webhook_url is called again with
    raise_as_validation_error=False.  If DNS has rebounded to a private IP the
    delivery must be blocked.
    """

    def test_dns_rebinding_blocked_at_delivery(self):
        """Hostname was valid at registration but now resolves to 127.0.0.1."""
        with _mock_dns("127.0.0.1"), pytest.raises(SSRFViolationError):
            validate_webhook_url(
                "http://rebind.example.com/hook",
                raise_as_validation_error=False,
            )

    def test_dns_rebinding_to_rfc1918(self):
        with _mock_dns("192.168.0.1"), pytest.raises(SSRFViolationError):
            validate_webhook_url(
                "http://rebind.example.com/hook",
                raise_as_validation_error=False,
            )


# ---------------------------------------------------------------------------
# Public URLs allowed
# ---------------------------------------------------------------------------


class TestPublicUrlAllowed:
    def test_public_https_url(self):
        with _mock_dns("93.184.216.34"):  # example.com public IP
            # Should not raise
            validate_webhook_url("https://example.com/webhook", raise_as_validation_error=False)

    def test_public_http_url(self):
        with _mock_dns("1.2.3.4"):
            validate_webhook_url("http://hook.example.org/deliver", raise_as_validation_error=False)

    def test_public_url_with_port(self):
        with _mock_dns("8.8.8.8"):
            validate_webhook_url(
                "https://api.example.com:8443/hook", raise_as_validation_error=False
            )
