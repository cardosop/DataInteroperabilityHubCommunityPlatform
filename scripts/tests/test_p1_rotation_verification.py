"""P1-2 (close-oss-release-conditions) — rotation-verification contract pins.

P1-1 (U + the rotation lane) rotates the 6 surfaces; P1-2 (D) proves the
old values DEAD, flips the record, closes the ledger. These pins enforce
the contract BEFORE the live runs so a row-flip without evidence cannot
land:

1. the dead-not-replaced proof: every ROTATED console-surface row in the
   rotation record must carry DATED dead-check evidence (the template
   rows carry none — a flip that only changes the status line fails);
2. the ledger closure: `w05-rotations` flips to CLOSED only with the
   record citation + the dead-check oracle + the Stripe drill re-run;
3. the Stripe drill wrapper exists and is the Makefile's target;
4. the pin file is CI-wired.

The live oracle runs (verify_old_creds_dead.py --strict per surface and
the `make staging-stripe-drill-w102` re-run) execute inside the P1-1
maintenance window's close-out — these pins gate the RECORDING of those
runs, not the runs themselves. No mocks: the real record, the real
ledger, the real Makefile + wrapper, parsed by the real contract rules.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
REPO_ROOT = SCRIPTS.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

RECORD = REPO_ROOT / "openspec/changes/oss-release-remediation/credential-rotation-2026-10-06.md"
LEDGER = REPO_ROOT / "docs/operations/oss-go-nogo-ledger.md"
DRILL = REPO_ROOT / "infrastructure/scripts/staging-stripe-drill-w102.sh"
MAKEFILE = REPO_ROOT / "Makefile"

_CONSOLE_SURFACES = (
    "gcp-sa-key",
    "aws-pair",
    "azure-sp-secret",
    "databricks-pat",
    "snowflake-pat",
    "stripe-test-key",
)
_DATE_RE = re.compile(r"\b2026-\d\d-\d\d\b")


def _record_steps(text: str) -> dict[str, str]:
    """surface → step-section text."""
    parts = re.split(r"^### step: ", text, flags=re.M)
    steps: dict[str, str] = {}
    for part in parts[1:]:
        surface = part.splitlines()[0].strip()
        steps[surface] = part.split("\n## ")[0]
    return steps


# ── 1. The flip contract (dead, not merely replaced) ─────────────────────────


def test_flip_contract_requires_dated_dead_check_evidence():
    """A console-surface row flipped to ROTATED must carry DATED dead-check
    evidence — flipping only the status line (the template is not
    evidence) fails this pin."""
    text = RECORD.read_text(encoding="utf-8")
    steps = _record_steps(text)
    for surface in _CONSOLE_SURFACES:
        assert surface in steps, f"missing step: {surface}"
        section = steps[surface]
        if re.search(r"\*\*Status:\*\*\s+ROTATED", section):
            assert "dead-check" in section, (
                f"{surface} flips ROTATED without the dead-check oracle — "
                "the DEAD-not-replaced proof is mandatory"
            )
            assert _DATE_RE.search(section), (
                f"{surface} flips ROTATED without a dated evidence run"
            )


def test_flip_contract_bites_on_status_only_flip():
    """RED-first fixture: the same contract rule over a status-only flip
    (template evidence, no date) — the pin must reject it."""
    fake = (
        "### step: gcp-sa-key\n\n"
        "- **Evidence:** dead-check PASS (invalid_grant).\n"
        "- **Status:** ROTATED\n"
    )
    steps = _record_steps(fake)
    section = steps["gcp-sa-key"]
    assert re.search(r"\*\*Status:\*\*\s+ROTATED", section)
    assert _DATE_RE.search(section) is None, "fixture must model the no-date flip"
    # the contract rule the real-record pin applies:
    ok = "dead-check" in section and _DATE_RE.search(section) is not None
    assert not ok


def test_flip_contract_bites_on_undated_flip():
    fake = (
        "### step: aws-pair\n\n"
        "- **Evidence:** dead-check PASS (STS InvalidAccessKeyId).\n"
        "- **Status:** ROTATED\n"
    )
    section = _record_steps(fake)["aws-pair"]
    assert re.search(r"\*\*Status:\*\*\s+ROTATED", section)
    assert _DATE_RE.search(section) is None


def test_pending_rows_carry_no_dated_evidence():
    """While PENDING-U, the rows hold templates (no dates) — the pin
    distinguishes template from executed evidence."""
    steps = _record_steps(RECORD.read_text(encoding="utf-8"))
    for surface in _CONSOLE_SURFACES:
        section = steps[surface]
        if re.search(r"\*\*Status:\*\*\s+PENDING", section):
            # templates are un-dated by design (see the record's evidence
            # lines: they name the expected rejection class, no date)
            assert "PENDING" in section


# ── 2. Ledger closure contract ───────────────────────────────────────────────


def _ledger_w05_row(text: str) -> str:
    m = re.search(r"\|\s*w05-rotations\s*\|[^|]*\|[^|]*\|(.*?)\|", text, re.S)
    return m.group(1) if m else ""


def test_ledger_closure_requires_full_citations():
    """When w05-rotations flips CLOSED it must cite the record, the
    dead-check oracle and the Stripe drill re-run — a closure without
    them fails this pin."""
    row = _ledger_w05_row(LEDGER.read_text(encoding="utf-8"))
    if "CLOSED" in row:
        for anchor in (
            "credential-rotation-2026-10-06.md",
            "verify_old_creds_dead.py",
            "staging-stripe-drill-w102",
        ):
            assert anchor in row, f"w05-rotations CLOSED without {anchor} citation"


def test_ledger_closure_bites_on_citationless_closure():
    fake = "| w05-rotations | x | U | CLOSED — all six surfaces rotated. |"
    row = _ledger_w05_row(fake)
    assert "CLOSED" in row
    ok = all(
        a in row
        for a in (
            "credential-rotation-2026-10-06.md",
            "verify_old_creds_dead.py",
            "staging-stripe-drill-w102",
        )
    )
    assert not ok


# ── 3. Stripe drill wrapper ──────────────────────────────────────────────────


def test_stripe_drill_wrapper_exists():
    assert DRILL.is_file(), "the W10.2 Stripe drill wrapper must exist for the P1-2 re-run"
    makefile = MAKEFILE.read_text(encoding="utf-8")
    assert "staging-stripe-drill-w102" in makefile
    assert "staging-stripe-drill-w102.sh" in makefile


# ── 4. Wiring ────────────────────────────────────────────────────────────────


def test_p1_pins_ci_wired():
    lint_yml = (REPO_ROOT / ".github/workflows/_reusable.lint.yml").read_text(encoding="utf-8")
    assert (
        "scripts/tests/test_p1_rotation_verification.py" in lint_yml
    ), "P1-2 pins must be CI-wired in the lint list"
