#!/usr/bin/env python3
"""
GATE-05 — No ``time.sleep()`` in test files.

Tests using ``time.sleep()`` are slow and flaky — use ``wait_for`` /
``poll.until`` / ``Event.wait`` / mock-time instead.

Allowed only with ``# noqa: sleep-needed`` and a documented reason.
Target: <20 total sleep calls (audit baseline from 312.6 audit).

Scans ``hub/``, ``tests/``, ``cli/tests/``, ``services/*/tests/``.

Usage:
    python scripts/check_time_sleep_in_tests.py
    python scripts/check_time_sleep_in_tests.py --max-allowed 20
    python scripts/check_time_sleep_in_tests.py --path hub/apps/assets/tests

Exit 0 if under the allowed maximum, 1 if exceeded.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
import tokenize
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Allow line:  # noqa: sleep-needed
_NOQA_RE = re.compile(r"#\s*noqa:\s*sleep-needed")


def _find_test_files(search_roots: list[str]) -> list[str]:
    files: list[str] = []
    for root in search_roots:
        p = Path(root)
        if not p.exists():
            continue
        for dirpath, dirnames, filenames in os.walk(p):
            dirnames[:] = [
                d
                for d in dirnames
                if d not in ("__pycache__", ".git", "migrations", ".venv", "venv", "node_modules")
            ]
            for fn in filenames:
                if not fn.endswith(".py"):
                    continue
                if fn.startswith("test_") or fn.endswith("_test.py") or fn == "tests.py":
                    files.append(os.path.join(dirpath, fn))
    return sorted(files)


def check_file(file_path: str) -> tuple[int, int]:
    """Return (total_sleep_calls, unannotated_sleep_calls).

    Token-based scan: only REAL ``time.sleep(...)`` call sites count.
    Comment / docstring / string-literal mentions are not calls (the
    pre-8.2 line-regex counted docstring mentions as calls — three false
    positives pushed the tree over the max). A syntax-error file counts
    nothing (a broken test file cannot be collected anyway).
    """
    total = 0
    unannotated = 0
    try:
        with open(file_path, encoding="utf-8") as fh:
            source = fh.read()
            lines = source.splitlines(keepends=True)
    except OSError:
        return 0, 0

    _artifacts = {
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.COMMENT,
        tokenize.ENCODING,
        tokenize.ENDMARKER,
    }
    try:
        raw_tokens = tokenize.generate_tokens(io.StringIO(source).readline)
        # TokenError raises at ITERATION time, not at the call — the
        # comprehension must live inside the try.
        tokens = [t for t in raw_tokens if t.type not in _artifacts]
    except (tokenize.TokenError, SyntaxError, IndentationError):
        return 0, 0

    for idx, tok in enumerate(tokens[:-3]):
        if tok.type != tokenize.NAME or tok.string != "time":
            continue
        nxt, nxt2, nxt3 = tokens[idx + 1], tokens[idx + 2], tokens[idx + 3]
        if not (
            nxt.type == tokenize.OP
            and nxt.string == "."
            and nxt2.type == tokenize.NAME
            and nxt2.string == "sleep"
            and nxt3.type == tokenize.OP
            and nxt3.string == "("
        ):
            continue
        if nxt.start[0] != tok.start[0] or nxt2.start[0] != tok.start[0]:
            continue  # the call spans lines — not a plain call site
        total += 1
        lineno = tok.start[0]
        line = lines[lineno - 1] if lineno - 1 < len(lines) else ""
        prev_line = lines[lineno - 2] if lineno - 2 >= 0 else ""
        # Check this line AND the previous line for the noqa annotation.
        if not (_NOQA_RE.search(line) or _NOQA_RE.search(prev_line)):
            unannotated += 1

    return total, unannotated


def main() -> None:
    parser = argparse.ArgumentParser(description="GATE-05: No time.sleep() in tests")
    parser.add_argument(
        "--max-allowed",
        type=int,
        default=20,
        help="Maximum allowed unannotated sleep calls (default: 20).",
    )
    parser.add_argument(
        "--list-all", action="store_true", help="List all sleep occurrences, not just violations."
    )
    parser.add_argument("--path", nargs="*", default=None)
    args = parser.parse_args()

    roots = (
        args.path
        if args.path
        else [
            str(REPO_ROOT / "hub"),
            str(REPO_ROOT / "tests"),
            str(REPO_ROOT / "cli/tests"),
            str(REPO_ROOT / "services"),
        ]
    )
    test_files = _find_test_files(roots)

    all_total = 0
    all_unannotated = 0
    violations: list[tuple[str, int]] = []

    for fp in test_files:
        total, unannotated = check_file(fp)
        all_total += total
        all_unannotated += unannotated
        if unannotated > 0:
            violations.append((fp, unannotated))

    print(
        f"GATE-05: Found {all_total} total time.sleep() calls "
        f"({all_unannotated} unannotated) in {len(test_files)} test files."
    )

    if all_unannotated > args.max_allowed:
        print(
            f"GATE-05: FAILED — {all_unannotated} unannotated sleep calls "
            f"exceeds max {args.max_allowed}."
        )
        for fp, count in sorted(violations, key=lambda x: -x[1])[:15]:
            rel = os.path.relpath(fp, REPO_ROOT)
            print(f"  {rel}  ({count} unannotated)")
        print("Add '# noqa: sleep-needed' with documented reason to allow.")
        sys.exit(1)

    print(f"GATE-05: PASSED — {all_unannotated} unannotated sleep calls (max {args.max_allowed}).")
    sys.exit(0)


if __name__ == "__main__":
    main()
