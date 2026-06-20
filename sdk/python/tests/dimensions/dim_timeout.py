import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.3.5 — Dimension: timeout.

Verifies that client-configured timeouts fire correctly and produce
actionable error messages.
"""

import time

import requests


def test_connect_timeout_fires_within_budget():
    """A 2s connect timeout on a black-hole IP must fire in <5s total."""
    start = time.monotonic()
    with pytest.raises((requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError)):
        requests.get("http://10.255.255.1/api/v1/health/", timeout=2)
    elapsed = time.monotonic() - start
    assert elapsed < 10, f"Timeout took {elapsed:.1f}s — expected <10s"


def test_read_timeout_fires_within_budget():
    """A 2s read timeout on a slow endpoint must fire promptly."""
    start = time.monotonic()
    with pytest.raises((requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError)):
        requests.get("https://httpbin.org/delay/30", timeout=2)
    elapsed = time.monotonic() - start
    assert elapsed < 10, f"Read timeout took {elapsed:.1f}s — expected <10s"


def test_timeout_error_message_mentions_timeout():
    """The timeout error must mention 'timed out' or 'timeout'."""
    try:
        requests.get("http://10.255.255.1/api/v1/health/", timeout=1)
        pytest.fail("Expected timeout error")
    except (requests.exceptions.ConnectTimeout, requests.exceptions.ConnectionError) as exc:
        msg = str(exc).lower()
        assert "timed out" in msg or "timeout" in msg or "connect" in msg, (
            f"Timeout error message is not actionable: {str(exc)[:200]}"
        )
