"""Contract pins for the Stripe test-key Makefile targets (pilot-readiness 4.3).

Holds the gate shape so it cannot regress:

- ``verify-stripe-test-keys`` — ADVISORY (SKIPs exit 0), the operator's
  wiring check;
- ``verify-stripe-test-keys-gate`` — ``--strict``: every missing key is a
  failure, so a declared-wired E2E run can never start with absent keys;
- ``test-frontend-e2e-billing-upgrade-stripe`` — the 4.3 live proof: the
  gate runs BEFORE the spec (a local operator cannot run the charged-path
  spec without verified test keys), the spec carries
  ``E2E_STRIPE_ENABLED=1``, and the spec path must point at the real
  file;
- all three targets are .PHONY-protected.
"""

import re
from pathlib import Path

MAKEFILE = Path(__file__).parent.parent.parent / "Makefile"
SPEC_PATH = "e2e/journeys/ta/JOURNEY-TA-BILLING-UPGRADE.spec.ts"


def _recipe(target: str) -> list[str]:
    text = MAKEFILE.read_text()
    match = re.search(
        rf"^{re.escape(target)}:.*\n((?:\t.*\n|\t.*\\\n\t.*\n)+)",
        text,
        re.MULTILINE,
    )
    assert match, f"target {target} not found in Makefile"
    return list(match.group(1).splitlines())


def test_targets_are_phony():
    text = MAKEFILE.read_text()
    phony_lines = [ln for ln in text.splitlines() if ln.startswith(".PHONY")]
    for target in (
        "verify-stripe-test-keys",
        "verify-stripe-test-keys-gate",
        "test-frontend-e2e-billing-upgrade-stripe",
    ):
        assert any(re.search(rf"(^|\s){target}(\s|$)", ln) for ln in phony_lines), (
            f"{target} is missing from .PHONY"
        )


def test_advisory_target_has_no_strict_flag():
    recipe = _recipe("verify-stripe-test-keys")
    assert any("verify_stripe_test_keys.py" in ln for ln in recipe)
    assert not any("--strict" in ln for ln in recipe), (
        "the advisory target must keep SKIP semantics"
    )


def test_gate_target_is_strict():
    recipe = _recipe("verify-stripe-test-keys-gate")
    assert any("--strict" in ln for ln in recipe), (
        "the gate must refuse missing keys"
    )


def test_e2e_target_runs_the_gate_before_the_spec():
    recipe = _recipe("test-frontend-e2e-billing-upgrade-stripe")
    gate_idx = next(
        i for i, ln in enumerate(recipe) if "verify_stripe_test_keys.py" in ln
    )
    spec_idx = next(i for i, ln in enumerate(recipe) if "JOURNEY-TA-BILLING-UPGRADE" in ln)
    assert gate_idx < spec_idx, (
        "the key gate must run BEFORE the spec — a charged-path run with "
        "absent/live keys must abort, not fail mid-run"
    )


def test_e2e_target_declares_stripe_enabled():
    recipe = _recipe("test-frontend-e2e-billing-upgrade-stripe")
    assert any("E2E_STRIPE_ENABLED=1" in ln for ln in recipe), (
        "the target exists to exercise the declared-wired branch — the flag "
        "must be set on the Playwright invocation"
    )


def test_e2e_target_spec_path_is_real():
    frontend_root = MAKEFILE.parent / "frontend"
    assert (frontend_root / SPEC_PATH).is_file(), (
        "the pinned spec path must exist on disk"
    )
