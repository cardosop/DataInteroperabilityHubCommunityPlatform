"""TDD suite for ``envpolicy.py`` — the W16 (Phase T.4) environment policy.

ONE policy for every "service unavailable / not authenticated / dependency
missing" branch in the Python test trees: when ``CI=true`` the branch RAISES
instead of skipping, so a broken environment fails the run loudly; local runs
keep the graceful skip.

The suite drives the policy against REAL HTTP servers on localhost (no mocks):
a live ``http.server`` serving 404 proves "the service answers"; a custom
handler serving 503 proves "a 5xx is DOWN" (the retired per-file
``_check_api_available()`` accepted anything below 600 — a 500 counted as up);
a closed port proves connection-refused is DOWN.

RED drills: every policy decision asserted both ways (CI raise vs local skip).
"""

from __future__ import annotations

import http.server
import socketserver
import sys
import threading

import pytest

REPO_ROOT = str(__import__("pathlib").Path(__file__).resolve().parent.parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from envpolicy import (
    EnvironmentFailureError,
    api_available,
    environment_guard,
    is_ci,
    probe_service,
    skip_or_fail,
)


class _Handler404(http.server.BaseHTTPRequestHandler):
    """Serves 404 to every request — a 4xx still proves the service is up."""

    def do_GET(self):
        self.send_response(404)
        self.end_headers()

    def log_message(self, *_args):
        pass


class _Handler503(http.server.BaseHTTPRequestHandler):
    """Serves 503 to every request — a broken service must count as DOWN."""

    def do_GET(self):
        self.send_response(503)
        self.end_headers()

    def log_message(self, *_args):
        pass


class _Server:
    """A real threaded HTTP server on an ephemeral localhost port."""

    def __init__(self, handler):
        self.httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        host, port = self.httpd.server_address
        return f"http://{host}:{port}/"

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


@pytest.fixture
def server404():
    server = _Server(_Handler404)
    yield server
    server.close()


@pytest.fixture
def server503():
    server = _Server(_Handler503)
    yield server
    server.close()


@pytest.fixture
def dead_port() -> str:
    """A port that is not listening — connection refused."""
    # Bind-and-release a port to get a (almost certainly) free one.
    import socket

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://127.0.0.1:{port}/"


@pytest.fixture(autouse=True)
def _ci_unset(monkeypatch):
    monkeypatch.delenv("CI", raising=False)


def _set_ci(monkeypatch, value):
    monkeypatch.setenv("CI", value)


class TestIsCi:
    def test_ci_true_variants(self, monkeypatch):
        for value in ("true", "1"):
            _set_ci(monkeypatch, value)
            assert is_ci() is True, f"CI={value!r} must count as CI"

    def test_ci_absent_is_not_ci(self):
        assert is_ci() is False

    def test_ci_other_values_are_not_ci(self, monkeypatch):
        for value in ("false", "0", "", "TRUE"):
            _set_ci(monkeypatch, value)
            assert is_ci() is False, f"CI={value!r} must not count as CI"


class TestEnvironmentGuard:
    def test_ci_raises_environment_failure_error(self, monkeypatch):
        _set_ci(monkeypatch, "true")
        with pytest.raises(EnvironmentFailureError, match=r"\[W16\]"):
            environment_guard("backend down")

    def test_ci_error_carries_the_detail(self, monkeypatch):
        _set_ci(monkeypatch, "true")
        with pytest.raises(EnvironmentFailureError, match="backend down"):
            environment_guard("backend down")

    def test_local_is_a_noop(self):
        # Must not raise, must not skip — the caller proceeds to its local
        # skip/fallback branch. The None pin is the observable contract of
        # the no-op (a raising guard would never reach it).
        assert environment_guard("backend down") is None


class TestSkipOrFail:
    def test_ci_raises_instead_of_skipping(self, monkeypatch):
        _set_ci(monkeypatch, "true")
        with pytest.raises(EnvironmentFailureError, match=r"\[W16\]"):
            skip_or_fail("dependency missing")

    def test_local_skips(self):
        with pytest.raises(pytest.skip.Exception):
            skip_or_fail("dependency missing")


class TestProbeService:
    def test_404_counts_as_up(self, server404):
        assert probe_service(server404.url) is True

    def test_503_counts_as_down(self, server503):
        # The retired `_check_api_available()` accepted anything < 600 —
        # a 500/503 counted as "up" and the suite ran green against a
        # broken backend. 5xx must be DOWN.
        assert probe_service(server503.url) is False

    def test_connection_refused_counts_as_down(self, dead_port):
        assert probe_service(dead_port) is False


class TestApiAvailable:
    def test_up_api_is_available(self, server404):
        assert api_available(server404.url) is True

    def test_down_api_skips_locally(self, dead_port):
        # Local: False — the caller's skipif/skip proceeds (graceful skip).
        assert api_available(dead_port) is False

    def test_down_api_raises_in_ci(self, monkeypatch, dead_port):
        # CI: the environment failure announces itself — the suite must fail,
        # not skip.
        _set_ci(monkeypatch, "true")
        with pytest.raises(EnvironmentFailureError, match=r"\[W16\]"):
            api_available(dead_port)

    def test_down_503_api_raises_in_ci(self, monkeypatch, server503):
        _set_ci(monkeypatch, "true")
        with pytest.raises(EnvironmentFailureError, match=r"\[W16\]"):
            api_available(server503.url)

    def test_default_url_honors_meshant_api_url(self, monkeypatch, server404):
        monkeypatch.setenv("MESHANT_API_URL", server404.url)
        assert api_available() is True
