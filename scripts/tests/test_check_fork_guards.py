"""GATE-56 (oss-release-remediation W7.3) fork-safety pins — no mocks.

The RED phase of W7.3: the real-tree pins below failed before the guard
sweep (e2e.yml, k6-load-test-gate.yml, playwright-e2e.yml, terraform
x2, test-marketplace-integration.yml, frontend-ci.yml/frontend-tests.yml
codecov steps, visual-regression.yml) and turned green only after every
secret-using pull_request path gained a fork guard / self-skip.

Pins exercise the REAL gate as a subprocess against:
  * the real workflow trees (master GREEN pins),
  * planted temp workflow dirs (the gate BITES — an unguarded secret
    use, a typo'd guard, a removed visual-regression fix, or an
    origin/<base> DCO range flips it RED; the sanctioned guard forms
    stay GREEN).
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
GATE = REPO_ROOT / "scripts" / "check_fork_guards.py"
PRIVATE_WF = REPO_ROOT / ".github" / "workflows"
OVERLAY_WF = (
    REPO_ROOT / "scripts" / "publish_public_overlay" / ".github" / "workflows"
)

GUARDED = """name: guarded
on:
  pull_request:
jobs:
  needs-secret:
    runs-on: ubuntu-latest
    if: ${{ github.event_name != 'pull_request' || github.event.pull_request.head.repo.fork == false }}
    steps:
      - run: echo "${{ secrets.SMOKE_ADMIN_PASSWORD }}"
"""

SELF_SKIP = """name: selfskip
on: [pull_request]
jobs:
  chromatic:
    runs-on: ubuntu-latest
    steps:
      - name: detect token
        run: |
          if [ -n "${{ secrets.CHROMATIC_PROJECT_TOKEN }}" ]; then
            echo present
          else
            echo "token unset — skipping"
          fi
      - name: upload
        run: echo "${{ secrets.CHROMATIC_PROJECT_TOKEN }}"
"""

STEP_GUARDED = """name: stepguarded
on: [pull_request]
jobs:
  job:
    runs-on: ubuntu-latest
    steps:
      - name: upload
        if: ${{ github.event_name != 'pull_request' || github.event.pull_request.head.repo.fork == false }}
        run: echo "${{ secrets.CODECOV_TOKEN }}"
"""

PUSH_ONLY = """name: pushonly
on: [pull_request]
jobs:
  job:
    runs-on: ubuntu-latest
    if: github.event_name == 'push'
    steps:
      - run: echo "${{ secrets.AWS_SECRET }}"
"""

GH_TOKEN_ONLY = """name: ghtoken
on: [pull_request]
jobs:
  job:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: echo "${{ secrets.GITHUB_TOKEN }}"
"""

UNGUARDED = """name: unguarded
on: [pull_request]
jobs:
  job:
    runs-on: ubuntu-latest
    steps:
      - run: echo "${{ secrets.SMOKE_ADMIN_PASSWORD }}"
"""

TYPO_GUARD = """name: typo
on: [pull_request]
jobs:
  job:
    runs-on: ubuntu-latest
    if: ${{ github.event_name != 'pull_request' || github.event.pull_request.head.repo.forked == false }}
    steps:
      - run: echo "${{ secrets.SMOKE_ADMIN_PASSWORD }}"
"""

VISUAL_OK = """name: Visual Regression Testing
on:
  pull_request:
    branches: [main]
env:
  CHROMATIC_PROJECT_TOKEN: ${{ secrets.CHROMATIC_PROJECT_TOKEN }}
jobs:
  visual-regression:
    runs-on: ubuntu-latest
    if: ${{ github.event_name != 'pull_request' || github.event.pull_request.head.repo.fork == false }}
    steps:
      - name: detect token
        run: |
          if [ -n "${{ env.CHROMATIC_PROJECT_TOKEN }}" ]; then
            echo present
          else
            echo "token unset — skipping"
          fi
      - name: Run Chromatic
        run: echo "${{ secrets.CHROMATIC_PROJECT_TOKEN }}"
  storybook-build-smoke:
    runs-on: ubuntu-latest
    if: ${{ github.event_name == 'pull_request' && github.event.pull_request.head.repo.fork == true }}
    steps:
      - run: npm run build-storybook
"""

VISUAL_NO_GUARD = VISUAL_OK.replace(
    "if: ${{ github.event_name != 'pull_request' || "
    "github.event.pull_request.head.repo.fork == false }}\n    steps:",
    "steps:",
)

DCO_ORIGIN = """name: dco
on: [pull_request]
jobs:
  dco:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - run: bash scripts/check_dco.sh "origin/${{ github.event.pull_request.base.ref }}..HEAD"
