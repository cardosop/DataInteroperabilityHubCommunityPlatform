#!/usr/bin/env python3
"""One-shot W16 repair: fix the migration's shadowing bug in the touched files.

Context: the pre-migration files wrapped ``_check_api_available()`` in
module-level defs/fixtures ALSO named ``api_available``. Once the helper is
retired and call sites point at the envpolicy import, any remaining local
``def api_available`` shadows the import (and a fixture whose body calls
``api_available()`` recurses).

Repair (AST-guided, absolute offsets — never column-as-position):
  * delete every module/class-level ``def api_available`` whose body is the
    OLD probe (``requests.get`` / ``status_code`` / ``self.session.get``);
  * ``@pytest.fixture``-decorated ``api_available`` defs (pre-existing
    wrappers) are RENAMED to ``api_service_available``, together with every
    test-function argument named ``api_available`` in the same file;
  * remaining plain ``api_available`` wrapper defs are deleted — call sites
    already point at the envpolicy import, which is the policy-applied
    implementation.
After repair every file has zero module-level ``def api_available`` and
exactly one ``from envpolicy import api_available`` import.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

IMPORT_LINE = "from envpolicy import api_available\n"
IMPORT_RE = re.compile(r"^from envpolicy import api_available\n$", re.M)


def _has_old_probe(node: ast.AST) -> bool:
    for sub in ast.walk(node):
        if (
            isinstance(sub, ast.Attribute)
            and sub.attr == "get"
            and isinstance(sub.value, ast.Name)
            and sub.value.id in ("requests", "session")
        ):
            return True
        if isinstance(sub, ast.Compare):
            for comparator in ast.walk(sub):
                if isinstance(comparator, ast.Attribute) and comparator.attr == "status_code":
                    return True
    return False


def _is_fixture_def(node: ast.AST) -> bool:
    for dec in node.decorator_list:
        if (
            isinstance(dec, ast.Call)
            and isinstance(dec.func, ast.Attribute)
            and dec.func.attr == "fixture"
            and isinstance(dec.func.value, ast.Name)
            and dec.func.value.id == "pytest"
        ):
            return True
    return False


def _line_offsets(text: str) -> list[int]:
    """Character offset of the start of each line."""
    offsets = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            offsets.append(i + 1)
    return offsets


def _span(node: ast.AST, offsets: list[int]) -> tuple[int, int]:
    start = offsets[node.lineno - 1] + node.col_offset
    end = offsets[node.end_lineno - 1] + node.end_col_offset
    return start, end


def repair(text: str, filename: str) -> tuple[str, list[str]]:
    """Return repaired text + human-readable actions taken."""
    actions: list[str] = []
    tree = ast.parse(text)
    offsets = _line_offsets(text)

    defs: list[ast.FunctionDef] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == "api_available":
            defs.append(node)

    delete_spans: list[tuple[int, int]] = []
    rename_spans: list[tuple[int, int]] = []

    for node in defs:
        if _is_fixture_def(node):
            # Rename just the NAME token, keeping the `def ` keyword.
            name_start = offsets[node.lineno - 1] + node.col_offset + len("def ")
            rename_spans.append((name_start, name_start + len("api_available")))
            actions.append(f"{filename}: rename fixture def api_available -> api_service_available")
        else:
            delete_spans.append(_span(node, offsets))
            actions.append(f"{filename}: delete local api_available def @{node.lineno}")

    # Test-function args named api_available must follow the fixture rename.
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name != "api_available":
            for arg in node.args.args:
                if arg.arg == "api_available":
                    rename_spans.append(_span(arg, offsets))
                    actions.append(f"{filename}: rename arg api_available @{node.lineno}")

    # Drop renames that fall inside a deleted block.
    def inside_deleted(span: tuple[int, int]) -> bool:
        return any(ds <= span[0] and span[1] <= de for ds, de in delete_spans)

    rename_spans = [s for s in rename_spans if not inside_deleted(s)]

    # Apply all edits right-to-left (positions left of an applied edit stay
    # valid).
    edits = [(s, e, "") for s, e in delete_spans] + [
        (s, e, "api_service_available") for s, e in rename_spans
    ]
    new_text = text
    for start, end, repl in sorted(edits, key=lambda t: t[0], reverse=True):
        new_text = new_text[:start] + repl + new_text[end:]

    # Import hygiene: exactly one envpolicy import.
    parts = IMPORT_RE.split(new_text)
    if len(parts) == 1:
        actions.append(f"{filename}: WARNING no envpolicy import present")
    elif len(parts) > 2:
        new_text = parts[0] + IMPORT_LINE + "".join(parts[1:])
        actions.append(f"{filename}: deduped envpolicy imports")

    return new_text, actions


def main() -> None:
    files = []
    for root in ("cli", "tests"):
        for p in Path(root).rglob("*.py"):
            text = p.read_text()
            if IMPORT_RE.search(text) and re.search(r"^\s*def api_available\(", text, re.M):
                files.append(p)
    files = sorted(files)
    print(f"{len(files)} files to repair")
    for p in files:
        repaired, actions = repair(p.read_text(), str(p))
        p.write_text(repaired)
        for a in actions:
            print(f"  {a}")


if __name__ == "__main__":
    main()
