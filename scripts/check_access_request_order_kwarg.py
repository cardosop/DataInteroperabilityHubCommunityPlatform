#!/usr/bin/env python3
"""Phase 2.7 — regression lint: ``AccessRequest(order=...)`` is dead.

The round-3 paid-ward FK moved the order link onto ``Order.access_request``;
``AccessRequest`` has NO ``order`` field. Any construction passing
``order=`` (``AccessRequest.objects.create(order=...)`` or a direct
``AccessRequest(order=...)``) raises ``TypeError``/``FieldError`` at
runtime — the exact drift class the 10 seller-refund tests hit (2.2).
This AST-based scan fails CI when the pattern reappears anywhere in
``hub/``, ``tests/``, ``scripts/``, or ``cli/``.

Mirrors ``check_assert_true_true.py`` (AST, not regex — no false
positives from comments/strings). Exit 0 clean, 1 on violations.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

DEFAULT_SCAN_DIRS = ("hub", "tests", "scripts", "cli")

_ACCESS_REQUEST_NAMES = {"AccessRequest"}
_ORDER_KW = "order"


def collect_violations(root: Path, scan_dirs: tuple[str, ...] = DEFAULT_SCAN_DIRS) -> list[str]:
    violations: list[str] = []
    for scan_dir in scan_dirs:
        base = root / scan_dir
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            try:
                tree = ast.parse(path.read_text(), filename=str(path))
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                func = node.func
                name: str | None = None
                if isinstance(func, ast.Name) and func.id in _ACCESS_REQUEST_NAMES:
                    name = func.id
                elif (
                    isinstance(func, ast.Attribute)
                    and isinstance(func.value, ast.Attribute)
                    and func.value.attr == "objects"
                    and isinstance(func.value.value, ast.Name)
                    and func.value.value.id in _ACCESS_REQUEST_NAMES
                    and func.attr in ("create", "get_or_create", "update_or_create")
                ):
                    name = func.value.value.id
                if name is None:
                    continue
                for keyword in node.keywords:
                    if keyword.arg == _ORDER_KW:
                        rel = path.relative_to(root)
                        violations.append(
                            f"{rel}:{node.lineno}: {name}(order=...) — "
                            "the round-3 contract links Order.access_request "
                            "instead (AccessRequest has no 'order' field)"
                        )
    return sorted(violations)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ban AccessRequest(order=...) — the round-3 paid-ward FK drift class"
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)

    violations = collect_violations(args.root)
    if violations:
        print(f"ACCESS-REQUEST-ORDER: {len(violations)} violation(s):")
        for entry in violations:
            print(f"  {entry}")
        return 1
    print("ACCESS-REQUEST-ORDER: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
