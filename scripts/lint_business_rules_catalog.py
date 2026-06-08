#!/usr/bin/env python3
"""
Phase 274.10.1 — Business rules catalog conformance CI check.

Idempotently verifies that every ``@register_rule``-decorated class in
``hub/apps/*/business_rules.py`` carries the three required metadata fields:

    * ``description`` — a 1-line human-readable summary
    * ``tags`` — a non-empty tuple of domain tags
    * ``openspec_ref`` — a pointer to the capability spec

Exit 0 when all rules conform; exit 1 with a report otherwise.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path
from typing import Dict, List, Tuple

HUB_APPS = Path(__file__).resolve().parent.parent / "hub" / "apps"

REQUIRED_KEYS = ("description", "tags", "openspec_ref")


class RuleMetadataChecker(ast.NodeVisitor):
    """Collect @register_rule call metadata and validate required keys."""

    def __init__(self, filepath: Path) -> None:
        self.filepath = filepath
        self.violations: List[str] = []
        self._current_class: str | None = None
        self._decorator_node: ast.Call | None = None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._current_class = node.name
        self._decorator_node = None
        for deco in node.decorator_list:
            if isinstance(deco, ast.Call) and _is_register_rule(deco):
                self._decorator_node = deco
                break
        self.generic_visit(node)
        if self._decorator_node:
            self._check_metadata(node)
        self._current_class = None
        self._decorator_node = None

    def _check_metadata(self, node: ast.ClassDef) -> None:
        assert self._decorator_node is not None
        kwargs = {kw.arg: _ast_value(kw.value) for kw in self._decorator_node.keywords if kw.arg}
        for key in REQUIRED_KEYS:
            if key not in kwargs:
                self.violations.append(
                    f"{self.filepath}:{node.lineno}: "
                    f"@{self._current_class} missing '{key}' in @register_rule()"
                )
            elif not kwargs[key]:
                self.violations.append(
                    f"{self.filepath}:{node.lineno}: "
                    f"@{self._current_class} has empty '{key}' in @register_rule()"
                )


def _is_register_rule(node: ast.Call) -> bool:
    if isinstance(node.func, ast.Name):
        return node.func.id == "register_rule"
    if isinstance(node.func, ast.Attribute):
        return node.func.attr == "register_rule"
    return False


def _ast_value(node: ast.expr) -> str | tuple | None:
    if isinstance(node, ast.Constant):
        val = node.value
        if isinstance(val, str):
            return val
        if isinstance(val, (int, float)):
            return str(val)
    if isinstance(node, ast.Tuple):
        return tuple(_ast_value(e) for e in node.elts)
    if isinstance(node, ast.List):
        return [_ast_value(e) for e in node.elts]
    return None


def collect_business_rules_files() -> List[Path]:
    files: List[Path] = []
    for app_dir in sorted(HUB_APPS.iterdir()):
        if not app_dir.is_dir():
            continue
        candidate = app_dir / "business_rules.py"
        if candidate.exists():
            files.append(candidate)
    return files


def main() -> int:
    files = collect_business_rules_files()
    if not files:
        print("No business_rules.py files found — nothing to check.")
        return 0

    all_violations: List[str] = []
    total_rules = 0

    for fpath in files:
        tree = ast.parse(fpath.read_text(encoding="utf-8"), filename=str(fpath))
        checker = RuleMetadataChecker(fpath)
        checker.visit(tree)
        all_violations.extend(checker.violations)
        # Count @register_rule in this file for summary
        total_rules += fpath.read_text(encoding="utf-8").count("@register_rule(")

    if all_violations:
        print(f"FAIL: {len(all_violations)} metadata violation(s) across {len(files)} files:")
        for v in all_violations:
            print(f"  {v}")
        return 1

    print(f"PASS: {total_rules} @register_rule classes across {len(files)} files — all conform.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
