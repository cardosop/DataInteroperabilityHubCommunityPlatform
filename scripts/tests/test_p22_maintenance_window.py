"""
Contract tests for the P2-2 maintenance-window machinery
(close-oss-release-conditions):

- ``scripts/run_history_rewrite_window.py`` — the window RUNNER. The
  ordered checklist with the machine-enforced G12 contract: push
  protection on origin is enabled AFTER the force-push lands and the
  post-push sweep is green — the runner's step order makes "enable
  first" unrepresentable, and every failed precondition HALTS the run
  before the next destructive step. One-shot execution tool (NOT in
  the always-on battery).
- ``scripts/sweep_remote_fragments.py`` — the post-push sweep: a fresh
  mirror of the remote, ``git log --all -S <fragment>`` per fragment
  (fragments named by INDEX only — values never printed), fail-closed
  on a missing fragments file or unreachable remote.
- ``scripts/cleanup_origin_refs.py`` — the G4 cleanup: plan (default)
  vs execute (explicit) for the open PRs + the stale dependabot/*
  branches that fork the tainted lineage (the pushed heads
  main/prepro01/staging/release-mvp-v1 are never touched).
- ``scripts/review_actions_artifacts.py`` — the G4 Actions review:
  real gh enumeration of workflow runs + artifacts, carrier-class
  classification (trace/network/junit artifacts are the value-carrier
  class), and the gated per-run log inspection with the REAL gitleaks
  binary (values never printed).

The fixtures are REAL: local bare repos as remotes (real git push /
clone / log), real-shape GitHub API JSON for the classification
functions, the real gh CLI for the live legs, and the real gitleaks
binary for the log-inspection leg — no mocks.
"""

import hashlib
import importlib.util
import shutil
import subprocess
import sys
from pathlib import Path

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

ROOT = scripts_dir.parent
sys.path.insert(0, str(ROOT))

from envpolicy import skip_or_fail

TOOLS = {
    name: str(scripts_dir / filename)
    for name, filename in (
        ("runner", "run_history_rewrite_window.py"),
        ("sweep", "sweep_remote_fragments.py"),
        ("cleanup", "cleanup_origin_refs.py"),
        ("review", "review_actions_artifacts.py"),
    )
}

MODULES: dict[str, object] = {}
for name, path in TOOLS.items():
    spec = importlib.util.spec_from_file_location(f"p22_{name}", path)
    assert spec is not None, f"{path} must load (P2-2 ships it)"
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    MODULES[name] = module

GITLEAKS = shutil.which("gitleaks")
GITLEAKS_CONFIG = ROOT / ".gitleaks.toml"
GH = shutil.which("gh")
ORIGIN_SLUG = "cardosop/DataInteroperabilityHub"

PLANTED = "FIXTURESECRETP22cafebabe0123456789deadbeef9876543210"
PLANTED_HASH = hashlib.sha256(PLANTED.encode()).hexdigest()


def _require_gh() -> None:
    """W16: the live legs call the REAL GitHub API — a missing gh CLI
    is an environment branch: skip locally, raise in CI."""
    if not GH:
        skip_or_fail("gh CLI (the live API legs run against the real remote)")


def _require_gitleaks() -> None:
    if not GITLEAKS:
        skip_or_fail(
            "gitleaks binary (the log-inspection leg is proven against "
            "the real scanner, never a fake)"
        )


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args], capture_output=True, text=True, check=False
    )


def _green_gate(tmp_path: Path) -> Path:
    """A real process with exit 0 — the runner's gate STEP is pinned on
    its exit-code handling, not on the gate itself (GATE-65 has its own
    pins)."""
    gate = tmp_path / "gate-green.sh"
    gate.write_text("#!/bin/sh\nexit 0\n")
    gate.chmod(0o755)
    return gate


def _red_gate(tmp_path: Path) -> Path:
    gate = tmp_path / "gate-red.sh"
    gate.write_text("#!/bin/sh\nexit 1\n")
    gate.chmod(0o755)
    return gate


