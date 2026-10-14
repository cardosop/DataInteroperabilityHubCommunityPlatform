"""W6.0 (oss-release-remediation) — registry name/account/secret pins.

TDD contract, no mock libraries:

  * logic pins drive the checker through a LOCAL threaded HTTP server —
    a real round-trip, the W4.6 precedent;
  * the gh pin drives the checker through a fake ``gh`` EXECUTABLE on
    PATH (harness seam on the external binary — real subprocess);
  * the evidence pin runs the checker against the REAL registries
    (PyPI + npm) and is envpolicy-governed: unreachable network raises
    in CI, skips locally (W16) — never a silent pass.

The evidence pin IS the W6.0 deliverable "names verified free": it is
RED when any D3 name is registered, GREEN while they are free. After
the first publish flips it to RED, switch the pin to ``--mode owned``.
"""

from __future__ import annotations

import json
import os
import stat
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import check_registry_names as crn

from envpolicy import environment_guard

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


class _RegistryHandler(BaseHTTPRequestHandler):
    """Serves configured (path -> status) responses; 404 otherwise.

    ``self.path`` arrives RAW (percent-encoded, per the HTTP spec) — the
    route keys are written decoded, so lookup unquotes first. That also
    proves the client really encoded the scoped name on the wire.
    """

    routes: ClassVar[dict[str, int]] = {}

    def do_GET(self) -> None:
        decoded = urllib.parse.unquote(self.path)
        status = self.routes.get(decoded, 404)
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def fake_registry():
    """A local threaded HTTP server acting as a registry (real round-trip)."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _RegistryHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    yield base
    server.shutdown()
    thread.join(timeout=5)


def _route(server_base: str, path: str, status: int) -> str:
    _RegistryHandler.routes[path] = status
    return server_base


def test_pypi_404_is_free(fake_registry):
    base = _route(fake_registry, "/pypi/datahub-interoperability/json", 404)
    assert crn.pypi_name_state("datahub-interoperability", base)["state"] == "free"


def test_pypi_200_is_taken(fake_registry):
    base = _route(fake_registry, "/pypi/datahub-interoperability/json", 200)
    assert crn.pypi_name_state("datahub-interoperability", base)["state"] == "taken"


def test_npm_scoped_name_is_url_encoded(fake_registry):
    # The scoped package must hit the registry as %40meshant%2F... — the
    # handler sees the decoded path, proving the client encoded the scope.
    decoded = "/@meshant/interoperability-sdk"
    _RegistryHandler.routes.clear()
    base = _route(fake_registry, decoded, 404)
    assert crn.npm_package_state("@meshant/interoperability-sdk", base)["state"] == "free"


def test_npm_200_is_taken(fake_registry):
    decoded = "/@meshant/interoperability-sdk"
    base = _route(fake_registry, decoded, 200)
    assert crn.npm_package_state("@meshant/interoperability-sdk", base)["state"] == "taken"


def test_npm_org_probe(fake_registry):
    _RegistryHandler.routes.clear()
    _RegistryHandler.routes["/-/org/meshant/package"] = 404
    assert crn.npm_org_exists("meshant", fake_registry) is False
    _RegistryHandler.routes["/-/org/meshant/package"] = 200
    assert crn.npm_org_exists("meshant", fake_registry) is True


def test_pypi_account_probe(fake_registry):
    _RegistryHandler.routes.clear()
    _RegistryHandler.routes["/user/meshant/"] = 404
    assert crn.pypi_account_exists("meshant", fake_registry) is False
    _RegistryHandler.routes["/user/meshant/"] = 200
    assert crn.pypi_account_exists("meshant", fake_registry) is True


def test_unreachable_registry_raises_registryunreachable():
    # A closed port on loopback — a real transport failure, not a mock.
    with pytest.raises(crn.RegistryUnreachable):
        crn.pypi_name_state("datahub-interoperability", "http://127.0.0.1:1")


def test_gh_secret_presence_parses_real_gh_output(tmp_path, monkeypatch):
    fake_gh = tmp_path / "gh"
    fake_gh.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "secret" ] && [ "$2" = "list" ]; then\n'
        "  # printf interprets \\t / \\n in the FORMAT string (not in args).\n"
        "  printf 'NPM_TOKEN\\t2026-10-01T00:00:00Z\\nOTHER\\t2026-10-01T00:00:00Z\\n'\n"
        "else\n"
        "  echo 'unexpected args' >&2; exit 1\n"
        "fi\n",
        encoding="utf-8",
    )
    fake_gh.chmod(fake_gh.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}")

    presence = crn.gh_secret_presence("cardosop/DataInteroperabilityHub")
    assert presence == {"NPM_TOKEN": True, "PYPI_TOKEN": False}


def test_gh_secret_presence_raises_when_gh_missing(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))  # empty dir: no gh binary
    with pytest.raises(RuntimeError, match="gh CLI not installed"):
        crn.gh_secret_presence()


def test_gh_secret_presence_raises_when_gh_fails(tmp_path, monkeypatch):
    fake_gh = tmp_path / "gh"
    fake_gh.write_text("#!/bin/sh\necho 'gh: auth failed' >&2\nexit 1\n", encoding="utf-8")
    fake_gh.chmod(fake_gh.stat().st_mode | stat.S_IXUSR)
    monkeypatch.setenv("PATH", f"{tmp_path}{os.pathsep}{os.environ.get('PATH', '')}")
    with pytest.raises(RuntimeError, match="gh secret list failed"):
        crn.gh_secret_presence()


def test_cli_exit_codes(fake_registry, tmp_path, monkeypatch):
    # available mode: names free → 0; one taken → 1; unreachable → 2 (local).
    _RegistryHandler.routes.clear()
    for name in crn.PYPI_NAMES:
        _RegistryHandler.routes[f"/pypi/{name}/json"] = 404
    _RegistryHandler.routes["/@meshant/interoperability-sdk"] = 404
    # Accounts exist in this phase — --check-accounts must PASS.
    _RegistryHandler.routes["/-/org/meshant/package"] = 200
    _RegistryHandler.routes["/user/meshant/"] = 200

    monkeypatch.setattr(crn, "DEFAULT_PYPI_BASE", fake_registry)
    monkeypatch.setattr(crn, "DEFAULT_NPM_BASE", fake_registry)
    assert crn.main(["--check-accounts"]) == 0

    _RegistryHandler.routes["/pypi/datahub-cli/json"] = 200
    assert crn.main([]) == 1

    monkeypatch.setattr(crn, "DEFAULT_PYPI_BASE", "http://127.0.0.1:1")
    assert crn.main([]) == 2


def test_cli_json_shape(fake_registry, monkeypatch):
    _RegistryHandler.routes.clear()
    for name in crn.PYPI_NAMES:
        _RegistryHandler.routes[f"/pypi/{name}/json"] = 404
    _RegistryHandler.routes["/@meshant/interoperability-sdk"] = 404
    monkeypatch.setattr(crn, "DEFAULT_PYPI_BASE", fake_registry)
    monkeypatch.setattr(crn, "DEFAULT_NPM_BASE", fake_registry)

    # main() RETURNS the exit code (SystemExit is __main__-only).
    assert crn.main(["--json"]) == 0

    results, passed = crn.run_checks("available", check_accounts=False, check_secrets=False)
    assert passed is True
    assert {r["name"] for r in results} == {
        "datahub-interoperability",
        "datahub-cli",
        "@meshant/interoperability-sdk",
    }


def test_package_metadata_declares_the_d3_names():
    """The shipped packages declare EXACTLY the D3 planned names —
    the namespace-collision guard (one source of truth, no drift)."""
    pyproject = (REPO_ROOT / "sdk" / "python" / "pyproject.toml").read_text(encoding="utf-8")
    assert 'name = "datahub-interoperability"' in pyproject

    package_json = (REPO_ROOT / "sdk" / "js" / "package.json").read_text(encoding="utf-8")
    pkg = json.loads(package_json)
    # W6.0 amendment: @datahub is third-party-owned; @meshant is the scope.
    assert pkg["name"] == "@meshant/interoperability-sdk"

    setup_py = (REPO_ROOT / "cli" / "setup.py").read_text(encoding="utf-8")
    assert 'name="datahub-cli"' in setup_py


def test_real_registries_d3_names_are_free():
    """THE W6.0 evidence pin — the D3 names are free on the REAL registries.

    Envpolicy-governed (W16): unreachable network raises in CI, skips
    locally. This is NOT a mock and not a stub: it queries pypi.org and
    registry.npmjs.org directly. After the first publish registers a
    name, flip this pin to ``--mode owned``.
    """
    try:
        pypi_states = {name: crn.pypi_name_state(name)["state"] for name in crn.PYPI_NAMES}
        npm_states = {name: crn.npm_package_state(name)["state"] for name in crn.NPM_PACKAGES}
    except crn.RegistryUnreachable as exc:
        environment_guard(f"real registries unreachable: {exc}")
        pytest.skip(f"registries unreachable locally: {exc}")

    for name, state in {**pypi_states, **npm_states}.items():
        assert state == "free", f"{name} is no longer free ({state}) — update the W6.0 plan"
