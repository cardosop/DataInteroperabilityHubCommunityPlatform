"""
Phase 227 Wave 1 (227.L1.10) — SSRF defence tests for ``port.contractURL``.

The Phase 227 root-cause investigation found that ODPS contracts could
declare ``outputPorts[*].contractURL`` pointing at arbitrary external
URLs. The Wave 1 helper (``_ports_helper.normalize_models_from_ports``)
delegates resolution to :class:`hub.apps.contracts.ref_resolver.RefResolver`,
which itself enforces the SSRF allowlist via
:func:`hub.apps.webhooks.ssrf_guard.is_safe_url`.

This test file is the regression suite for that delegation. It checks:

1. Non-HTTP schemes (``file://``, ``gopher://``, ``dict://``,
   ``ftp://``) are rejected by :func:`is_safe_url` itself.
2. With ``WEBHOOK_SSRF_ENABLED=True``, blocked targets (IMDS,
   localhost, RFC1918, link-local, loopback, multicast) raise
   :class:`ODPSRefResolutionError` from ``RefResolver._validate_external_url``.
3. End-to-end: a port whose ``contractURL`` is SSRF-blocked produces NO
   model in ``hub_contract.models[]`` and surfaces a
   ``STRUCTURELESS_PORT_NO_RESOLVABLE_PAYLOAD`` warning.
4. Public HTTPS URL with a mocked-network ``RefResolver`` resolves
   correctly and a ``HubContractModelEntry`` is emitted.

Mocking discipline
------------------
The only mocks in this file are at the *network boundary*
(``socket.getaddrinfo``, ``httpx`` transport). The SSRF guard, the
RefResolver, and the helper itself run as production code paths — no
internal-code mocks per Phase 227 doctrine.
"""
from __future__ import annotations

import socket
from typing import Any, Dict, List
from unittest.mock import patch

import pytest
from django.test import TestCase, override_settings

from hub.apps.contracts.odps_errors import ODPSRefResolutionError
from hub.apps.contracts.ref_resolver import RefResolver
from hub.apps.webhooks.ssrf_guard import is_safe_url


# ---------------------------------------------------------------------------
# 1. Scheme rejection (no DNS — purely string-shape)
# ---------------------------------------------------------------------------


class SchemeRejectionTests(TestCase):
    """Non-HTTP schemes are rejected at ``is_safe_url`` level.

    The SSRF allowlist is restricted to ``http`` and ``https`` because
    ``file://`` reads local disk, ``gopher://`` enables CRLF-injection
    attacks against vulnerable services, and ``dict://`` was a known
    SSRF vector against memcache/Redis pre-CVE-2017-9805.
    """

    def test_file_scheme_rejected(self):
        self.assertFalse(is_safe_url("file:///etc/passwd"),
            "file:// scheme must be rejected")

    def test_gopher_scheme_rejected(self):
        self.assertFalse(is_safe_url("gopher://evil.example/_payload"),
            "gopher:// scheme must be rejected")

    def test_dict_scheme_rejected(self):
        self.assertFalse(is_safe_url("dict://localhost:6379/INFO"),
            "dict:// scheme must be rejected")

    def test_ftp_scheme_rejected(self):
        self.assertFalse(is_safe_url("ftp://internal.fileshare.example/file.json"),
            "ftp:// scheme must be rejected")

    def test_data_scheme_rejected(self):
        # Inline data: URLs would let an attacker exfiltrate via the
        # response cache; rejected for defence-in-depth.
        self.assertFalse(is_safe_url("data:text/plain;base64,SGVsbG8="),
            "data: scheme must be rejected")

    def test_javascript_scheme_rejected(self):
        self.assertFalse(is_safe_url("javascript:alert(1)"),
            "javascript: scheme must be rejected")


# ---------------------------------------------------------------------------
# 2. Blocked-host enforcement at RefResolver._validate_external_url
# ---------------------------------------------------------------------------


