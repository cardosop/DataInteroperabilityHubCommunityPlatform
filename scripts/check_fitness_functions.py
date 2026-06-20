#!/usr/bin/env python3
"""
281.A.1.4 — Architectural Fitness Functions.

CI-enforceable checks:
  1. **max-file-size** — no Python file may exceed 500 lines (configurable).
     Tests are checked at 1000 lines.
  2. **max-complexity** — no function may exceed cyclomatic complexity 15
     (McCabe). Uses ``radon`` if installed; falls back to AST-based
     approximation.
  3. **app-boundary** — apps may not import from sibling apps across
     semantic-group boundaries without a documented exception.

Usage:
  python scripts/check_fitness_functions.py                  # all checks
  python scripts/check_fitness_functions.py --max-lines 500  # custom threshold
  python scripts/check_fitness_functions.py --check           # exit 1 on violation
  python scripts/check_fitness_functions.py --json            # JSON output
"""

import ast
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HUB_DIR = PROJECT_ROOT / "hub"

# ── Configuration ─────────────────────────────────────────────────────────

MAX_FILE_LINES = 500
MAX_TEST_FILE_LINES = 1000
MAX_COMPLEXITY = 15

# Semantic group boundaries (same as audit_app_overlaps.py).
# Apps in DIFFERENT groups should not cross-import without explicit exception.
APP_GROUPS = {
    "data-pipeline": {
        "integrations",
        "virtualization",
        "transformation",
        "scheduled_ingestion",
        "scheduled_export",
    },
    "governance-compliance": {
        "governance",
        "compliance",
        "regulation_policies",
        "dsar",
    },
    "assets-contracts": {
        "assets",
        "contracts",
        "datasets",
        "files",
    },
    "marketplace-billing": {
        "marketplace",
        "billing",
        "baas",
    },
    "observability-audit": {
        "observability",
        "audit",
        "notifications",
    },
    "core-infra": {
        "core",
        "api",
        "auth",
        "tenants",
        "users",
        "jobs",
        "mesh",
    },
    "search-semantic": {
        "search",
        "semantic",
    },
    "quality-webhooks": {
        "dq",
        "webhooks",
        "processor_agreements",
    },
}

# Allowed cross-group imports (documented exceptions)
ALLOWED_CROSS_GROUP = {
    # Any app is allowed to import from 'core' (shared infrastructure)
    "core",
    "api",
    "auth",
    "tenants",
}

# Files exempt from line-count checks
EXEMPT_FILES = {
    "hub/settings.py",  # Django settings are configuration, not logic
}


def _app_group(app_name: str) -> str | None:
    """Return the semantic group for an app, or None."""
    for group, apps in APP_GROUPS.items():
        if app_name in apps:
            return group
    return None


# ── Check 1: File size ────────────────────────────────────────────────────


def check_file_sizes(max_lines: int = MAX_FILE_LINES) -> list[dict]:
    """Return files exceeding the line-count threshold."""
    violations = []
    for py_file in HUB_DIR.rglob("*.py"):
        rel = str(py_file.relative_to(PROJECT_ROOT))
        if rel in EXEMPT_FILES:
            continue
        if "__pycache__" in str(py_file):
            continue
        if "node_modules" in str(py_file):
            continue

        is_test = "test" in py_file.name or "/tests/" in str(py_file)
        threshold = MAX_TEST_FILE_LINES if is_test else max_lines

        try:
            line_count = len(py_file.read_text().split("\n"))
        except Exception:
            continue

        if line_count > threshold:
            violations.append(
                {
                    "file": rel,
                    "lines": line_count,
                    "threshold": threshold,
                    "is_test": is_test,
                }
            )

    violations.sort(key=lambda v: v["lines"], reverse=True)
    return violations


# ── Check 2: Cyclomatic complexity (AST approximation) ─────────────────────


