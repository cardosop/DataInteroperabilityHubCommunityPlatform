#!/usr/bin/env python3
"""
Phase 227 Wave 1 (227.L1.6) — SSRF lint rule.

Why this exists
---------------
The Phase 227 root-cause investigation found that the previous ODPS
contractURL plumbing was vulnerable to direct ``requests.get`` calls in
normaliser code paths. SSRF protection lives in
:mod:`hub.apps.contracts.ref_resolver` (which delegates to
:mod:`hub.apps.webhooks.ssrf_guard`); any normaliser that bypasses
``RefResolver.resolve()`` and calls ``requests.get`` / ``httpx.get`` /
``urllib.request.urlopen`` directly defeats the SSRF allowlist.

This script greps the normaliser tree for the prohibited symbols and
fails the build when any are found.

Usage
-----
    python scripts/lint_no_direct_http_in_normalizers.py

Exit codes
----------
* ``0`` — clean. No prohibited HTTP calls in normaliser code.
* ``1`` — one or more prohibited HTTP calls found.

CI wiring
---------
Invoked from ``code-quality.yml`` as a fast check (~50ms). Add new
allowed paths to ``ALLOWED_PATHS`` only after architectural review.
"""
from __future__ import annotations

import ast
import re
import sys
import tokenize
from pathlib import Path
from typing import Iterable, List, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Paths under inspection — recursively scanned.
TARGET_DIRS = [
    PROJECT_ROOT / "hub" / "apps" / "contracts" / "normalization",
]

# Files / sub-paths that are explicitly allowed to call requests/httpx
# directly. The ONLY currently-permitted path is the RefResolver itself,
# which centralises SSRF defence — every other caller MUST go through
# ``RefResolver.resolve()``.
ALLOWED_PATHS: List[Path] = [
    PROJECT_ROOT / "hub" / "apps" / "contracts" / "ref_resolver.py",
]

# Patterns flagged as SSRF-unsafe in normaliser code paths. Each tuple
# is (regex, human-readable description). Patterns are conservative —
# they target the call surface, not arbitrary string mentions.
PROHIBITED_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\brequests\.(get|post|put|delete|patch|head|request)\b"),
        "direct `requests.*` call — use RefResolver.resolve() instead",
    ),
    (
        re.compile(r"\bhttpx\.(get|post|put|delete|patch|head|request|stream)\b"),
        "direct `httpx.*` call — use RefResolver.resolve() instead",
    ),
    (
        re.compile(r"\burllib\.request\.(urlopen|Request)\b"),
        "direct urllib call — use RefResolver.resolve() instead",
    ),
    (
        re.compile(r"\baiohttp\.(ClientSession|request)\b"),
        "direct aiohttp call — use RefResolver.resolve() instead",
    ),
    (
        re.compile(r"\burlopen\("),
        "direct urlopen() call — use RefResolver.resolve() instead",
    ),
]


def _iter_python_files(roots: Iterable[Path]) -> Iterable[Path]:
    """Yield every .py file under each root, deterministically ordered."""
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.py")):
            if path in seen:
                continue
            seen.add(path)
            yield path


def _is_allowed(path: Path) -> bool:
    """True iff the file is on the allow-list."""
    return any(path == allowed for allowed in ALLOWED_PATHS)


def _string_and_comment_lines(text: str) -> Set[int]:
    """Return line numbers occupied by string-literal or comment tokens.

    Includes triple-quoted docstrings. We skip these so the lint can
    discuss `requests.get` in narrative without false positives.
    """
    skip: Set[int] = set()
    try:
        tokens = list(tokenize.generate_tokens(iter(text.splitlines(keepends=True)).__next__))
    except (tokenize.TokenizeError, IndentationError, SyntaxError):
        # Fall back: treat unparseable files as fully scannable, so a
        # broken file fails the lint visibly rather than silently.
        return skip
    for tok in tokens:
        if tok.type in (tokenize.STRING, tokenize.COMMENT):
            start_line, _ = tok.start
            end_line, _ = tok.end
            for n in range(start_line, end_line + 1):
                skip.add(n)
    return skip


def lint() -> int:
    violations: List[Tuple[Path, int, str, str]] = []

    for path in _iter_python_files(TARGET_DIRS):
        if _is_allowed(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"warn: could not read {path}: {exc}", file=sys.stderr)
            continue
        # Quick pre-check: parseable file? (a syntax error would be a
        # different bug; flag it but don't claim SSRF violation)
        try:
            ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            print(f"warn: {path} has a syntax error: {exc}", file=sys.stderr)
            continue
        skip_lines = _string_and_comment_lines(text)
        for line_no, line in enumerate(text.splitlines(), start=1):
            if line_no in skip_lines:
                continue
            for pattern, description in PROHIBITED_PATTERNS:
                if pattern.search(line):
                    violations.append(
                        (path.relative_to(PROJECT_ROOT), line_no, line.rstrip(), description)
                    )

    if not violations:
        print(
            "OK: no direct HTTP calls in normaliser code paths "
            f"({len(list(_iter_python_files(TARGET_DIRS)))} files scanned)."
        )
        return 0

    print("FAIL: prohibited direct HTTP calls in normaliser code paths.")
    print()
    print(
        "Phase 227 Wave 1 mandates that all external URL fetches go "
        "through `RefResolver.resolve()`, which enforces the SSRF "
        "allowlist (`hub.apps.webhooks.ssrf_guard.is_safe_url`). "
        "Direct `requests.get` / `httpx.get` / `urllib.request.urlopen` "
        "calls bypass the allowlist and re-introduce the SSRF risk we "
        "fixed in Wave 0."
    )
    print()
    for path, line_no, source, description in violations:
        print(f"  {path}:{line_no}: {description}")
        print(f"      {source!r}")
    print()
    print(
        "If you genuinely need a direct HTTP call (e.g., a new central "
        "fetcher), add the file path to ALLOWED_PATHS in "
        "scripts/lint_no_direct_http_in_normalizers.py and document the "
        "review in the PR description."
    )
    return 1


if __name__ == "__main__":
    sys.exit(lint())
