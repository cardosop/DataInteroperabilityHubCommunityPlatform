#!/usr/bin/env python3
"""
Phase 250.0.13 / D250.14 — CI gate enforcing that every error code emitted
by the Hub API is documented in ``docs/api/error-codes.md``.

Why this exists
---------------
Error codes are part of the public API contract. SDKs, dashboards, and
client-side error-handling depend on stability. Without this gate, a
developer can introduce a new error code in a view without telling the
client team — they discover it in production via a customer ticket.

This script:

1. Scans ``hub/apps/**/*.py`` for code-emission patterns:

   * ``"code": "SOME_CODE"`` (string-literal in a dict — most common in DRF Response bodies)
   * ``code="SOME_CODE"`` (kwarg in error helpers)

2. Extracts the ``SOME_CODE`` literals (uppercase + underscore + digits).

3. Cross-references against the ``| CODE_NAME |`` table cells in
   ``docs/api/error-codes.md``.

4. Exits non-zero if any emitted code is missing from the catalogue,
   printing the offence in ``file:line: <message>`` format for editor +
   CI annotation.

Exemptions
----------
Lines with ``# pragma: error-code-internal`` are skipped (for codes that
are explicitly internal — never emitted on the API surface).

Usage
-----
::

    python scripts/check_error_codes_catalogue.py [path...]

When invoked with no args, scans the canonical paths.

Exit codes
----------
* 0 — every emitted code appears in the catalogue.
* 1 — at least one offence; details printed to stdout.
* 2 — environment misconfigured (catalogue file missing).
"""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

_CATALOGUE_PATH = Path("docs/api/error-codes.md")

# Canonical scan roots: production Python code only. Tests + migrations
# are excluded — tests assert on existing codes; migrations don't emit.
_DEFAULT_SCAN_ROOTS: tuple[str, ...] = ("hub/apps",)
_EXCLUDE_DIR_PARTS: frozenset[str] = frozenset(
    {
        "__pycache__",
        "tests",
        "test",
        "migrations",
        ".tox",
        ".venv",
        "venv",
        "node_modules",
    }
)

# Code emission patterns. Each yields a single capture group with the code.
# We deliberately don't try to evaluate Python — we extract candidate
# uppercase identifiers from string-literal contexts, then keep only ones
# that match the SCREAMING_SNAKE_CASE format.
_PATTERNS: tuple[re.Pattern[str], ...] = (
    # "code": "SOME_CODE"   in a JSON / dict literal
    re.compile(r'"code"\s*:\s*"([A-Z][A-Z0-9_]+)"'),
    # 'code': 'SOME_CODE'   in a Python dict literal
    re.compile(r"'code'\s*:\s*'([A-Z][A-Z0-9_]+)'"),
    # code="SOME_CODE"      kwarg
    re.compile(r"\bcode\s*=\s*[\"']([A-Z][A-Z0-9_]+)[\"']"),
    # error_code="SOME_CODE" kwarg
    re.compile(r"\berror_code\s*=\s*[\"']([A-Z][A-Z0-9_]+)[\"']"),
    # ErrorCode.SOME_CODE   enum reference
    re.compile(r"\bErrorCode\.([A-Z][A-Z0-9_]+)\b"),
)

_PRAGMA_INTERNAL = re.compile(r"#\s*pragma:\s*error-code-internal")
_TABLE_CODE_PATTERN = re.compile(r"^\|\s*`([A-Z][A-Z0-9_]+)`\s*\|")


@dataclass(frozen=True)
class Offence:
    file: str
    line: int
    code: str

    def render(self) -> str:
        return (
            f"{self.file}:{self.line}: E[ERROR-CODES-001] "
            f"error code {self.code!r} is emitted in source but is NOT "
            f"in docs/api/error-codes.md catalogue. Add a row per the "
            f"'Adding a new error code' procedure in that document."
        )


def _load_catalogue_codes(catalogue_path: Path) -> set[str]:
    if not catalogue_path.exists():
        print(
            f"ERROR: error-codes catalogue not found at {catalogue_path}",
            file=sys.stderr,
        )
        sys.exit(2)
    codes: set[str] = set()
    with catalogue_path.open(encoding="utf-8") as fh:
        for line in fh:
            match = _TABLE_CODE_PATTERN.match(line)
            if match:
                codes.add(match.group(1))
    return codes


def _iter_python_files(roots: Iterable[str]) -> Iterable[Path]:
    for root in roots:
        root_path = Path(root)
        if not root_path.exists():
            continue
        if root_path.is_file():
            yield root_path
            continue
        for path in root_path.rglob("*.py"):
            if any(part in _EXCLUDE_DIR_PARTS for part in path.parts):
                continue
            yield path


def _extract_emitted_codes(path: Path) -> Iterable[tuple[int, str]]:
    """Yield ``(line_number, code)`` tuples for each emission found."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    for line_no, line in enumerate(text.splitlines(), start=1):
        if _PRAGMA_INTERNAL.search(line):
            continue
        for pattern in _PATTERNS:
            for match in pattern.finditer(line):
                yield line_no, match.group(1)


def main(argv: list[str]) -> int:
    paths = argv[1:] or list(_DEFAULT_SCAN_ROOTS)

    catalogued = _load_catalogue_codes(_CATALOGUE_PATH)
    if not catalogued:
        print(
            f"WARN: catalogue at {_CATALOGUE_PATH} loaded but no "
            "rows extracted. Verify the table format matches the "
            "_TABLE_CODE_PATTERN regex.",
            file=sys.stderr,
        )

    offences: list[Offence] = []
    for py_file in _iter_python_files(paths):
        for line_no, code in _extract_emitted_codes(py_file):
            if code in catalogued:
                continue
            offences.append(Offence(file=str(py_file), line=line_no, code=code))

    if offences:
        print(
            f"❌ Phase 250.0.13 — found {len(offences)} undocumented error code emission(s):",
            file=sys.stderr,
        )
        # Stable, deterministic ordering for editor / CI annotations.
        for off in sorted(offences, key=lambda o: (o.file, o.line, o.code)):
            print(off.render())
        return 1

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main(sys.argv))
