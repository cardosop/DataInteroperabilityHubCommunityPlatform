"""
Phase 45 (45.5) — SSRF Single Source of Truth Tests

Verifies that ref_resolver uses ssrf_guard.is_safe_url as the single canonical
SSRF function, DNS failures are treated as unsafe, DNS timeout raises, and
local $ref (#fragment) is considered safe.
"""

from unittest.mock import patch

from django.test import TestCase

from hub.apps.webhooks.ssrf_guard import (
    SSRFViolationError,
    _resolve_and_check,
    is_safe_url,
)


class SSRFSingleSourceTest(TestCase):
    """Tests for SSRF consolidation (Phase 45)."""

    def test_ref_resolver_imports_is_safe_url_from_ssrf_guard(self):
        """ref_resolver.is_safe_url is the exact same object as ssrf_guard.is_safe_url."""
        from hub.apps.contracts.ref_resolver import is_safe_url as ref_is_safe
        from hub.apps.webhooks.ssrf_guard import is_safe_url as guard_is_safe

        assert ref_is_safe is guard_is_safe

    def test_nxdomain_hostname_raises(self):
        """An NXDOMAIN hostname raises SSRFViolationError."""
        with self.assertRaises(SSRFViolationError) as ctx:
            _resolve_and_check("this-domain-definitely-does-not-exist-xyz123.invalid")
        self.assertIn("could not be resolved", str(ctx.exception))

    def test_nxdomain_via_is_safe_url_returns_false(self):
        """is_safe_url returns False for NXDOMAIN hostnames."""
        result = is_safe_url("https://this-domain-definitely-does-not-exist-xyz123.invalid/hook")
        self.assertFalse(result)

    @patch("hub.apps.webhooks.ssrf_guard.socket.getaddrinfo")
    def test_dns_timeout_raises(self, mock_getaddrinfo):
        """DNS resolution timeout raises SSRFViolationError."""
        import time

        def slow_resolve(*args, **kwargs):
            time.sleep(10)  # noqa: sleep-needed  # INTENTIONAL: test-specific delay  # longer than the 5s timeout
            return []

        mock_getaddrinfo.side_effect = slow_resolve

        with self.assertRaises(SSRFViolationError) as ctx:
            _resolve_and_check("slow-dns.example.com")
        self.assertIn("timed out", str(ctx.exception))

    def test_local_ref_fragment_is_safe(self):
        """'#local-ref' (JSON pointer) returns True — no network call needed."""
        self.assertTrue(is_safe_url("#/definitions/Foo"))
        self.assertTrue(is_safe_url("#local-ref"))
        self.assertTrue(is_safe_url("#"))

    def test_empty_url_is_unsafe(self):
        """Empty/None URLs are considered unsafe."""
        self.assertFalse(is_safe_url(""))
        self.assertFalse(is_safe_url(None))

    def test_private_ip_is_unsafe(self):
        """Private IPs return False via is_safe_url."""
        self.assertFalse(is_safe_url("http://127.0.0.1/hook"))
        self.assertFalse(is_safe_url("http://10.0.0.1/hook"))
        self.assertFalse(is_safe_url("http://169.254.169.254/latest/meta-data/"))

    def test_ipv6_scope_id_handled(self):
        """IPv6 with scope ID (fe80::1%eth0) is correctly detected as private."""
        self.assertFalse(is_safe_url("http://[fe80::1%25eth0]/hook"))

    def test_no_ssrf_blocked_networks_in_contracts(self):
        """No _SSRF_BLOCKED_NETWORKS reference exists in contracts/ directory."""
        import subprocess

        result = subprocess.run(
            ["grep", "-r", "_SSRF_BLOCKED_NETWORKS", "hub/apps/contracts/", "--include=*.py"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.stdout.strip(), "", "Found _SSRF_BLOCKED_NETWORKS in contracts/")
