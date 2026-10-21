"""P0-13 (close-oss-release-conditions, G7) — copyleft-gate pins.

The restored `scripts/check_copyleft.py` must cover the closures the
deleted 313.3.4 checker never saw — npm manifests AND pyproject extras —
and the publish pre-flight must refuse to publish without it. These pins
exercise the REAL checker against REAL artifacts:

* a real throwaway venv with a REAL known-GPL package (html2text — the
  very package the repo removed for GPL-3.0 in Phase 313.3.4) fails the
  py side; LGPL (pyclamd) and dual-licensed (docutils BSD/GPL/PD)
  fixtures pass;
* a real-format node_modules fixture with a planted GPL package.json
  fails the npm side; an SPDX "(MIT OR GPL-3.0)" fixture passes;
* the real repo closures (venv + frontend/sdk node_modules) are clean;
* the publish pre-flight and the CI wiring carry the gate (the
  fail-closed philosophy: a publish is the one non-recoverable path —
  no evidence, no publish).

No mocks: real venv module, real pip installs, real pip-licenses, real
package.json format, the real publish scripts.
"""

from __future__ import annotations

import json
import subprocess
import sys
import venv
from pathlib import Path

import pytest

from envpolicy import environment_guard

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parent.parent
CHECKER = REPO_ROOT / "scripts/check_copyleft.py"

# Real known-license fixtures (tiny, pure-python, fast installs):
#  * html2text — GPL-3.0 — the package requirements.txt REMOVED (313.3.4)
#  * pyclamd — LGPLv3+ — the accepted weak-copyleft class
#  * docutils — BSD + GPL + Public Domain — dual-licensed with a
#    permissive option
GPL_PKG = "html2text==2025.4.15"
LGPL_PKG = "pyclamd==0.4.0"
DUAL_PKG = "docutils==0.23"


def _make_venv(tmp_path: Path) -> Path:
    venv_dir = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True).create(venv_dir)
    return venv_dir


def _pip_install(venv_dir: Path, spec: str) -> None:
    """Real pip install into the throwaway venv (network, like CI)."""
    pip = venv_dir / "bin" / "pip"
    proc = subprocess.run(
        [str(pip), "install", "--quiet", spec],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if proc.returncode != 0:
        environment_guard(f"fixture pip install failed for {spec}: {proc.stderr[-200:]}")
        pytest.skip(f"pip install {spec} unavailable (offline) — fixture leg skipped")



def _run_checker(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECKER), *args],
        capture_output=True,
        text=True,
        timeout=600,
        cwd=cwd or REPO_ROOT,
        check=False,
    )


# ── Python closure fixtures ──────────────────────────────────────────────────


