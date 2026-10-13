#!/usr/bin/env python3
"""One-shot W16 migration: retire the per-file ``_check_api_available()`` helpers.

For every file under ``cli/`` and ``tests/`` that defines the duplicated
helper: drop the definition, route every call site through the shared
``envpolicy.api_available()`` policy, and add the import after the module
docstring. Idempotent — a second run is a no-op.
"""

from __future__ import annotations

import re
from pathlib import Path

IMPORT_LINE = "from envpolicy import api_available\n"


def _module_docstring_end(text: str) -> int:
    """Index just past the module docstring, or 0 when there is none.

    Handles both triple-quoted and single-line string docstrings; a shebang
    line is allowed before the docstring.
    """
    pos = 0
    if text.startswith("#!"):
        pos = text.index("\n") + 1
    rest = text[pos:]
    for marker in ('"""', "'''"):
        if not rest.startswith(marker):
            continue
        closing = rest.find(marker, len(marker))
        if closing == -1:
            # Unterminated docstring — do not insert anything.
            return 0
        end = pos + closing + len(marker)
        # Consume trailing whitespace so the import starts on its own line.
        while end < len(text) and text[end] in " \t\r\n":
            end += 1
        return end
    m = re.match(r"\s*(\"[^\"]*\"|'[^']*')\s*", rest)
    if m and rest[m.start() : m.end()].strip():
        return pos + m.end()
    return 0


def migrate(text: str) -> str:
    # 1. Drop the duplicated helper definition (module-level or method).
    lines = text.splitlines(keepends=True)
    out = []
    i = 0
    while i < len(lines):
        m = re.match(r"^(?P<indent>[ \t]*)def _check_api_available\((?:self)?\):", lines[i])
        if m:
            indent = len(m.group("indent"))
            i += 1  # the def line
            while i < len(lines):
                stripped = lines[i].strip()
                if stripped and len(lines[i]) - len(lines[i].lstrip(" \t")) <= indent:
                    break
                i += 1
            while out and out[-1].strip() == "":
                out.pop()
            if out and not out[-1].endswith("\n\n"):
                out.append("\n")
            continue
        out.append(lines[i])
        i += 1
    text = "".join(out)

    # 2. Route every call site through the policy.
    text = text.replace("self._check_api_available()", "api_available()")
    text = text.replace("_check_api_available()", "api_available()")

    # 3. Insert the import after the module docstring (or at the top).
    pos = _module_docstring_end(text)
    text = text[:pos] + IMPORT_LINE + text[pos:]
    return text


def repair_mangled_docstring(text: str) -> str:
    """Undo the first-run bug: the import was inserted between the first two
    quotes of a triple-quoted docstring (``""from envpolicy...``)."""
    for marker, short in (('"""', '""'), ("'''", "''")):
        mangled = short + IMPORT_LINE + marker[0]
        if text.startswith(mangled):
            return marker + text[len(mangled) :]
    return text


def main() -> None:
    files = sorted(
        p
        for root in ("cli", "tests")
        for p in Path(root).rglob("*.py")
        if re.search(r"^\s*def _check_api_available\(", p.read_text(), re.M)
    )
    total = 0
    for p in files:
        text = p.read_text()
        n = text.count("def _check_api_available")
        p.write_text(migrate(text))
        total += n
        print(f"{p}: {n} def(s) removed")
    print(f"migrated {len(files)} files, removed {total} defs")


if __name__ == "__main__":
    main()
