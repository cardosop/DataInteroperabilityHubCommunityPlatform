"""
P0-9 (close-oss-release-conditions, H-1) — secret-prevention hardening pins.

Three deliverables, each pinned at its weakest point:

1. **CI backstop verified** — the gitleaks-action backstop in ci.yml was
   already wired and is double-pinned (check_ci_arming.py invariant 6 +
   test_w1110_security_tooling_gates.py). The verification evidence lives
   in the P0-9 task record; this file adds the job-SHAPE pin so the scan
   cannot silently become advisory or shallow: the secret-scan job must
   fetch the full history and carry no continue-on-error.
2. **Rewrite verifier restored + gitleaks-over-history pass** — the W0.4
   verifier (deleted from the tree) is restored and extended with a
   gitleaks-over-history pass. The behavioral RED-first pins live in
   scripts/tests/test_verify_history_rewrite.py (REAL gitleaks binary,
   REAL fixture histories); this file anchors the restoration so the
   module cannot silently vanish again.
3. **G12 push-protection ordering** — machine-enforced on the public
   side: publish_public.sh refuses to sync while the public remote's
   secret-scanning push protection is not enabled. The origin-side
   ordering (pre-window guard OFF, enable AFTER the force-push) is the
   runbook contract, anchored here. The standing-posture live leg (W16)
   asserts the public repo reports push protection enabled right now.

No mocks anywhere: the unit legs exercise real parsing/state logic, the
source pins inspect the real files, and the live leg queries the real
GitHub API read-only.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(SCRIPTS.parent))

from envpolicy import skip_or_fail

_checker_spec = importlib.util.spec_from_file_location(
    "check_push_protection", SCRIPTS.parent / "check_push_protection.py"
)
assert _checker_spec is not None, "check_push_protection.py must load (P0-9)"
assert _checker_spec.loader is not None, "check_push_protection.py must carry a loader"
checker = importlib.util.module_from_spec(_checker_spec)
_checker_spec.loader.exec_module(checker)

_verifier_spec = importlib.util.spec_from_file_location(
    "verify_history_rewrite", SCRIPTS.parent / "verify_history_rewrite.py"
)
assert _verifier_spec is not None, "verify_history_rewrite.py must load (P0-9)"
assert _verifier_spec.loader is not None, "verify_history_rewrite.py must carry a loader"
verifier = importlib.util.module_from_spec(_verifier_spec)
_verifier_spec.loader.exec_module(verifier)

CI_WF = REPO_ROOT / ".github/workflows/ci.yml"
RUNBOOK = (
    REPO_ROOT
    / "openspec/changes/oss-release-remediation/history-rewrite-2026-10-06.md"
)
PUBLISH_PUBLIC = SCRIPTS.parent / "publish_public.sh"
PUBLISH_GATES = SCRIPTS.parent / "publish_gates.sh"
PUBLISH_SYNC = SCRIPTS.parent / "publish_sync.sh"
CHECKER_SCRIPT = SCRIPTS.parent / "check_push_protection.py"

# The public surface (G12 standing posture): readable by anyone, so the
# live leg below works in every CI context, authenticated or not.
PUBLIC_SLUG = "cardosop/DataInteroperabilityHubCommunityPlatform"


# ── 1. CI backstop job shape ──────────────────────────────────────────────


def test_secret_scan_job_fetches_full_history_and_is_blocking():
    """The gitleaks backstop scans the FULL history (fetch-depth 0) and
    cannot be silenced with continue-on-error — a shallow or advisory
    secret scan is the vacuity class the W0.2 scan found and fixed."""
    text = CI_WF.read_text(encoding="utf-8")
    jobs = text.split("jobs:", 1)[1]
    secret_scan = jobs.split("\n  traefik-security-lint:", 1)[0]
    assert "gitleaks/gitleaks-action" in secret_scan
    assert "fetch-depth: 0" in secret_scan
    assert "continue-on-error" not in secret_scan


# ── 2. Rewrite verifier restoration anchors ───────────────────────────────


def test_rewrite_verifier_carries_the_gitleaks_over_history_pass():
    assert callable(verifier.gitleaks_over_history), (
        "the restored verifier must expose the gitleaks-over-history pass"
    )
    source = (SCRIPTS.parent / "verify_history_rewrite.py").read_text(
        encoding="utf-8"
    )
    assert "--log-opts=--all" in source, (
        "the pass must scan EVERY commit reachable from any ref, not "
        "the working tree (a tree-only scan would miss exactly the "
        "committed-then-removed secret the rewrite must scrub)"
    )


# ── 3. G12 push-protection ordering — machine + runbook ───────────────────


def test_publish_sync_refuses_an_unprotected_public_remote():
    """publish_public.sh must hard-gate on public push protection BEFORE
    any push — and the gate runs on real publishes only (after the
    SKIP_PUSH dry-run exit, so offline dry-runs keep working)."""
    publish = PUBLISH_PUBLIC.read_text(encoding="utf-8")
    gates = PUBLISH_GATES.read_text(encoding="utf-8")
    assert "require_push_protection" in gates, (
        "publish_gates.sh must define the push-protection gate"
    )
    assert "scripts/check_push_protection.py check" in gates
    assert "--expect enabled" in gates
    skip_idx = publish.index('if [ "${SKIP_PUSH:-0}" = "1" ]; then')
    gate_idx = publish.index("require_push_protection")
    sync_idx = publish.index("sync_to_public")
    assert skip_idx < gate_idx < sync_idx, (
        "the gate must run on real publishes: after the SKIP_PUSH dry-run "
        "exit and before the sync invocation (P2-5: the pushes live in "
        "publish_sync.sh, invoked only after the gate) — never as a "
        "warn-only log line"
    )
    sync = PUBLISH_SYNC.read_text(encoding="utf-8")
    assert "git push" in sync, (
        "the pushes live in publish_sync.sh (the sourced sync) — invoked "
        "only via sync_to_public, which the gate precedes"
    )


def test_g12_ordering_is_the_runbook_contract():
    """The origin-after / public-before ordering (never during the
    window) is recorded in the Phase-2 runbook with the exact commands —
    the ordering is an execution contract, not prose in a task list."""
    runbook = RUNBOOK.read_text(encoding="utf-8")
    assert "Push-protection enablement (G12" in runbook
    assert "check --remote origin --expect disabled" in runbook, (
        "pre-window guard: origin must be proven OFF before the window"
    )
    assert "set --remote origin --state enabled" in runbook, (
        "origin enablement lands AFTER the force-push + post-push sweep"
    )
    assert "BEFORE the first re-sync" in runbook, (
        "public enablement precedes the first publish sync"
    )


# ── 4. check_push_protection.py — real logic, no network for unit legs ────


@pytest.mark.parametrize(
    ("url", "slug"),
    [
        ("git@github.com:cardosop/DataInteroperabilityHub.git",
         "cardosop/DataInteroperabilityHub"),
        ("https://github.com/cardosop/DataInteroperabilityHubCommunityPlatform",
         "cardosop/DataInteroperabilityHubCommunityPlatform"),
        ("ssh://git@github.com/o/r.git", "o/r"),
        ("https://github.com/o/r.git", "o/r"),
    ],
)
def test_repo_slug_parsing(url, slug):
    assert checker.repo_slug(url) == slug


def test_repo_slug_rejects_non_github_urls():
    with pytest.raises(ValueError, match="gitlab"):
        checker.repo_slug("https://gitlab.com/o/r.git")
    with pytest.raises(ValueError, match="not a GitHub"):
        checker.repo_slug("not-a-url")


def test_state_satisfied_fails_closed_on_enabled():
    assert checker.state_satisfied("enabled", "enabled") is True
    assert checker.state_satisfied("disabled", "enabled") is False
    assert checker.state_satisfied("", "enabled") is False, (
        "a never-configured repo must NOT satisfy --expect enabled"
    )


def test_state_satisfied_disabled_accepts_unconfigured():
    assert checker.state_satisfied("disabled", "disabled") is True
    assert checker.state_satisfied("", "disabled") is True, (
        "never-configured means nothing can block the window"
    )
    assert checker.state_satisfied("enabled", "disabled") is False


def test_checker_unknown_remote_fails_before_any_api_call(tmp_path):
    """A remote the checkout does not have is a hard failure (exit 2)
    with a message naming the remote — never a fallback to 'assume ok'."""
    tmp = tmp_path / "repo"
    tmp.mkdir()
    subprocess.run(["git", "-C", str(tmp), "init", "-q"], check=True)
    proc = subprocess.run(
        [
            sys.executable,
            str(CHECKER_SCRIPT),
            "--repo-root",
            str(tmp),
            "check",
            "--remote",
            "nope",
            "--expect",
            "enabled",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == checker.EXIT_FAILURE
    assert "nope" in proc.stderr


def test_checker_set_rejects_an_unknown_state():
    proc = subprocess.run(
        [
            sys.executable,
            str(CHECKER_SCRIPT),
            "set",
            "--repo",
            PUBLIC_SLUG,
            "--state",
            "bogus",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode != checker.EXIT_OK


# ── 5. Standing-posture live leg (W16-gated, read-only) ───────────────────


def test_public_push_protection_enabled_live():
    """The G12 public-side posture, queried from the REAL GitHub API:
    the public repo reports secret-scanning push protection enabled.
    Disabling it must fail this pin in every CI context."""
    gh_bin = subprocess.run(
        ["sh", "-c", "command -v gh"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()
    if not gh_bin:
        skip_or_fail(
            "gh CLI (the live leg queries the real GitHub API for the "
            "public repo's push-protection state)"
        )
    proc = subprocess.run(
        [
            sys.executable,
            str(CHECKER_SCRIPT),
            "check",
            "--repo",
            PUBLIC_SLUG,
            "--expect",
            "enabled",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == checker.EXIT_OK, proc.stdout + proc.stderr
