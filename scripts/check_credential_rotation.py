#!/usr/bin/env python3
"""
GATE-51 (oss-release-remediation W0.5) — the credential-rotation record
contract checker.

The committed record
(openspec/changes/oss-release-remediation/credential-rotation-2026-10-06.md)
must:

- exist and carry the mandated sections — the window re-check (guard +
  ListAgents evidence with the date), the named PRE/POST
  verify_test_stack_creds runs, the rotated surfaces, the Postgres TLS
  fingerprint evidence, and the U-gated console checklist;
- carry one ``### step: <surface>`` row per canonical surface, each with
  a ``**Status:**`` line — the gate is HONEST: any row that is not
  ``**Status:** ROTATED`` fails it (a gate that tolerates PENDING is the
  vacuous-gate failure mode this repo's Q.5 discipline exists to kill);
- record >=2 sha256 fingerprints for the regenerated TLS material;
- carry no TBD/TODO placeholders.

Exit 0 when the record satisfies the contract; 1 otherwise, each problem
named.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
RECORD_DEFAULT = (
    _ROOT / "openspec/changes/oss-release-remediation/credential-rotation-2026-10-06.md"
)

REQUIRED_SECTIONS = (
    "## Window re-check",
    "## Pre/post test-stack verification",
    "## Rotated surfaces",
    "## Postgres TLS certs",
    "## U-gated console checklist",
)

STEPS = (
    "gcp-sa-key",
    "aws-pair",
    "azure-sp-secret",
    "databricks-pat",
    "snowflake-pat",
    "stripe-test-key",
    "secret-key",
    "staging-passwords",
    "postgres-certs",
)

_PLACEHOLDER = re.compile(r"\b(TBD|TODO|PLACEHOLDER|XXX)\b", re.I)


def _sections(text: str, marker: str) -> dict[str, str]:
    """Split on line-start headings; marker is ``"## "`` or ``"### "``.

    Line-anchored on purpose — a plain substring split would also cut at
    the ``"## "`` inside a ``"### "`` heading (that bug cost the RED pass).
    """
    parts = re.split(rf"^{re.escape(marker)}", text, flags=re.M)
    result: dict[str, str] = {}
    for part in parts[1:]:
        heading, _, body = part.partition("\n")
        result[marker + heading.strip()] = body
    return result


def check(record_path: Path) -> list[str]:
    problems: list[str] = []
    if not record_path.exists():
        return [f"credential-rotation record missing: {record_path}"]
    text = record_path.read_text()
    top = _sections(text, "## ")

    for section in REQUIRED_SECTIONS:
        if section not in top:
            problems.append(f"missing mandated section {section!r}")

    window_section = top.get("## Window re-check", "")
    if "guard exit=0" not in window_section:
        problems.append(
            "the Window re-check section does not record a `guard exit=0` "
            "run of scripts/check_no_live_tests.py"
        )
    if "scripts/check_no_live_tests.py" not in window_section:
        problems.append("the Window re-check section does not name scripts/check_no_live_tests.py")
    if "ListAgents" not in window_section:
        problems.append("the Window re-check section does not record the ListAgents check")
    if "2026-10-06" not in window_section:
        problems.append("the Window re-check section does not carry the date")

    prepost_section = top.get("## Pre/post test-stack verification", "")
    if "verify_test_stack_creds" not in prepost_section:
        problems.append("the Pre/post section does not name scripts/verify_test_stack_creds.py")
    if "PRE" not in prepost_section or "POST" not in prepost_section:
        problems.append("the Pre/post section does not record the named PRE/POST runs")

    step_bodies = _sections(top.get("## Rotated surfaces", ""), "### ")
    for step in STEPS:
        step_section = step_bodies.get(f"### step: {step}", "")
        if not step_section:
            problems.append(f"missing rotated-surface step {step!r}")
            continue
        if "**Status:**" not in step_section:
            problems.append(f"step {step!r} has no **Status:** line")
            continue
        if "**Status:** ROTATED" not in step_section:
            found = re.search(r"\*\*Status:\*\*\s*(\S+)", step_section)
            status = found.group(1) if found else "missing"
            problems.append(
                f"step {step!r} has status {status!r} — the honest gate "
                "blocks until every surface is ROTATED"
            )

    certs_section = top.get("## Postgres TLS certs", "")
    if len(re.findall(r"sha256", certs_section)) < 2:
        problems.append(
            "the Postgres TLS certs section does not record the old/new sha256 fingerprints"
        )

    for word in sorted(set(_PLACEHOLDER.findall(text))):
        problems.append(f"unresolved placeholder {word!r} in the record")

    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, default=RECORD_DEFAULT)
    args = parser.parse_args()
    problems = check(args.record)
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        print(f"GATE-51 FAILED: {len(problems)} problem(s)")
        sys.exit(1)
    print(f"GATE-51 PASSED: {args.record} satisfies the rotation-record contract")
    sys.exit(0)


if __name__ == "__main__":
    main()