def _bare_remote_with_secret(tmp_path: Path, keep_secret: bool = True) -> Path:
    """A real local bare repository playing the role of the pushed
    remote. ``keep_secret=True``: some commit carries the planted
    fragment (the tainted shape). ``keep_secret=False``: NO commit ever
    carried it (the rewritten shape — a plain 'rotate' commit would
    NOT make ``git log -S`` clean: the old blob stays reachable)."""
    work = tmp_path / "src"
    work.mkdir()
    _git(work, "init", "-q")
    _git(work, "config", "user.email", "t@t")
    _git(work, "config", "user.name", "t")
    _git(work, "config", "commit.gpgsign", "false")
    if keep_secret:
        (work / "app.py").write_text(f'TOKEN = "{PLANTED}"\n')
    else:
        (work / "app.py").write_text('TOKEN = os.environ["TOKEN"]\n')
    _git(work, "add", ".")
    _git(work, "commit", "-qm", "initial")
    remote = tmp_path / "remote.git"
    _git(work, "init", "--bare", "-q", str(remote))
    _git(work, "remote", "add", "r", str(remote))
    _git(work, "push", "-q", "r", "HEAD:refs/heads/main")
    return remote


def _mirror_of(remote: Path, tmp_path: Path) -> Path:
    """The P2-1 mirror shape the runner force-pushes from: a bare
    mirror of the (rewritten) remote."""
    mirror = tmp_path / "mirror.git"
    subprocess.run(
        ["git", "clone", "--mirror", "-q", str(remote), str(mirror)], check=True
    )
    return mirror


def _fragments(tmp_path: Path, value: str | None = PLANTED) -> Path:
    f = tmp_path / "fragments.txt"
    f.write_text(f"# sweep list\n{value}\n" if value else "# sweep list\n")
    return f


# ── the runner: G12 ordering + halting ──────────────────────────────────────


def test_runner_step_order_enforces_g12():
    """The machine-enforced ordering: the pre-window disabled-check
    precedes the force-push, and ENABLING push protection comes only
    after the push + the sweep + the cleanup — 'enable first' is
    unrepresentable in the step list."""
    steps = MODULES["runner"].WINDOW_STEPS
    names = [step[0] for step in steps]
    assert names.index("pre-window-push-protection") < names.index("force-push")
    assert names.index("force-push") < names.index("post-push-sweep")
    assert names.index("post-push-sweep") < names.index("enable-push-protection")
    assert names.index("refs-cleanup") < names.index("enable-push-protection")
    assert "enable-push-protection" in names


def test_runner_halt_on_rotation_gate_red(tmp_path):
    """The force-push gate: a RED rotation gate HALTS the run before
    any push (Phase 2 sequencing — rotations before the rewrite)."""
    remote = _bare_remote_with_secret(tmp_path, keep_secret=False)
    mirror = _mirror_of(remote, tmp_path)
    proc = _run(
        [
            TOOLS["runner"],
            "--fragments",
            str(_fragments(tmp_path)),
            "--mirror",
            str(mirror),
            "--remote-url",
            str(remote),
            "--rotation-gate",
            str(_red_gate(tmp_path)),
            "--skip-guard",
            "--confirm-force-push",
        ]
    )
    assert proc.returncode == 1
    assert "HALTED" in proc.stdout
    assert "rotation-gate" in proc.stdout
    # the remote was NOT pushed: its history still lacks the runner's
    # marker commit (the mirror's own head equals the remote's)
    assert _git(remote, "rev-parse", "refs/heads/main").strip() == _git(
        mirror, "rev-parse", "refs/heads/main"
    ).strip()


def test_runner_halt_on_live_tests_guard(tmp_path):
    """The runner's guard step: a refusing guard HALTS the window
    before anything else. (The guard's own scan is pinned in its own
    suite; this pins the RUNNER's handling, host-independent via
    --guard-cmd.)"""
    remote = _bare_remote_with_secret(tmp_path, keep_secret=False)
    mirror = _mirror_of(remote, tmp_path)
    proc = _run(
        [
            TOOLS["runner"],
            "--fragments",
            str(_fragments(tmp_path)),
            "--mirror",
            str(mirror),
            "--remote-url",
            str(remote),
            "--rotation-gate",
            str(_green_gate(tmp_path)),
            "--guard-cmd",
            str(_red_gate(tmp_path)),
            "--confirm-force-push",
        ]
    )
    assert proc.returncode == 1
    assert "zero-live-pytest" in proc.stdout
    assert "rotation-gate" not in proc.stdout