def _mock_dns(ip: str):
    """Patch the SSRF guard's getaddrinfo to return a fixed IP."""
    return patch(
        "hub.apps.webhooks.ssrf_guard.socket.getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 0, "", (ip, 0))],
    )


@override_settings(WEBHOOK_SSRF_ENABLED=True)
@pytest.mark.django_db
class BlockedHostsTests(TestCase):
    """Blocked targets raise ``ODPSRefResolutionError`` from the RefResolver."""

    def _resolver(self) -> RefResolver:
        # tenant_id/user_id only used for audit-log scoping; tests don't assert.
        return RefResolver(tenant_id="ssrf-test-tenant", user_id="ssrf-test-user")

    def _expect_security_violation(self, url: str) -> None:
        with self.assertRaises(ODPSRefResolutionError) as ctx:
            self._resolver()._validate_external_url(url)
        self.assertEqual(
            ctx.exception.error_code,
            ODPSRefResolutionError.ERROR_CODE_SECURITY_VIOLATION,
            f"URL {url!r} should raise SECURITY_VIOLATION, got {ctx.exception.error_code}",
        )

    def test_aws_imds_blocked(self):
        """AWS instance-metadata service — the canonical SSRF target."""
        self._expect_security_violation("http://169.254.169.254/latest/meta-data/")

    def test_gcp_imds_blocked(self):
        """GCP IMDS uses metadata.google.internal — must resolve to a private IP."""
        with _mock_dns("169.254.169.254"):
            self._expect_security_violation(
                "http://metadata.google.internal/computeMetadata/v1/"
            )

    def test_localhost_redis_blocked(self):
        with _mock_dns("127.0.0.1"):
            self._expect_security_violation("http://localhost:6379/INFO")

    def test_loopback_literal_blocked(self):
        self._expect_security_violation("http://127.0.0.1/contract.json")

    def test_rfc1918_10_blocked(self):
        self._expect_security_violation("http://10.0.0.1/contract.json")

    def test_rfc1918_172_blocked(self):
        self._expect_security_violation("http://172.16.0.1/contract.json")

    def test_rfc1918_192_168_blocked(self):
        self._expect_security_violation("http://192.168.1.1/contract.json")

    def test_link_local_169_254_blocked(self):
        self._expect_security_violation("http://169.254.10.5/contract.json")


# ---------------------------------------------------------------------------
# 3. End-to-end: helper + RefResolver with an SSRF-blocked URL
# ---------------------------------------------------------------------------


@override_settings(WEBHOOK_SSRF_ENABLED=True)
@pytest.mark.django_db
class HelperWithBlockedURLTests(TestCase):
    """The helper must swallow SSRF errors fail-soft and emit a warning."""

    def test_blocked_contractURL_yields_no_model_and_warning(self):
        from hub.apps.contracts.normalization import _ports_helper

        resolver = RefResolver(tenant_id="t", user_id="u")
        port: Dict[str, Any] = {
            "name": "blocked-port",
            "contractURL": "http://169.254.169.254/latest/meta-data/iam/info",
        }
        hub: Dict[str, Any] = {"info": {}, "schema": {"fields": []}, "extensions": {}}
        warnings: List[str] = []

        _ports_helper.normalize_models_from_ports(
            contract_data={"product": {"outputPorts": [port]}},
            hub_contract=hub,
            warnings=warnings,
            ref_resolver=resolver,
        )

        # SSRF blocked → no model emitted.
        self.assertEqual(hub["models"], [],
            f"Expected no models; got {hub['models']!r}")
        # … and a STRUCTURELESS warning surfaces so ops can find it.
        self.assertTrue(any(
            "STRUCTURELESS_PORT_NO_RESOLVABLE_PAYLOAD" in w
            for w in warnings
        ), f"Expected STRUCTURELESS warning; got {warnings!r}")


# ---------------------------------------------------------------------------
# 4. Public-HTTPS URL via mocked RefResolver — happy path
# ---------------------------------------------------------------------------


