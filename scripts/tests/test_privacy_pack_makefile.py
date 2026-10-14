"""
Contract tests for the privacy-pack Makefile wiring (pilot-readiness 3.3).

Pins the pack-run shape so it cannot regress:

- ``verify-privacy-pack`` is the ADVISORY run (an unreachable API is a
  SKIP, exit 0) — the operator's rehearsal check;
- ``verify-privacy-pack-gate`` adds ``--strict`` — a SKIP becomes a
  failure (W16 semantics: CI raises, local operators get the gate);
- GATE-46 (``check_privacy_pack.py``) is wired into ``quality-gates``
  right after the other pilot-record gates;
- both targets are .PHONY-protected.
"""

import re
from pathlib import Path

MAKEFILE = Path(__file__).parent.parent.parent / "Makefile"


def _recipe(target: str) -> list[str]:
    text = MAKEFILE.read_text()
    match = re.search(
        rf"^{re.escape(target)}:.*\n((?:\t.*\n|\t.*\\\n\t.*\n)+)",
        text,
        re.MULTILINE,
    )
    assert match, f"target {target} not found in Makefile"
    return list(match.group(1).splitlines())


def _quality_gates_recipe() -> list[str]:
    text = MAKEFILE.read_text()
    match = re.search(r"^quality-gates:.*\n((?:\t.*\n)+)", text, re.MULTILINE)
    assert match, "quality-gates target not found in Makefile"
    return list(match.group(1).splitlines())


def test_targets_are_phony():
    text = MAKEFILE.read_text()
    phony_lines = [ln for ln in text.splitlines() if ln.startswith(".PHONY")]
    for target in ("verify-privacy-pack", "verify-privacy-pack-gate"):
        assert any(re.search(rf"(^|\s){target}(\s|$)", ln) for ln in phony_lines), (
            f"{target} is missing from .PHONY"
        )


def test_advisory_target_runs_runner_without_strict():
    joined = "\n".join(_recipe("verify-privacy-pack"))
    assert "verify_privacy_pack.py" in joined
    assert "--strict" not in joined, (
        "the advisory run must not turn SKIPs into failures"
    )


def test_gate_target_is_strict():
    joined = "\n".join(_recipe("verify-privacy-pack-gate"))
    assert "verify_privacy_pack.py" in joined
    assert "--strict" in joined, "the gate must treat a SKIP as a failure"


def test_gate46_wired_into_quality_gates():
    recipe = _quality_gates_recipe()
    joined = "\n".join(recipe)
    assert "check_privacy_pack.py" in joined, "GATE-46 must run in quality-gates"
    gate45 = next(i for i, ln in enumerate(recipe) if "check_pilot_scope.py" in ln)
    gate46 = next(i for i, ln in enumerate(recipe) if "check_privacy_pack.py" in ln)
    assert gate45 < gate46, "the privacy-pack gate runs after the scope-record gate"
