#!/usr/bin/env python3
"""
GATE-53 (oss-release-remediation W1.0) — the IdP-JWKS decision-note
contract checker.

The signed decision note (docs/audits/idp-jwks-verification-2026-10-07.md)
is the W1.0 (S3) evidence — the D4 precondition check. It must:

- exist and carry the mandated sections — Outcome, Live verification
  evidence, D4 consequence, Sign-off;
- record exactly one outcome, ``JWKS_EXPOSED`` or ``JWKS_NOT_EXPOSED``;
- keep the D4 consequence MATCHING the outcome:
  * JWKS_EXPOSED — ``**D4 proceeds on the JWKS-verification plan**``
    and ``**No cert-pinned fallback**`` (the fallback decision is NOT
    taken, D4 is not re-scoped);
  * JWKS_NOT_EXPOSED — the POSITIVE ``**Cert-pinned fallback:**`` and
    ``**D4 re-scope:**`` markers (the fallback decision + re-scope
    must be recorded, not negated);
- name the live check tool (scripts/check_idp_jwks.py), record HTTP 200
  on BOTH legs (discovery + JWKS), and count usable signing keys;
- carry the D + Meshant (U) sign-off rows with dates;
- carry no TBD/TODO placeholders.

A vacuous or deleted record would let W1.5 proceed on an unverified
precondition — or silently drop the fallback decision the D4 re-scope
path requires.

Exit 0 when the note satisfies the contract; 1 otherwise, each problem
named.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
NOTE_DEFAULT = _ROOT / "docs/audits/idp-jwks-verification-2026-10-07.md"
VERIFICATION_DATE = "2026-10-07"

REQUIRED_SECTIONS = (
    "## Outcome",
    "## Live verification evidence",
    "## D4 consequence",
    "## Sign-off",
)

_VALID_OUTCOMES = ("JWKS_EXPOSED", "JWKS_NOT_EXPOSED")
_OUTCOME = re.compile(r"\*\*Outcome:\*\*\s*(JWKS\S*)")
_EXPOSED_MARKERS = (
    "**D4 proceeds on the JWKS-verification plan**",
    "**No cert-pinned fallback**",
)
_NOT_EXPOSED_MARKERS = (
    "**Cert-pinned fallback:**",
    "**D4 re-scope:**",
)
_CHECK_TOOL = "scripts/check_idp_jwks.py"
_LIVE_TEST = "test_sso_idp_metadata.py"
_USABLE_KEYS = re.compile(r"(\d+)\s+usable signing key")
_PLACEHOLDER = re.compile(r"\b(TBD|TODO|PLACEHOLDER|XXX)\b", re.I)


def _section(text: str, heading: str) -> str:
    if heading not in text:
        return ""
    return text.split(heading, 1)[1].split("## ", 1)[0]


def check(note_path: Path) -> list[str]:
    problems: list[str] = []
    if not note_path.exists():
        return [f"IdP-JWKS decision note missing: {note_path}"]
    text = note_path.read_text()

    for section in REQUIRED_SECTIONS:
        if section not in text:
            problems.append(f"missing mandated section {section!r}")

    if VERIFICATION_DATE not in text:
        problems.append(
            f"the note does not record the verification date {VERIFICATION_DATE}"
        )

    outcome_match = _OUTCOME.search(text)
    if not outcome_match:
        problems.append("no **Outcome:** JWKS_EXPOSED / JWKS_NOT_EXPOSED recorded")
    else:
        outcome = outcome_match.group(1)
        if outcome not in _VALID_OUTCOMES:
            problems.append(
                f"outcome {outcome!r} is not one of {', '.join(_VALID_OUTCOMES)}"
            )
        d4 = _section(text, "## D4 consequence")
        if outcome == "JWKS_EXPOSED":
            for marker in _EXPOSED_MARKERS:
                if marker not in d4:
                    problems.append(
                        f"JWKS_EXPOSED requires the {marker} marker in the "
                        "D4 consequence section"
                    )
        else:
            for marker in _NOT_EXPOSED_MARKERS:
                if marker not in d4:
                    problems.append(
                        f"JWKS_NOT_EXPOSED requires the {marker} marker in the "
                        "D4 consequence section (the fallback decision + "
                        "re-scope must be recorded)"
                    )

    evidence = _section(text, "## Live verification evidence")
    if _CHECK_TOOL not in evidence:
        problems.append(f"the evidence does not name the live check tool {_CHECK_TOOL}")
    if _LIVE_TEST not in evidence:
        problems.append(f"the evidence does not name the W16 live tests {_LIVE_TEST}")
    if evidence.count("HTTP 200") < 2:
        problems.append(
            "the evidence does not record HTTP 200 on both legs " "(discovery + JWKS)"
        )
    usable = _USABLE_KEYS.search(evidence)
    if not usable or int(usable.group(1)) < 1:
        problems.append("the evidence does not record at least 1 usable signing key")

    signoff = _section(text, "## Sign-off")
    for party in ("| D (engineering)", "| Meshant (U)"):
        if party not in signoff:
            problems.append(f"the Sign-off section is missing the {party} row")
    if "signed" not in signoff:
        problems.append("the Sign-off section carries no signed status")

    for word in sorted(set(_PLACEHOLDER.findall(text))):
        problems.append(f"unresolved placeholder {word!r} in the note")

    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--note", type=Path, default=NOTE_DEFAULT)
    args = parser.parse_args()
    problems = check(args.note)
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        print(f"GATE-53 FAILED: {len(problems)} problem(s)")
        sys.exit(1)
    print(f"GATE-53 PASSED: {args.note} satisfies the IdP-JWKS decision-note contract")
    sys.exit(0)


if __name__ == "__main__":
    main()