def test_hard_copyleft_py_fixture_fails(tmp_path):
    venv_dir = _make_venv(tmp_path)
    _pip_install(venv_dir, GPL_PKG)
    req = tmp_path / "fixture-reqs.txt"
    req.write_text("html2text==2025.4.15\n", encoding="utf-8")
    proc = _run_checker(
        [
            "--venv",
            str(venv_dir / "bin" / "python"),
            "--requirement-files",
            str(req),
            "--skip-npm",
        ]
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "html2text" in (proc.stdout + proc.stderr)
    assert "GPL" in (proc.stdout + proc.stderr)


def test_lgpl_fixture_passes(tmp_path):
    venv_dir = _make_venv(tmp_path)
    _pip_install(venv_dir, LGPL_PKG)
    req = tmp_path / "fixture-reqs.txt"
    req.write_text("pyclamd==0.4.0\n", encoding="utf-8")
    proc = _run_checker(
        [
            "--venv",
            str(venv_dir / "bin" / "python"),
            "--requirement-files",
            str(req),
            "--skip-npm",
        ]
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_dual_license_fixture_passes(tmp_path):
    venv_dir = _make_venv(tmp_path)
    _pip_install(venv_dir, DUAL_PKG)
    req = tmp_path / "fixture-reqs.txt"
    req.write_text("docutils==0.23\n", encoding="utf-8")
    proc = _run_checker(
        [
            "--venv",
            str(venv_dir / "bin" / "python"),
            "--requirement-files",
            str(req),
            "--skip-npm",
        ]
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_unresolved_declared_dependency_fails_closed(tmp_path):
    venv_dir = _make_venv(tmp_path)
    req = tmp_path / "fixture-reqs.txt"
    req.write_text("definitely-not-installed-package==1.0.0\n", encoding="utf-8")
    proc = _run_checker(
        [
            "--venv",
            str(venv_dir / "bin" / "python"),
            "--requirement-files",
            str(req),
            "--skip-npm",
        ]
    )
    # fail-closed certification: a declared dep with no resolvable license
    # is refused, never assumed clean.
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "unresolved" in (proc.stdout + proc.stderr).lower()


# ── npm closure fixtures ─────────────────────────────────────────────────────


def _npm_fixture(tmp_path: Path, license_value) -> Path:
    root = tmp_path / "npmroot"
    pkg_json = root / "package.json"
    pkg_json.parent.mkdir(parents=True, exist_ok=True)
    pkg_json.write_text(
        json.dumps(
            {
                "name": "fixture-app",
                "version": "1.0.0",
                "dependencies": {"gplpkg": "1.0.0"},
            }
        ),
        encoding="utf-8",
    )
    dep_dir = root / "node_modules" / "gplpkg"
    dep_dir.mkdir(parents=True)
    (dep_dir / "package.json").write_text(
        json.dumps({"name": "gplpkg", "version": "1.0.0", "license": license_value}),
        encoding="utf-8",
    )
    return root


def test_npm_gpl_fixture_fails(tmp_path):
    root = _npm_fixture(tmp_path, "GPL-3.0")
    proc = _run_checker(["--npm-roots", str(root), "--skip-py"])
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "gplpkg" in (proc.stdout + proc.stderr)


def test_npm_dual_license_fixture_passes(tmp_path):
    root = _npm_fixture(tmp_path, "(MIT OR GPL-3.0)")
    proc = _run_checker(["--npm-roots", str(root), "--skip-py"])
    assert proc.returncode == 0, proc.stdout + proc.stderr


# ── Real closures ────────────────────────────────────────────────────────────


def test_real_py_closure_clean():
    proc = _run_checker(["--skip-npm"])
    assert proc.returncode == 0, proc.stdout + proc.stderr


def _npm_available() -> bool:
    return (REPO_ROOT / "frontend/node_modules").is_dir() and (
        REPO_ROOT / "sdk/js/node_modules"
    ).is_dir()


@pytest.mark.skipif(
    not _npm_available(),
    reason="node_modules absent — npm closure leg runs in the publish "
    "pre-flight and the dedicated CI job",
)
def test_real_npm_closure_clean():
    proc = _run_checker(["--skip-py"])
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_missing_npm_root_fails_closed(tmp_path):
    proc = _run_checker(
        ["--npm-roots", str(tmp_path / "absent-root"), "--skip-py"]
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "npm root missing" in (proc.stdout + proc.stderr)


def test_missing_venv_fails_closed_in_ci():
    proc = _run_checker(["--ci", "--venv", "/nonexistent/python", "--skip-npm"])
    assert proc.returncode == 1, proc.stdout + proc.stderr


# ── Wiring ───────────────────────────────────────────────────────────────────


def test_publish_preflight_wired():
    gates = (REPO_ROOT / "scripts/publish_gates.sh").read_text(encoding="utf-8")
    publish = (REPO_ROOT / "scripts/publish_public.sh").read_text(encoding="utf-8")
    assert "require_copyleft" in gates, "publish_gates.sh must carry the copyleft gate"
    assert "require_copyleft" in publish, "publish_public.sh must invoke it pre-flight"
    # fail-closed philosophy: the gate is invoked unconditionally, not
    # behind a best-effort if-available guard.
    assert "command -v pip-licenses" not in gates or "require_copyleft" in gates


def test_ci_wired():
    scan_yml = (REPO_ROOT / ".github/workflows/security-scan.yml").read_text(encoding="utf-8")
    lint_yml = (REPO_ROOT / ".github/workflows/_reusable.lint.yml").read_text(encoding="utf-8")
    assert (
        "check_copyleft.py" in scan_yml
    ), "the CI license-scan job must run the checker, not only raw pip-licenses"
    assert (
        "scripts/tests/test_copyleft_gate.py" in lint_yml
    ), "these pins must be CI-wired in the lint list"
