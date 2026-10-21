#!/usr/bin/env python3
"""
GATE-50 (oss-release-remediation W0.3) — the maintenance-window notice
contract checker.

The committed notice
(openspec/changes/oss-release-remediation/maintenance-window-2026-10-06.md)
must:

- exist and carry the mandated sections — the window scope, the peer
  notification record (the ListAgents check with its outcome + date),
  the zero-live-pytest guard evidence (a recorded ``guard exit=0`` run
  of scripts/check_no_live_tests.py), and the destructive steps the
  window gates;
- state the re-run rule (the guard is re-run immediately before W0.4);
- carry no TBD/TODO placeholders.

The notice is the coordination record for the destructive W0.4/W0.5
steps on the shared machine — a vacuous or deleted record would let the
rewrite proceed without the peer/guard checks.

Exit 0 when the notice satisfies the contract; 1 otherwise, each problem
named.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
NOTICE_DEFAULT = (
    _ROOT / "openspec/changes/oss-release-remediation/maintenance-window-2026-10-06.md"
)

REQUIRED_SECTIONS = (
    "## Window",
    "## Peer notification",
    "## Zero-live-pytest guard",
    "## Gated destructive steps",
)

_PLACEHOLDER = re.compile(r"\b(TBD|TODO|PLACEHOLDER|XXX)\b", re.I)


def check(notice_path: Path) -> list[str]:
    problems: list[str] = []
    if not notice_path.exists():
        return [f"maintenance-window notice missing: {notice_path}"]
    text = notice_path.read_text()

    for section in REQUIRED_SECTIONS:
        if section not in text:
            problems.append(f"missing mandated section {section!r}")

    guard_section = (
        text.split("## Zero-live-pytest guard", 1)[1].split("## ", 1)[0]
        if "## Zero-live-pytest guard" in text
        else ""
    )
    if "guard exit=0" not in guard_section:
        problems.append(
            "the Zero-live-pytest guard section does not record a "
            "`guard exit=0` run of scripts/check_no_live_tests.py"
        )
    if "scripts/check_no_live_tests.py" not in guard_section:
        problems.append(
            "the guard section does not name scripts/check_no_live_tests.py"
        )

    peer_section = (
        text.split("## Peer notification", 1)[1].split("## ", 1)[0]
        if "## Peer notification" in text
        else ""
    )
    if "ListAgents" not in peer_section:
        problems.append(
            "the Peer notification section does not record the ListAgents check"
        )
    if "2026-10-06" not in peer_section:
        problems.append("the Peer notification section does not carry the date")

    gated_section = (
        text.split("## Gated destructive steps", 1)[1].split("## ", 1)[0]
        if "## Gated destructive steps" in text
        else ""
    )
    if "re-run" not in gated_section:
        problems.append(
            "the Gated destructive steps section does not state the re-run rule "
            "(the guard is re-run immediately before W0.4)"
        )

    for word in sorted(set(_PLACEHOLDER.findall(text))):
        problems.append(f"unresolved placeholder {word!r} in the notice")

    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--notice", type=Path, default=NOTICE_DEFAULT)
    args = parser.parse_args()
    problems = check(args.notice)
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        print(f"GATE-50 FAILED: {len(problems)} problem(s)")
        sys.exit(1)
    print(f"GATE-50 PASSED: {args.notice} satisfies the maintenance-window contract")
    sys.exit(0)


if __name__ == "__main__":
    main()