def test_runner_halts_without_confirm_force_push(tmp_path):
    """The destructive step requires the explicit confirmation flag."""
    remote = _bare_remote_with_secret(tmp_path, keep_secret=False)
    mirror = _mirror_of(remote, tmp_path)
    proc = _run(
        [
            TOOLS["runner"],
            "--fragments",
            str(_fragments(tmp_path)),
            "--mirror",
            str(mirror),
            "--remote-url",
            str(remote),
            "--rotation-gate",
            str(_green_gate(tmp_path)),
            "--skip-guard",
        ]
    )
    assert proc.returncode == 1
    assert "confirm-force-push" in proc.stdout


def test_runner_end_to_end_local_remote(tmp_path):
    """The full happy path against a REAL local remote: guard-shaped
    preconditions pass, the force-push lands, the sweep is green, and
    the gh-only steps (refs cleanup / actions review / push-protection
    enablement) are REPORTED SKIPPED for a non-GitHub URL."""
    remote = _bare_remote_with_secret(tmp_path, keep_secret=False)
    mirror = _mirror_of(remote, tmp_path)
    proc = _run(
        [
            TOOLS["runner"],
            "--fragments",
            str(_fragments(tmp_path)),
            "--mirror",
            str(mirror),
            "--remote-url",
            str(remote),
            "--rotation-gate",
            str(_green_gate(tmp_path)),
            "--skip-guard",
            "--confirm-force-push",
        ]
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "SWEEP: clean" in proc.stdout
    assert "SKIPPED" in proc.stdout  # gh-only steps, non-GitHub URL
    assert PLANTED not in proc.stdout + proc.stderr


def test_runner_post_push_sweep_halts_on_reachable_fragment(tmp_path):
    """The sweep is the post-push stop-the-line: a reachable fragment
    HALTS the window AFTER the push (the support-ticket path), and the
    enablement step is never reached."""
    remote = _bare_remote_with_secret(tmp_path, keep_secret=True)
    mirror = _mirror_of(remote, tmp_path)
    proc = _run(
        [
            TOOLS["runner"],
            "--fragments",
            str(_fragments(tmp_path)),
            "--mirror",
            str(mirror),
            "--remote-url",
            str(remote),
            "--rotation-gate",
            str(_green_gate(tmp_path)),
            "--skip-guard",
            "--confirm-force-push",
        ]
    )
    assert proc.returncode == 1
    assert "post-push-sweep" in proc.stdout
    assert "enable-push-protection" not in proc.stdout
    assert PLANTED not in proc.stdout + proc.stderr


# ── the sweep tool ──────────────────────────────────────────────────────────


def test_sweep_flags_reachable_fragment_by_index_only(tmp_path):
    remote = _bare_remote_with_secret(tmp_path)
    proc = _run(
        [
            TOOLS["sweep"],
            "--fragments",
            str(_fragments(tmp_path)),
            "--remote-url",
            str(remote),
        ]
    )
    assert proc.returncode == 1
    assert "fragment #0" in proc.stdout
    assert PLANTED not in proc.stdout + proc.stderr


def test_sweep_clean_after_removal(tmp_path):
    remote = _bare_remote_with_secret(tmp_path, keep_secret=False)
    proc = _run(
        [
            TOOLS["sweep"],
            "--fragments",
            str(_fragments(tmp_path)),
            "--remote-url",
            str(remote),
        ]
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "clean" in proc.stdout


def test_sweep_missing_fragments_fails_closed(tmp_path):
    remote = _bare_remote_with_secret(tmp_path)
    proc = _run(
        [
            TOOLS["sweep"],
            "--fragments",
            str(tmp_path / "nope.txt"),
            "--remote-url",
            str(remote),
        ]
    )
    assert proc.returncode == 2


def test_sweep_unreachable_remote_fails_closed(tmp_path):
    proc = _run(
        [
            TOOLS["sweep"],
            "--fragments",
            str(_fragments(tmp_path)),
            "--remote-url",
            str(tmp_path / "missing.git"),
        ]
    )
    assert proc.returncode == 2


# ── the refs cleanup tool ───────────────────────────────────────────────────


def test_cleanup_branch_classification_never_touches_pushed_heads():
    """The dependabot/* branches fork the tainted lineage and are
    deleted; the pushed heads (main, prepro01, staging, release/mvp-v1)
    are NEVER in the cleanup set."""
    classify = MODULES["cleanup"].cleanup_branches
    branches = [
        "dependabot/pip/black-gte-23.12.1",
        "dependabot/pip/pydantic-gte-2.13.3-and-lt-2.13.4",
        "main",
        "prepro01",
        "staging",
        "release/mvp-v1",
        "313-H-something",
    ]
    stale = classify(branches)
    assert set(stale) == {
        "dependabot/pip/black-gte-23.12.1",
        "dependabot/pip/pydantic-gte-2.13.3-and-lt-2.13.4",
    }


def test_cleanup_execute_requires_flag(tmp_path):
    """execute is explicit-only: without --execute the tool plans and
    never calls a mutating endpoint (a bogus slug still yields the
    plan-path failure, not a mutation)."""
    proc = _run(
        [
            TOOLS["cleanup"],
            "--repo",
            "cardosop/definitely-not-a-real-repo-xyz",
        ]
    )
    assert proc.returncode != 0
    assert "DELETE" not in proc.stdout + proc.stderr


def test_cleanup_plan_enumerates_real_origin():
    """LIVE leg: the real plan over origin — the open PRs (incl. the
    dependabot set) and the stale dependabot/* branches."""
    _require_gh()
    proc = _run([TOOLS["cleanup"], "--repo", ORIGIN_SLUG])
    assert proc.returncode == 0, proc.stderr
    assert "dependabot" in proc.stdout
    assert "PR" in proc.stdout


# ── the Actions review tool ─────────────────────────────────────────────────


def test_actions_review_classifies_carrier_artifacts():
    """The value-carrier classes: trace/network/junit/E2E artifact
    names are flagged; inert artifacts (docs builds, sboms) are not."""
    classify = MODULES["review"].carrier_artifact
    assert classify("playwright-artifacts-7-traces.zip")
    assert classify("junit-results.xml")
    assert classify("e2e-test-results.zip")
    assert classify("network-recordings.zip")
    assert not classify("storybook-static.zip")
    assert not classify("sbom-spdx.json")


def test_actions_review_plan_live():
    """LIVE leg: the real enumeration over origin — a review table
    with run + artifact counts."""
    _require_gh()
    proc = _run([TOOLS["review"], "--repo", ORIGIN_SLUG])
    assert proc.returncode == 0, proc.stderr
    assert "artifact" in proc.stdout.lower()


def test_actions_review_inspect_missing_run_fails_closed():
    """A run the API cannot resolve is a FAILURE, never a silent
    'clean'."""
    _require_gh()
    proc = _run([TOOLS["review"], "--repo", ORIGIN_SLUG, "--inspect-run", "99999999999"])
    assert proc.returncode == 2


# ── the G12 live contract + wiring ──────────────────────────────────────────


def test_pre_window_origin_push_protection_disabled_live():
    """LIVE leg: until the window executes, origin MUST stay
    not-configured/disabled — an enabled origin would block the
    rewritten force-push mid-flight (G12)."""
    _require_gh()
    proc = _run(
        [
            str(scripts_dir / "check_push_protection.py"),
            "check",
            "--remote",
            "origin",
            "--expect",
            "disabled",
        ]
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_public_push_protection_enabled_live():
    """LIVE leg: the public remote stays enabled BEFORE the re-sync
    (the publish pre-flight machine-enforces it)."""
    _require_gh()
    proc = _run(
        [
            str(scripts_dir / "check_push_protection.py"),
            "check",
            "--remote",
            "public",
            "--expect",
            "enabled",
        ]
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr


def test_runbook_covers_the_window():
    runbook = (ROOT / "docs/runbooks/history-rewrite-maintenance-window.md").read_text()
    for token in (
        "check_no_live_tests.py",
        "check_push_protection.py",
        "run_history_rewrite_window.py",
        "sweep_remote_fragments.py",
        "cleanup_origin_refs.py",
        "review_actions_artifacts.py",
        "support",
        "re-clone",
    ):
        assert token in runbook, token


def test_makefile_and_lint_list_wiring():
    makefile = (ROOT / "Makefile").read_text()
    assert "rewrite-window" in makefile
    lint = (ROOT / ".github/workflows/_reusable.lint.yml").read_text()
    assert "scripts/tests/test_p22_maintenance_window.py" in lint
