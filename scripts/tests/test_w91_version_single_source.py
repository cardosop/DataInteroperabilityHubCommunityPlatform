"""W9.1 (oss-release-remediation) — single-source version contract pins.

The repo-root ``VERSION`` file is the ONE release-version source; every
shipped version surface (hub/cli/sdk-py ``__version__``, sdk/js +
frontend ``package.json``, helm ``appVersion``) must agree.  The
checker (``scripts/check_release_versions.py``) is exercised against
the REAL tree:

* check mode exits 1 with a drift report when artifacts disagree (the
  CI gate — this is the ``check_release_versions`` the W12.6 item
  names, delivered with W9.1's single-source work);
* ``--sync`` rewrites drifted artifacts to VERSION;
* a drift pin proves the detector bites (mutated artifact flips RED);
* the release-please wiring is pinned: the config carries the
  ``version-file`` for VERSION and ``extra-files`` covering the same
  artifacts, and a workflow invokes the release-please action.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CHECKER = REPO_ROOT / "scripts" / "check_release_versions.py"
VERSION_FILE = REPO_ROOT / "VERSION"
RELEASE_PLEASE_CONFIG = REPO_ROOT / ".release-please-config.json"


def _checker(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(CHECKER), *args],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
        timeout=60,
    )


def _read_version_file() -> str:
    return VERSION_FILE.read_text(encoding="utf-8").strip()


def test_version_file_is_bare_semver():
    assert re.fullmatch(r"\d+\.\d+\.\d+", _read_version_file()), (
        "VERSION must be a bare semver (no v prefix — release-please "
        "adds the v in the tag name via include-v-in-tag)"
    )


def test_checker_reports_no_drift_on_the_synced_tree():
    proc = _checker("--check")
    assert proc.returncode == 0, proc.stdout


def test_every_named_surface_is_covered():
    # The artifacts the checker must cover (W12.6's named list: hub
    # __version__ / frontend / helm appVersion / SDK / CLI).
    text = CHECKER.read_text(encoding="utf-8")
    for marker in (
        '"hub" / "__init__.py"',
        '"cli" / "datahub_cli" / "__init__.py"',
        '"sdk" / "python" / "datahub_interoperability" / "__init__.py"',
        '"sdk" / "js" / "package.json"',
        '"sdk" / "js" / "package-lock.json"',
        '"frontend" / "package.json"',
        '"helm" / "Chart.yaml"',
    ):
        assert marker in text, f"checker missing artifact: {marker}"


def test_helm_app_version_matches():
    chart = yaml.safe_load((REPO_ROOT / "helm" / "Chart.yaml").read_text())
    assert chart["appVersion"] == _read_version_file()


def test_python_sdk_pep621_version_is_dynamic():
    """The SDK's published metadata must derive from its __init__ (the
    root fix for the 2.0.0/1.0.0/setup.py mismatch named in W12.6)."""
    pyproject = (REPO_ROOT / "sdk" / "python" / "pyproject.toml").read_text()
    project = pyproject.split("[project]")[1].split("\n[")[0]
    assert (
        'dynamic = ["version"]' in project
    ), "sdk/python pyproject.toml must declare version as dynamic"
    assert "tool.setuptools.dynamic" in pyproject
    assert "datahub_interoperability.__version__" in pyproject


def test_cli_setup_py_derives_from_init():
    setup = (REPO_ROOT / "cli" / "setup.py").read_text(encoding="utf-8")
    assert "datahub_cli" in setup
    assert "__init__.py" in setup


def _bump_py_version(text: str) -> str:
    return re.sub(
        r'^__version__ = "[^"]+"',
        '__version__ = "9.9.9"',
        text,
        flags=re.M,
    )


def _bump_json_version(text: str) -> str:
    data = json.loads(text)
    data["version"] = "9.9.9"
    return json.dumps(data, indent=2) + "\n"


def _bump_lockfile_version(text: str) -> str:
    data = json.loads(text)
    data["version"] = "9.9.9"
    data["packages"][""]["version"] = "9.9.9"
    return json.dumps(data, indent=2) + "\n"


def _bump_chart_version(text: str) -> str:
    return re.sub(
        r'^appVersion: "?[^"\n]+"?',
        'appVersion: "9.9.9"',
        text,
        flags=re.M,
    )


# Every shipped version surface — bumping ONE alone must flip the
# checker RED (the W12.6 evidence clause, extended to all 7 surfaces).
_DRIFT_SURFACES = [
    ("hub/__init__.py", _bump_py_version),
    ("cli/datahub_cli/__init__.py", _bump_py_version),
    (
        "sdk/python/datahub_interoperability/__init__.py",
        _bump_py_version,
    ),
    ("sdk/js/package.json", _bump_json_version),
    ("sdk/js/package-lock.json", _bump_lockfile_version),
    ("frontend/package.json", _bump_json_version),
    ("helm/Chart.yaml", _bump_chart_version),
]


@pytest.mark.parametrize(
    ("relpath", "mutate"),
    _DRIFT_SURFACES,
    ids=[rel for rel, _ in _DRIFT_SURFACES],
)
def test_drift_pin_bites_on_each_surface(relpath: str, mutate):
    """Falsifiability: mutating ONE artifact alone must flip the checker
    RED (the drift pin)."""
    path = REPO_ROOT / relpath
    original = path.read_text(encoding="utf-8")
    path.write_text(mutate(original))
    try:
        proc = _checker("--check")
        assert proc.returncode == 1
        assert relpath in proc.stdout
    finally:
        path.write_text(original)


def test_release_please_config_wired_to_version_file():
    config = json.loads(RELEASE_PLEASE_CONFIG.read_text(encoding="utf-8"))
    root = config["packages"]["."]
    assert (
        root.get("version-file") == "VERSION"
    ), "release-please must bump VERSION itself (the single source)"
    extra = {entry.get("path") for entry in root.get("extra-files", [])}
    for path in (
        "hub/__init__.py",
        "cli/datahub_cli/__init__.py",
        "sdk/python/datahub_interoperability/__init__.py",
        "sdk/js/package.json",
        "frontend/package.json",
        "helm/Chart.yaml",
    ):
        assert path in extra, f"release-please extra-files missing {path}"


def test_release_please_workflow_exists():
    workflow = REPO_ROOT / ".github" / "workflows" / "release-please.yml"
    assert workflow.is_file(), ".github/workflows/release-please.yml must exist"
    text = workflow.read_text(encoding="utf-8")
    assert "googleapis/release-please-action" in text
    assert "contents: write" in text
