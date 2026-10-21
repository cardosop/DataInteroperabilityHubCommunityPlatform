#!/usr/bin/env python3
"""P0-11 (close-oss-release-conditions, F-3) — SDK ``: any`` typing ratchet.

Counts every any-typing site in ``sdk/js/src/**/*.ts`` and compares the
total against a committed baseline (``scripts/sdk_any_typing_baseline.json``).
Net-accounting (the check_mypy_debt_ratchet pattern): the count is TOTAL
sites, so a site moving between files cannot false-fail the gate. Growth
past the baseline fails; ``--update`` ratchets the floor down after a fix
wave (the P4-2 sweep runs on this contract).

Site shapes counted — ONE non-overlapping alternation, one site per
``any`` in a type position:

  ``: any`` / ``: any[]`` / return-type ``any[]`` · ``as any`` · ``<any>``
  (``Promise<any>``, ``Array<any>``, …)

The baseline records the LIVE site count (379 at P0-11 — the W10.5
triage's "139" was a line-grep undercount: a line carrying two sites
counted once, and generic ``<any>`` sites were missed entirely; the
gate measures the tree, not the prose).

Exit codes: 0 clean, 1 debt growth, 2 usage error (missing scope dir,
missing/unreadable baseline).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE = Path(__file__).resolve().parent / "sdk_any_typing_baseline.json"
SCOPE = "sdk/js/src"

ANY_SITE_RE = re.compile(
    r":\s*any(?:\s*\[\s*\])?\b"  # : any / : any[] / : any[]
    r"|\bas\s+any\b"             # x as any
    r"|<\s*any\s*>"              # Promise<any>, Array<any>, ...
)


def count_sites(path: Path) -> int:
    text = path.read_text(encoding="utf-8", errors="replace")
    return len(ANY_SITE_RE.findall(text))


def measure(root: Path) -> tuple[int, dict[str, int]]:
    """(total sites, per-file counts) over the scope dir."""
    src = root / SCOPE
    per_file: dict[str, int] = {}
    if src.is_dir():
        for path in sorted(src.rglob("*.ts")):
            count = count_sites(path)
            if count:
                per_file[str(path.relative_to(root))] = count
    return sum(per_file.values()), per_file


def load_baseline(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"{path}: expected a dict")
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument(
        "--update",
        action="store_true",
        help="ratchet the baseline down to the current count (after a fix wave)",
    )
    args = parser.parse_args(argv)

    if not (args.root / SCOPE).is_dir():
        print(f"ERROR: SDK scope dir missing: {args.root / SCOPE}", file=sys.stderr)
        return 2
    total, per_file = measure(args.root)

    if args.update:
        args.baseline.write_text(
            json.dumps({SCOPE: total}, indent=2) + "\n", encoding="utf-8"
        )
        print(f"SDK any-typing baseline ratcheted to {total} site(s)")
        return 0

    try:
        baseline = load_baseline(args.baseline)
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        print(f"ERROR: baseline unreadable — {exc}", file=sys.stderr)
        return 2
    floor = baseline.get(SCOPE)
    if not isinstance(floor, int):
        print(
            f"ERROR: baseline carries no integer count for {SCOPE!r}",
            file=sys.stderr,
        )
        return 2

    if total > floor:
        print(f"SDK any-typing debt grew: {total} site(s) > baseline {floor}")
        for path, count in sorted(
            per_file.items(), key=lambda item: -item[1]
        )[:5]:
            print(f"  {count:3d}  {path}")
        return 1
    print(f"SDK any-typing: {total} site(s) <= baseline {floor}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