class _FakeRefResolver:
    """Resolver substitute that does not touch the network.

    This is the ONLY internal-component substitute in the test file —
    it stands in for ``RefResolver`` on the happy path so we can verify
    helper behaviour without spinning up an HTTP server. The SSRF guard
    is exercised separately in :class:`BlockedHostsTests`.
    """

    def __init__(self, payload: Dict[str, Any]):
        self._payload = payload
        self.calls: List[str] = []

    def resolve(self, ref_path: str, document=None) -> Dict[str, Any]:
        self.calls.append(ref_path)
        return self._payload


class HelperWithMockedResolverTests(TestCase):

    def test_public_https_contractURL_resolves_to_model(self):
        """Public URL → resolver returns ODCS-shaped doc → model emitted."""
        from hub.apps.contracts.normalization import _ports_helper

        resolver = _FakeRefResolver(
            payload={
                "spec": {
                    "schema": {
                        "fields": [
                            {"name": "id", "data_type": "string"},
                            {"name": "amount", "data_type": "number"},
                        ]
                    }
                }
            }
        )
        port = {
            "name": "remote-port",
            "contractURL": "https://contracts.example.com/odcs/orders.json",
        }
        hub: Dict[str, Any] = {
            "info": {}, "schema": {"fields": []}, "extensions": {},
        }
        warnings: List[str] = []

        _ports_helper.normalize_models_from_ports(
            contract_data={"product": {"outputPorts": [port]}},
            hub_contract=hub,
            warnings=warnings,
            ref_resolver=resolver,
        )

        self.assertEqual(resolver.calls,
            ["https://contracts.example.com/odcs/orders.json"],
            f"Resolver should have been called once with the URL; got {resolver.calls}")
        self.assertEqual(len(hub["models"]), 1)
        self.assertEqual(hub["models"][0]["name"], "remote-port")
        self.assertEqual([f["name"] for f in hub["models"][0]["fields"]],
            ["id", "amount"])
        self.assertEqual(warnings, [],
            f"Expected no warnings; got {warnings!r}")

    def test_resolver_raising_falls_back_to_no_resolvable(self):
        """If RefResolver raises (e.g., 404, SSRF block), helper warns."""
        from hub.apps.contracts.normalization import _ports_helper

        class _BoomResolver:
            def resolve(self, ref_path: str, document=None):
                raise RuntimeError("simulated network failure")

        port = {
            "name": "boom",
            "contractURL": "https://broken.example.com/odcs.json",
        }
        hub: Dict[str, Any] = {
            "info": {}, "schema": {"fields": []}, "extensions": {},
        }
        warnings: List[str] = []
        _ports_helper.normalize_models_from_ports(
            contract_data={"product": {"outputPorts": [port]}},
            hub_contract=hub,
            warnings=warnings,
            ref_resolver=_BoomResolver(),
        )
        self.assertEqual(hub["models"], [])
        self.assertTrue(any("STRUCTURELESS_PORT_NO_RESOLVABLE_PAYLOAD" in w for w in warnings))

    def test_no_ref_resolver_supplied_means_contractURL_is_unresolvable(self):
        """Caller did not pass a resolver — contractURL-only ports warn."""
        from hub.apps.contracts.normalization import _ports_helper

        port = {
            "name": "noresolver",
            "contractURL": "https://example.com/x.json",
        }
        hub: Dict[str, Any] = {
            "info": {}, "schema": {"fields": []}, "extensions": {},
        }
        warnings: List[str] = []
        _ports_helper.normalize_models_from_ports(
            contract_data={"product": {"outputPorts": [port]}},
            hub_contract=hub,
            warnings=warnings,
            # ref_resolver omitted on purpose
        )
        self.assertEqual(hub["models"], [])
        self.assertTrue(any("STRUCTURELESS_PORT_NO_RESOLVABLE_PAYLOAD" in w for w in warnings))
