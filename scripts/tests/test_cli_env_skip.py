"""TDD suite for ``cli/tests/_env_skip.py`` — the shared collection hook that
retires the five duplicated auto-skip bodies in the CLI conftest family
(integration / e2e / security / dimensions / use_cases).

W16 contract under test (real HTTP servers, no mocks):
  * ``MESHANT_FORCE_INTEGRATION=1`` — operator override, never touched.
  * API reachable — no markers.
  * API unreachable + local — skip markers only on the suite's path scopes,
    never on API-independent files.
  * API unreachable + CI — EnvironmentFailureError: the environment failure
    announces itself instead of skipping.
"""

from __future__ import annotations

import http.server
import pathlib
import socketserver
import sys
import threading

import pytest

REPO_ROOT = str(pathlib.Path(__file__).resolve().parent.parent.parent)
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from cli.tests._env_skip import auto_skip_unreachable_api
from envpolicy import EnvironmentFailureError


class _Handler404(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(404)
        self.end_headers()

    def log_message(self, *_args):
        pass


class _Server:
    def __init__(self):
        self.httpd = socketserver.TCPServer(("127.0.0.1", 0), _Handler404)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    @property
    def url(self) -> str:
        host, port = self.httpd.server_address
        return f"http://{host}:{port}"

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()


class _Item:
    """Minimal pytest item stand-in: the hook only touches fspath + markers."""

    def __init__(self, fspath: str):
        self.fspath = pathlib.Path(fspath)
        self.markers = []

    def add_marker(self, marker):
        self.markers.append(marker)


@pytest.fixture
def live_api():
    server = _Server()
    yield server
    server.close()


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("MESHANT_FORCE_INTEGRATION", raising=False)
    monkeypatch.delenv("MESHANT_API_URL", raising=False)


def _dead_url() -> str:
    import socket

    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return f"http://127.0.0.1:{port}/api/v1"


SCOPES = ("/tests/integration/",)
LABEL = "CLI integration tests"


class TestForceOverride:
    def test_force_integration_never_marks(self, monkeypatch):
        monkeypatch.setenv("MESHANT_FORCE_INTEGRATION", "1")
        monkeypatch.setenv("MESHANT_API_URL", _dead_url())
        item = _Item("/repo/cli/tests/integration/test_x.py")
        auto_skip_unreachable_api([item], suite_label=LABEL, path_scopes=SCOPES)
        assert item.markers == []


class TestReachableApi:
    def test_live_api_adds_no_markers(self, monkeypatch, live_api):
        monkeypatch.setenv("MESHANT_API_URL", f"{live_api.url}/api/v1")
        item = _Item("/repo/cli/tests/integration/test_x.py")
        auto_skip_unreachable_api([item], suite_label=LABEL, path_scopes=SCOPES)
        assert item.markers == []


class TestUnreachableApiLocal:
    def test_marks_scoped_items_only(self, monkeypatch):
        monkeypatch.setenv("MESHANT_API_URL", _dead_url())
        in_scope = _Item("/repo/cli/tests/integration/test_x.py")
        out_of_scope = _Item("/repo/cli/tests/unit/test_x.py")
        auto_skip_unreachable_api([in_scope, out_of_scope], suite_label=LABEL, path_scopes=SCOPES)
        assert len(in_scope.markers) == 1
        assert in_scope.markers[0].name == "skip"
        assert out_of_scope.markers == []

    def test_skip_reason_names_api_and_override(self, monkeypatch):
        monkeypatch.setenv("MESHANT_API_URL", _dead_url())
        item = _Item("/repo/cli/tests/integration/test_x.py")
        auto_skip_unreachable_api([item], suite_label=LABEL, path_scopes=SCOPES)
        reason = item.markers[0].kwargs["reason"]
        assert "Meshant API not reachable" in reason
        assert "MESHANT_FORCE_INTEGRATION=1" in reason

    def test_api_independent_files_never_marked(self, monkeypatch):
        monkeypatch.setenv("MESHANT_API_URL", _dead_url())
        independent = _Item("/repo/cli/tests/security/test_tls_verification.py")
        dependent = _Item("/repo/cli/tests/security/test_api_keys.py")
        auto_skip_unreachable_api(
            [independent, dependent],
            suite_label="Security integration tests",
            path_scopes=("/tests/security/",),
            api_independent_files=frozenset({"test_tls_verification.py"}),
        )
        assert independent.markers == []
        assert len(dependent.markers) == 1


class TestUnreachableApiInCi:
    def test_raises_instead_of_marking(self, monkeypatch):
        monkeypatch.setenv("CI", "true")
        monkeypatch.setenv("MESHANT_API_URL", _dead_url())
        item = _Item("/repo/cli/tests/integration/test_x.py")
        with pytest.raises(EnvironmentFailureError, match=r"\[W16\]"):
            auto_skip_unreachable_api([item], suite_label=LABEL, path_scopes=SCOPES)
        assert item.markers == []

    def test_raises_even_for_api_independent_files(self, monkeypatch):
        # The policy governs the environment, not the test file: in CI a
        # broken API fails the run even for files that would skip locally.
        monkeypatch.setenv("CI", "true")
        monkeypatch.setenv("MESHANT_API_URL", _dead_url())
        independent = _Item("/repo/cli/tests/security/test_tls_verification.py")
        with pytest.raises(EnvironmentFailureError, match=r"\[W16\]"):
            auto_skip_unreachable_api(
                [independent],
                suite_label="Security integration tests",
                path_scopes=("/tests/security/",),
                api_independent_files=frozenset({"test_tls_verification.py"}),
            )
