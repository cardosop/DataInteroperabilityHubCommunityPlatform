import pytest

pytestmark = pytest.mark.mvp

"""
Phase 216.5.6 — Dimension: proxy failure.

Verifies that the client handles a dead HTTPS_PROXY gracefully —
raises a connection-level error, not a cryptic SSL or protocol error.
"""

import os
from unittest.mock import patch

import requests
from tests.fixtures.test_data import unique_port


def test_dead_proxy_raises_connection_error():
    """HTTPS_PROXY pointing to a dead host must raise ConnectionError."""
    dead_port = unique_port()
    dead_proxy = f"http://127.0.0.1:{dead_port}"

    with patch.dict(os.environ, {"HTTPS_PROXY": dead_proxy, "HTTP_PROXY": dead_proxy}):
        with pytest.raises(
            (
                requests.exceptions.ConnectionError,
                requests.exceptions.ProxyError,
            )
        ):
            requests.get(
                "https://stagingmeshant-internal.example.com/api/v1/health/",
                timeout=5,
                # Explicit proxies to override any session-level config
                proxies={"https": dead_proxy, "http": dead_proxy},
            )


def test_proxy_error_message_is_actionable():
    """The proxy error must mention the proxy address or 'proxy'."""
    dead_port = unique_port()
    dead_proxy = f"http://127.0.0.1:{dead_port}"

    try:
        requests.get(
            "https://httpbin.org/get",
            timeout=5,
            proxies={"https": dead_proxy},
        )
        pytest.fail("Expected ProxyError or ConnectionError")
    except (requests.exceptions.ProxyError, requests.exceptions.ConnectionError) as exc:
        msg = str(exc).lower()
        assert "proxy" in msg or "127.0.0.1" in msg or "connect" in msg, (
            f"Proxy error message is not actionable: {str(exc)[:200]}"
        )


def test_no_proxy_env_is_respected():
    """NO_PROXY=*.meshant.com must bypass the proxy for meshant hosts."""
    dead_port = unique_port()
    dead_proxy = f"http://127.0.0.1:{dead_port}"

    # With NO_PROXY set, the request should NOT go through the dead proxy
    # and instead connect directly (which may succeed or fail with a
    # different error — the point is it must NOT raise ProxyError).
    with patch.dict(
        os.environ,
        {
            "HTTPS_PROXY": dead_proxy,
            "NO_PROXY": "*.meshant.com,localhost,127.0.0.1",
        },
    ):
        try:
            requests.get("http://127.0.0.1:1/health/", timeout=2)
        except requests.exceptions.ProxyError:
            pytest.fail("NO_PROXY was not respected — request went through dead proxy")
        except requests.exceptions.ConnectionError:
            pass  # Expected: direct connection refused (no proxy involved)
