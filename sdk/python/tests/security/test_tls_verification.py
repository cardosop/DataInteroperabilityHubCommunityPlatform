import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.2.17 — Security: TLS verification (SDK only).

Verifies that the SDK refuses connections to hosts with self-signed
or invalid TLS certificates by default.

This test is in the CLI tree for organizational convenience but the
core assertion is SDK-specific. In the CLI tree it validates that
requests.get with verify=True (default) rejects bad certs.
"""

import requests


def test_self_signed_cert_rejected_by_default():
    """requests library (used by both CLI and SDK) must reject self-signed certs."""
    # self-signed.badssl.com has a valid self-signed cert that should be
    # rejected by default (verify=True).
    with pytest.raises(requests.exceptions.SSLError):
        requests.get("https://self-signed.badssl.com/", timeout=10)


def test_expired_cert_rejected():
    """Expired TLS certificate must be rejected."""
    with pytest.raises(requests.exceptions.SSLError):
        requests.get("https://expired.badssl.com/", timeout=10)


def test_wrong_host_cert_rejected():
    """Certificate for wrong hostname must be rejected."""
    with pytest.raises(requests.exceptions.SSLError):
        requests.get("https://wrong.host.badssl.com/", timeout=10)
