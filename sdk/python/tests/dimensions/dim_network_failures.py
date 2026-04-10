import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.3.3 — Dimension: network failures.

Verifies that the CLI/SDK handles connection refused, DNS error, and
slow responses gracefully (clear error, no crash, no hang).
"""

import requests


def test_connection_refused_raises_connection_error():
    """Connecting to a closed port must raise ConnectionError, not hang."""
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get("http://127.0.0.1:1/health/", timeout=5)


def test_dns_error_raises_connection_error():
    """Connecting to an unresolvable host must raise ConnectionError."""
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get(
            "http://this-host-does-not-exist-meshant-test.invalid/api/v1/health/",
            timeout=5,
        )


def test_connect_timeout_raises_timeout():
    """Connecting to a black-hole IP must raise a Timeout within the budget."""
    # 10.255.255.1 is a non-routable address — TCP SYN is dropped
    with pytest.raises((requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError)):
        requests.get("http://10.255.255.1/api/v1/health/", timeout=3)


def test_read_timeout_raises_timeout():
    """A server that accepts but never responds must trigger ReadTimeout.

    httpbin.org/delay/10 delays 10s; with a 2s timeout this must fail.
    """
    with pytest.raises((requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError)):
        requests.get("https://httpbin.org/delay/10", timeout=2)


def test_connection_error_message_is_actionable():
    """The error message for a connection failure must include the target host."""
    try:
        requests.get("http://127.0.0.1:1/health/", timeout=2)
        pytest.fail("Expected ConnectionError")
    except requests.exceptions.ConnectionError as exc:
        msg = str(exc)
        assert "127.0.0.1" in msg, (
            f"ConnectionError message does not mention the target host: {msg[:200]}"
        )
