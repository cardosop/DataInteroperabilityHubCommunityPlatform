#!/usr/bin/env python3
"""
P1-3 (close-oss-release-conditions) — the history-content →
rotation-status mapping checker. THE FORCE-PUSH GATE (G8): Phase 2 (the
history rewrite force-push) is blocked while any credential CLASS
visible in the tainted history lacks dated dead-value evidence.

Inputs (both committed, never carrying secret values):

- the candidate enumeration from the real gitleaks-over-history pass
  (``docs/audits/gitleaks-history-candidates-2026-10-19.md`` — rule +
  path-category + finding count per class);
- the mapping table (``docs/audits/history-content-rotation-map-2026-10-19.md``)
  — one row per class with DATED rotation/retirement evidence.

Contract:

- every candidate class must have a map row (completeness over what the
  history actually contains);
- every MANDATED class must have a map row even when gitleaks never
  flagged it (the 6 GATE-51 surfaces, the ANTHROPIC token, the staging
  passwords, the postgres TLS certs, the test stack);
- every row must carry DATED evidence (``20XX-XX-XX``) and must NOT be
  PENDING — a class without dead-value evidence fails the gate by
  design (a gate that tolerates PENDING is the vacuous failure mode);
- no TBD/TODO/PLACEHOLDER placeholders anywhere.

Exit 0 when the mapping is complete and evidenced; 1 otherwise, each
problem named (class keys only — never values).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
CANDIDATES_DEFAULT = _ROOT / "docs/audits/gitleaks-history-candidates-2026-10-19.md"
MAP_DEFAULT = _ROOT / "docs/audits/history-content-rotation-map-2026-10-19.md"

# The classes the task mandates regardless of gitleaks coverage: the 6
# GATE-51 surfaces + the ANTHROPIC token + the W0.5-window rotations +
# the test stack.
MANDATED_CLASSES = (
    "gcp-sa-key",
    "aws-pair",
    "azure-sp-secret",
    "databricks-pat",
    "snowflake-pat",
    "stripe-test-key",
    "anthropic-auth-token",
    "staging-passwords",
    "postgres-certs",
    "test-stack",
)

_DATE = re.compile(r"\b20\d{2}-\d{2}-\d{2}\b")
_PENDING = re.compile(r"\bPENDING\b", re.I)
_PLACEHOLDER = re.compile(r"\b(TBD|TODO|PLACEHOLDER|XXX)\b", re.I)


def _table_rows(path: Path) -> list[tuple[str, str]]:
    """(cell0, cell1) pairs of each markdown table row (headers, comments,
    and separator rows skipped).

    Cells may carry the markdown pipe escape (``\\|`` — a class key like
    ``jwt|frontend/...`` must stay one column) and inline-code backticks;
    the split honors the escape and the unescape is undone afterwards so
    the parsed key matches the candidate key.
    """
    rows: list[tuple[str, str]] = []
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or not line.startswith("|"):
            continue
        cells = [
            cell.strip().strip("`").replace("\\|", "|")
            for cell in re.split(r"(?<!\\)\|", line.strip("|"))
        ]
        if len(cells) < 2:
            continue
        if set(cells[0]) <= {"-", ":", " "} and not cells[0].strip(" :-"):
            continue  # separator row
        if cells[0] in {"Rule", "Class", "Class key"}:
            continue  # header row
        rows.append((cells[0], cells[1]))
    return rows


def candidate_classes(path: Path) -> list[str]:
    """The class keys (``rule|category``) of the candidate enumeration."""
    classes: list[str] = []
    for rule, category in _table_rows(path):
        key = f"{rule}|{category}"
        if key not in classes:
            classes.append(key)
    return classes


def check(candidates_path: Path, map_path: Path) -> list[str]:
    problems: list[str] = []
    if not candidates_path.exists():
        return [f"candidate enumeration missing: {candidates_path}"]
    if not map_path.exists():
        return [f"rotation-status map missing: {map_path}"]

    map_rows = _table_rows(map_path)
    map_keys = [row[0] for row in map_rows]

    for key in candidate_classes(candidates_path):
        if key not in map_keys:
            problems.append(f"candidate class {key!r} has no mapping row")

    for mandated in MANDATED_CLASSES:
        if mandated not in map_keys:
            problems.append(f"mandated class {mandated!r} has no mapping row")

    for key, evidence in map_rows:
        if key not in candidate_classes(candidates_path) and key not in MANDATED_CLASSES:
            continue  # extra rows are advisory, not errors
        if _PENDING.search(evidence):
            problems.append(
                f"class {key!r} is PENDING — dead-value evidence required "
                "before Phase 2"
            )
        elif not _DATE.search(evidence):
            problems.append(f"class {key!r} carries no dated evidence")

    for word in sorted(set(_PLACEHOLDER.findall(map_path.read_text()))):
        problems.append(f"unresolved placeholder {word!r} in the map")

    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, default=CANDIDATES_DEFAULT)
    parser.add_argument("--map", type=Path, default=MAP_DEFAULT)
    args = parser.parse_args()
    problems = check(args.candidates, args.map)
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        print(f"G8 FORCE-PUSH GATE FAILED: {len(problems)} problem(s)")
        sys.exit(1)
    print(
        f"G8 FORCE-PUSH GATE PASSED: every history-content class in "
        f"{args.map} carries dated dead-value evidence"
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
