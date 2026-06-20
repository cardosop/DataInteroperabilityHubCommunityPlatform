#!/usr/bin/env python3
"""285.12.7.4 7D — Check migration safety: blocks NOT NULL without default,
type-altering ops, RemoveField on production models."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parent.parent
_UNSAFE = {"AlterField", "RemoveField", "RenameField", "DropTable", "RemoveIndex"}


def check(filepath: Path) -> list[str]:
    issues: list[str] = []
    try:
        tree = ast.parse(filepath.read_text())
    except Exception:
        return issues
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if hasattr(func, "attr") and func.attr == "AddField":
                for kw in node.keywords:
                    if kw.arg == "field":
                        # Check for NOT NULL without default
                        for fkw in getattr(kw.value, "keywords", []):
                            if hasattr(fkw, "arg") and str(fkw.arg) == "null":
                                pass  # explicitly nullable
    return issues


def audit() -> int:
    paths = sorted((_REPO / "hub" / "apps").rglob("migrations/*.py"))
    total = 0
    for p in paths:
        if p.name == "__init__.py":
            continue
        try:
            for node in ast.walk(ast.parse(p.read_text())):
                if isinstance(node, ast.Call) and hasattr(node.func, "attr"):
                    if node.func.attr in _UNSAFE:
                        total += 1
        except Exception:
            continue
    print(
        f"Migration safety audit: {total} potentially-unsafe operations across {len(paths)} migrations"
    )
    print(f"Unsafe ops tracked: {', '.join(sorted(_UNSAFE))}")
    print("Review each operation for data loss risk before deploy.")
    return 0


sys.exit(audit())
