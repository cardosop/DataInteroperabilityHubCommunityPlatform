"""
Phase 227 Wave 4 (227.W4.4) — deploy.yml smoke-gate presence test.

The structureless residue smoke gate runs in CI as a kubectl-exec
step on staging.  We can't exercise the kubectl path itself in unit
tests, but we CAN guard against accidental removal by parsing
deploy.yml and asserting the canonical step + invocation are present.

This protects against the failure mode where someone refactors
deploy.yml, drops the step by mistake, and the structural-floor
enforcement starts silently regressing in production with no alarm
fired until a customer hits the bug.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
DEPLOY_YML = REPO_ROOT / ".github" / "workflows" / "deploy.yml"


@pytest.fixture(scope="module")
def deploy_yml_text() -> str:
    if not DEPLOY_YML.exists():
        pytest.skip(f"deploy.yml not found at {DEPLOY_YML} — repo layout drift?")
    return DEPLOY_YML.read_text(encoding="utf-8")


def test_w44_smoke_gate_step_is_present(deploy_yml_text):
    """The named step header is the canonical anchor humans grep for."""
    assert "Phase 227 W4.4 — structureless residue smoke gate" in deploy_yml_text


def test_w44_smoke_gate_invokes_renormalize_with_active_only(deploy_yml_text):
    """The canonical invocation pins all four required flags so that
    a partial refactor (e.g. dropping --include-active-only) doesn't
    silently widen the gate's scope and start failing on DRAFT residue."""
    # Allow whitespace + line continuations between the flags so YAML
    # reformatting doesn't break the test.
    pattern = re.compile(
        r"renormalize_contracts"
        r".*?--spec-version=3\.1\.0"
        r".*?--filter=structureless"
        r".*?--include-active-only"
        r".*?--dry-run"
        r".*?--output=count",
        re.DOTALL,
    )
    assert pattern.search(deploy_yml_text), (
        "deploy.yml must invoke renormalize_contracts with the four "
        "smoke-gate flags. Pin: --spec-version=3.1.0, "
        "--filter=structureless, --include-active-only, --dry-run, "
        "--output=count."
    )


def test_w44_smoke_gate_fails_on_nonzero_count(deploy_yml_text):
    """The gate must hard-fail (`exit 1`) on non-zero residue; a
    softer warning would let regressions ship to production."""
    # Look for the failure branch — count != "0" → error → exit 1.
    assert "exit 1" in deploy_yml_text and "W4.4 smoke gate FAILED" in deploy_yml_text, (
        "W4.4 smoke gate must hard-fail (exit 1) and emit a "
        "'W4.4 smoke gate FAILED' error annotation on non-zero "
        "structureless residue."
    )


def test_w44_smoke_gate_scoped_to_staging_environment(deploy_yml_text):
    """Production runs must NOT hard-block on this gate — staging
    catches regressions first, and blocking a prod rollout on a
    transient counter glitch would be the wrong tradeoff (we'd
    rather page).  Pin that the step's `if:` is staging-only."""
    # Find the smoke-gate step block and confirm the if-clause directly
    # under its name targets staging.
    block_match = re.search(
        r"- name: Phase 227 W4\.4.*?\n(.*?)\n      - name:",
        deploy_yml_text,
        re.DOTALL,
    )
    assert block_match, "could not locate the W4.4 smoke-gate step body"
    body = block_match.group(1)
    assert "needs.meta.outputs.environment == 'staging'" in body, (
        "W4.4 smoke gate must be scoped to staging via "
        "`if: needs.meta.outputs.environment == 'staging'`."
    )
