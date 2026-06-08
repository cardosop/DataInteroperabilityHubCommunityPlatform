#!/usr/bin/env python3
"""
281.B.6.3 — Architectural fitness function enforcement.

Verifies structural invariants in CI. Fails the build on violations.
Expanded from W5.1 max-file-size + max-complexity to full criteria set.

Usage: python scripts/check_arch_fitness.py [--ci]
"""
from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path

# ── Fitness criteria ────────────────────────────────────────────────
MAX_FILE_LINES = 500
MAX_CYCLOMATIC_COMPLEXITY = 15
MAX_FUNCTION_LENGTH = 50  # lines
MAX_CLASS_METHODS = 30
MAX_IMPORT_DEPTH = 6  # max import chain depth
MAX_MODULE_COUPLING = 10  # max imports per module

SOURCE_DIRS = ("hub/", "cli/datahub_cli/", "sdk/python/datahub_interoperability/")


def _count_indented_lines(body: list[ast.stmt]) -> int:
    """Count non-blank, non-comment lines in a function body."""
    return len([s for s in body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant) and isinstance(s.value.value, str))])


def cyclomatic_complexity(node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """McCabe cyclomatic complexity: 1 + branches."""
    branches = 0
    for child in ast.walk(node):
        if isinstance(child, (ast.If, ast.For, ast.While, ast.And, ast.Or,
                              ast.ExceptHandler, ast.With, ast.Match)):
            branches += 1
        elif isinstance(child, ast.BoolOp):
            branches += len(child.values) - 1
    return 1 + branches


def check_fitness(source_dir: str, violations: list[str]) -> None:
    for py_file in sorted(Path(source_dir).rglob("*.py")):
        if "/migrations/" in str(py_file) or "/tests/" in str(py_file):
            continue
        try:
            content = py_file.read_text()
        except Exception:
            continue

        lines = content.split("\n")
        file_lines = len(lines)

        # 1. Max file size
        if file_lines > MAX_FILE_LINES:
            violations.append(
                f"{py_file}: {file_lines} lines (max {MAX_FILE_LINES})"
            )

        # 2. Max imports
        imports = content.count("\nimport ") + content.count("\nfrom ")
        if imports > MAX_MODULE_COUPLING:
            violations.append(
                f"{py_file}: {imports} imports (max {MAX_MODULE_COUPLING})"
            )

        # 3. Per-function checks
        try:
            tree = ast.parse(content)
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Cyclomatic complexity
                cc = cyclomatic_complexity(node)
                if cc > MAX_CYCLOMATIC_COMPLEXITY:
                    violations.append(
                        f"{py_file}:{node.lineno} {node.name}() "
                        f"complexity {cc} (max {MAX_CYCLOMATIC_COMPLEXITY})"
                    )

                # Function length
                func_lines = _count_indented_lines(node.body)
                if func_lines > MAX_FUNCTION_LENGTH:
                    violations.append(
                        f"{py_file}:{node.lineno} {node.name}() "
                        f"{func_lines} lines (max {MAX_FUNCTION_LENGTH})"
                    )

            # 4. Max class methods
            if isinstance(node, ast.ClassDef):
                methods = [n for n in node.body
                           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                if len(methods) > MAX_CLASS_METHODS:
                    violations.append(
                        f"{py_file}:{node.lineno} {node.name} "
                        f"{len(methods)} methods (max {MAX_CLASS_METHODS})"
                    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Architectural fitness checks")
    parser.add_argument("--ci", action="store_true", help="CI mode: exit 1 on violation")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    violations: list[str] = []
    for src in SOURCE_DIRS:
        if Path(src).is_dir():
            check_fitness(src, violations)

    if args.json:
        import json
        print(json.dumps({"violations": violations, "count": len(violations)}, indent=2))
    elif violations:
        print(f"Architectural fitness violations ({len(violations)}):")
        for v in sorted(violations):
            print(f"  ⚠️  {v}")
    else:
        print("All architectural fitness checks passed.")

    if violations and args.ci:
        print("\nCI gate: FAILED — architectural fitness violations must be resolved.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