"""

DCO_BASE_SHA = """name: dco
on: [pull_request]
jobs:
  dco:
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - run: bash scripts/check_dco.sh "${{ github.event.pull_request.base.sha }}..${{ github.event.pull_request.head.sha }}"
"""


def _run_gate(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(GATE), *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def empty_allowlist(tmp_path):
    # Planted trees run against an EMPTY allowlist: the real
    # ci.yml:test:STRIPE anchor would otherwise report dead in a temp dir.
    path = tmp_path / "allowlist.txt"
    path.write_text("# empty\n")
    return path


def _write_wf(tmp_path: Path, name: str, content: str) -> Path:
    directory = tmp_path / name.replace(".", "_")
    directory.mkdir()
    (directory / name).write_text(content)
    return directory


class TestRealTrees:
    """Master GREEN pins — both workflow trees are fork-safe."""

    def test_private_workflows_fork_safe(self):
        # The DEFAULT invocation — both trees + the real allowlist.
        result = _run_gate()
        assert result.returncode == 0, result.stdout + result.stderr
        assert "fork-guard check clean" in result.stdout

    def test_public_overlay_workflows_fork_safe(self):
        result = _run_gate(
            "--workflow-dir",
            str(OVERLAY_WF),
            "--allowlist",
            str(REPO_ROOT / "scripts" / "fork_guards_allowlist.txt"),
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_overlay_dco_uses_pr_commit_range(self):
        text = (OVERLAY_WF / "ci-core.yml").read_text(encoding="utf-8")
        assert "check_dco.sh" in text
        assert "base.sha" in text and "head.sha" in text
        assert "origin/${{ github.event.pull_request.base.ref }}" not in text
        assert 'base.sha }}..${{ github.event.pull_request.head.sha' in text

    def test_every_fork_guard_is_canonical(self):
        # A typo'd guard is dead — the canonical expression is pinned.
        for directory in (PRIVATE_WF, OVERLAY_WF):
            for path in directory.glob("*.yml"):
                text = path.read_text(encoding="utf-8")
                for match in re.finditer(r"head\.repo\.[a-zA-Z_]+", text):
                    assert match.group(0) == "head.repo.fork", (
                        f"{path.name}: non-canonical guard "
                        f"{match.group(0)!r}"
                    )


class TestSanctionedGuardForms:
    """The four sanctioned guard shapes pass the gate."""

    @pytest.mark.parametrize(
        "content",
        [GUARDED, SELF_SKIP, STEP_GUARDED, PUSH_ONLY, GH_TOKEN_ONLY],
        ids=["job-guard", "self-skip", "step-guard", "push-only", "gh-token"],
    )
    def test_sanctioned_forms_pass(self, tmp_path, empty_allowlist, content):
        directory = _write_wf(tmp_path, "wf.yml", content)
        result = _run_gate(
            "--workflow-dir", str(directory), "--allowlist", str(empty_allowlist)
        )
        assert result.returncode == 0, result.stdout + result.stderr


class TestAllowlist:
    """Degrade-graceful secret uses may be allowlisted; dead anchors fail."""

    def test_allowlisted_degradable_secret_passes(self, tmp_path, empty_allowlist):
        directory = _write_wf(tmp_path, "ci.yml", UNGUARDED)
        allow = tmp_path / "allow.txt"
        allow.write_text(
            "ci.yml:job:SMOKE_ADMIN_PASSWORD:optional - tests self-skip\n"
        )
        result = _run_gate(
            "--workflow-dir", str(directory), "--allowlist", str(allow)
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_dead_allowlist_anchor_bites(self, tmp_path, empty_allowlist):
        directory = _write_wf(tmp_path, "ci.yml", UNGUARDED)
        allow = tmp_path / "allow.txt"
        allow.write_text(
            "ci.yml:no-such-job:SMOKE_ADMIN_PASSWORD:reason\n"
        )
        result = _run_gate(
            "--workflow-dir",
            str(directory),
            "--allowlist",
            str(allow),
            "--check-dead-anchors",
        )
        assert result.returncode == 1
        assert "job missing" in result.stdout

    def test_malformed_allowlist_line_fails(self, tmp_path, empty_allowlist):
        directory = _write_wf(tmp_path, "ci.yml", UNGUARDED)
        allow = tmp_path / "allow.txt"
        allow.write_text("ci.yml:job\n")
        result = _run_gate(
            "--workflow-dir", str(directory), "--allowlist", str(allow)
        )
        assert result.returncode == 2
        assert "malformed allowlist line" in result.stderr


class TestPlantedViolationsBite:
    """Drift pins — the W7.3 regression classes flip the gate RED."""

    def test_unguarded_secret_bites(self, tmp_path, empty_allowlist):
        directory = _write_wf(tmp_path, "wf.yml", UNGUARDED)
        result = _run_gate(
            "--workflow-dir", str(directory), "--allowlist", str(empty_allowlist)
        )
        assert result.returncode == 1
        assert "secrets.SMOKE_ADMIN_PASSWORD" in result.stdout

    def test_typo_guard_bites(self, tmp_path, empty_allowlist):
        directory = _write_wf(tmp_path, "wf.yml", TYPO_GUARD)
        result = _run_gate(
            "--workflow-dir", str(directory), "--allowlist", str(empty_allowlist)
        )
        assert result.returncode == 1
        assert "secrets.SMOKE_ADMIN_PASSWORD" in result.stdout

    def test_visual_regression_guard_removed_bites(self, tmp_path, empty_allowlist):
        directory = _write_wf(tmp_path, "visual-regression.yml", VISUAL_NO_GUARD)
        result = _run_gate(
            "--workflow-dir", str(directory), "--allowlist", str(empty_allowlist)
        )
        assert result.returncode == 1
        assert "no fork guard" in result.stdout

    def test_visual_regression_fix_passes(self, tmp_path, empty_allowlist):
        directory = _write_wf(tmp_path, "visual-regression.yml", VISUAL_OK)
        result = _run_gate(
            "--workflow-dir", str(directory), "--allowlist", str(empty_allowlist)
        )
        assert result.returncode == 0, result.stdout + result.stderr

    def test_dco_origin_range_bites(self, tmp_path, empty_allowlist):
        directory = _write_wf(tmp_path, "ci-core.yml", DCO_ORIGIN)
        result = _run_gate(
            "--workflow-dir", str(directory), "--allowlist", str(empty_allowlist)
        )
        assert result.returncode == 1
        assert "base.sha..head.sha" in result.stdout

    def test_dco_base_sha_passes(self, tmp_path, empty_allowlist):
        directory = _write_wf(tmp_path, "ci-core.yml", DCO_BASE_SHA)
        result = _run_gate(
            "--workflow-dir", str(directory), "--allowlist", str(empty_allowlist)
        )
        assert result.returncode == 0, result.stdout + result.stderr
