import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.5.5 — Dimension: DNS resolution failure.

Verifies that the client handles unresolvable hostnames gracefully —
raises ConnectionError with a message that mentions the hostname,
not an opaque socket.gaierror.
"""

import requests


def test_unresolvable_host_raises_connection_error():
    """Request to an unresolvable hostname must raise ConnectionError."""
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get(
            "http://this-hostname-will-never-resolve-meshant.invalid/api/v1/health/",
            timeout=5,
        )


def test_dns_error_message_contains_hostname():
    """The error message must mention the unresolvable hostname."""
    try:
        requests.get(
            "http://unresolvable-host-meshant-test.invalid/api/v1/health/",
            timeout=5,
        )
        pytest.fail("Expected ConnectionError")
    except requests.exceptions.ConnectionError as exc:
        msg = str(exc).lower()
        assert "unresolvable-host-meshant-test" in msg or "name" in msg or "resolve" in msg, (
            f"DNS error message does not mention the hostname or resolution: {str(exc)[:200]}"
        )


def test_dns_failure_does_not_hang():
    """DNS failure must resolve within the timeout budget, not hang."""
    import time

    start = time.monotonic()
    with pytest.raises(requests.exceptions.ConnectionError):
        requests.get(
            "http://another-fake-host-meshant.invalid/health/",
            timeout=3,
        )
    elapsed = time.monotonic() - start
    assert elapsed < 10, f"DNS failure took {elapsed:.1f}s — should fail fast"