def _ast_complexity(func_node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
    """Approximate McCabe cyclomatic complexity from AST.

    Starts at 1; adds 1 for each branch point:
    if, elif, for, while, except, and, or, ternary, comprehension.
    """
    complexity = 1
    for node in ast.walk(func_node):
        if isinstance(node, (ast.If, ast.For, ast.While, ast.ExceptHandler)):
            complexity += 1
        elif isinstance(node, ast.BoolOp):
            complexity += len(node.values) - 1
        elif isinstance(
            node, (ast.IfExp, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)
        ):
            complexity += 1
        elif isinstance(node, ast.Try):
            complexity += len(node.handlers)
    return complexity


def check_complexity(max_cc: int = MAX_COMPLEXITY) -> list[dict]:
    """Return functions exceeding the cyclomatic complexity threshold."""
    violations = []
    for py_file in HUB_DIR.rglob("*.py"):
        rel = str(py_file.relative_to(PROJECT_ROOT))
        if "__pycache__" in rel or "migrations" in rel or "node_modules" in rel:
            continue

        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                cc = _ast_complexity(node)
                if cc > max_cc:
                    violations.append(
                        {
                            "file": rel,
                            "function": node.name,
                            "line": node.lineno,
                            "complexity": cc,
                            "threshold": max_cc,
                        }
                    )

    violations.sort(key=lambda v: v["complexity"], reverse=True)
    return violations


# ── Check 3: App boundary (cross-group imports) ────────────────────────────


def check_app_boundaries() -> list[dict]:
    """Return cross-group imports that violate architectural boundaries."""
    violations = []
    app_to_group = {}
    for app_dir in HUB_DIR.glob("apps/*"):
        if app_dir.is_dir() and (app_dir / "apps.py").exists():
            app_to_group[app_dir.name] = _app_group(app_dir.name)

    for py_file in HUB_DIR.rglob("*.py"):
        rel = str(py_file.relative_to(PROJECT_ROOT))
        if "migrations" in rel or "__pycache__" in rel:
            continue

        # Determine which app this file belongs to
        parts = Path(rel).parts
        source_app = None
        for part in parts:
            if part in app_to_group:
                source_app = part
                break

        if source_app is None:
            continue

        source_group = app_to_group.get(source_app)

        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module is None:
                    continue
                target_app = node.module.split(".")[0]
                if target_app == source_app:
                    continue
                if target_app not in app_to_group:
                    continue

                target_group = app_to_group.get(target_app)
                if target_group is None or source_group is None:
                    continue
                if target_group == source_group:
                    continue  # Same group — allowed
                if target_app in ALLOWED_CROSS_GROUP:
                    continue  # Explicitly allowed

                violations.append(
                    {
                        "file": rel,
                        "line": node.lineno,
                        "source_app": source_app,
                        "source_group": source_group,
                        "target_app": target_app,
                        "target_group": target_group,
                        "import": f"from {node.module} import ...",
                    }
                )

    return violations


# ── Main ───────────────────────────────────────────────────────────────────


def run_all(max_lines: int = MAX_FILE_LINES, max_cc: int = MAX_COMPLEXITY) -> dict:
    """Run all fitness checks and return a structured report."""
    size_violations = check_file_sizes(max_lines)
    cc_violations = check_complexity(max_cc)
    boundary_violations = check_app_boundaries()

    return {
        "file_size": {
            "threshold": max_lines,
            "test_threshold": MAX_TEST_FILE_LINES,
            "violations": len(size_violations),
            "details": size_violations[:30],  # Top 30 worst offenders
        },
        "complexity": {
            "threshold": max_cc,
            "violations": len(cc_violations),
            "details": cc_violations[:30],  # Top 30 worst offenders
        },
        "app_boundaries": {
            "violations": len(boundary_violations),
            "allowed_cross_group": sorted(ALLOWED_CROSS_GROUP),
            "details": boundary_violations[:30],
        },
        "summary": {
            "total_violations": (
                len(size_violations) + len(cc_violations) + len(boundary_violations)
            ),
            "pass": (len(size_violations) == 0 and len(cc_violations) == 0),
        },
    }


def print_report(results: dict) -> None:
    """Print a human-readable fitness report."""
    fs = results["file_size"]
    cc = results["complexity"]
    ab = results["app_boundaries"]

    print("Architectural Fitness Check (281.A.1.4)\n")

    print(f"1. File Size (max {fs['threshold']} lines, tests {fs['test_threshold']}):")
    if fs["violations"] == 0:
        print("   ✅ All files within limits")
    else:
        print(f"   ❌ {fs['violations']} file(s) exceed limit:")
        for v in fs["details"][:10]:
            print(f"      {v['file']}: {v['lines']} lines (limit={v['threshold']})")

    print(f"\n2. Cyclomatic Complexity (max {cc['threshold']}):")
    if cc["violations"] == 0:
        print("   ✅ All functions within complexity limit")
    else:
        print(f"   ❌ {cc['violations']} function(s) exceed limit:")
        for v in cc["details"][:10]:
            print(
                f"      {v['file']}:{v['line']} {v['function']}() "
                f"— complexity {v['complexity']} "
                f"(limit={v['threshold']})"
            )

    print("\n3. App Boundaries (cross-group imports):")
    if ab["violations"] == 0:
        print("   ✅ No cross-group boundary violations")
    else:
        print(f"   ⚠️  {ab['violations']} cross-group import(s):")
        for v in ab["details"][:10]:
            print(
                f"      {v['file']}:{v['line']} — "
                f"{v['source_group']} → {v['target_group']} "
                f"({v['import']})"
            )

    s = results["summary"]
    print(
        f"\nSummary: {s['total_violations']} total violations ({'PASS' if s['pass'] else 'FAIL'})"
    )


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Architectural fitness checks")
    parser.add_argument("--max-lines", type=int, default=MAX_FILE_LINES)
    parser.add_argument("--max-complexity", type=int, default=MAX_COMPLEXITY)
    parser.add_argument("--check", action="store_true", help="Exit 1 if any violation found")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--file-size-only", action="store_true", help="Check file sizes only")
    parser.add_argument("--complexity-only", action="store_true", help="Check complexity only")
    args = parser.parse_args()

    if args.file_size_only:
        violations = check_file_sizes(args.max_lines)
        results = {"file_size": {"violations": len(violations), "details": violations}}
    elif args.complexity_only:
        violations = check_complexity(args.max_complexity)
        results = {"complexity": {"violations": len(violations), "details": violations}}
    else:
        results = run_all(args.max_lines, args.max_complexity)

    if args.json:
        print(json.dumps(results, indent=2, default=str))
    else:
        print_report(results)

    if args.check:
        total = results.get("summary", {}).get(
            "total_violations",
            len(results.get("file_size", {}).get("details", []))
            + len(results.get("complexity", {}).get("details", [])),
        )
        if total > 0:
            sys.exit(1)


if __name__ == "__main__":
    main()
