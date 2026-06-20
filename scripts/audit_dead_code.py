#!/usr/bin/env python3
"""
281.A.1.3 — Dead Code Audit & Removal.

Scans the codebase for:
  - ``_services_legacy.py`` / ``_legacy.py`` files (legacy service stubs)
  - Files with no incoming imports (orphaned modules)
  - Commented-out code blocks (``# ...`` spanning >3 consecutive lines)
  - ``TODO remove`` / ``FIXME remove`` markers
  - Feature flags that are always-true or always-false

Usage:
  python scripts/audit_dead_code.py              # audit only
  python scripts/audit_dead_code.py --remove     # audit + remove safe items
  python scripts/audit_dead_code.py --json       # JSON output
"""

import ast
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
HUB_DIR = PROJECT_ROOT / "hub"

# Files safe to remove — confirmed dead code (zero incoming imports)
KNOWN_DEAD_FILES = [
    "hub/apps/integrations/_services_legacy.py",
    "hub/apps/virtualization/_services_legacy.py",
]

# Feature flags confirmed as always-true (GA, unconditionally enabled)
ALWAYS_TRUE_FLAGS = [
    # Add flags confirmed as permanently enabled after verification
]


def find_legacy_files() -> list[Path]:
    """Find files matching legacy naming patterns."""
    patterns = ["_services_legacy.py", "_legacy.py", "_deprecated.py"]
    results = []
    for pattern in patterns:
        results.extend(HUB_DIR.rglob(pattern))
    return sorted(results)


def find_orphaned_modules() -> list[Path]:
    """Find Python modules with zero incoming imports (excluding tests/migrations)."""
    all_modules = set()
    imported_modules = set()

    for py_file in HUB_DIR.rglob("*.py"):
        if "__pycache__" in str(py_file) or "node_modules" in str(py_file):
            continue
        rel = str(py_file.relative_to(PROJECT_ROOT))
        all_modules.add(rel)

        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    imported_modules.add(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imported_modules.add(alias.name)

    # A module is orphaned if no other module imports it.
    # Exclude Django auto-discovered files (apps.py, admin.py, urls.py, signals.py,
    # management/commands, __init__.py) which are loaded by Django's app registry,
    # not by explicit import statements — they're not dead code.
    DJANGO_AUTO_FILES = {
        "apps",
        "admin",
        "urls",
        "signals",
        "receivers",
        "tasks",
        "forms",
        "__init__",
        "conftest",
        "settings",
        "factories",
    }
    EXCLUDED_DIRS = {
        "tests",
        "migrations",
        "management",
        "__pycache__",
        "node_modules",
        ".mypy_cache",
    }

    orphans = []
    for mod in sorted(all_modules):
        mod_path = Path(mod)
        # Skip Django infrastructure and generated files
        if mod_path.stem in DJANGO_AUTO_FILES:
            continue
        if any(d in str(mod_path) for d in EXCLUDED_DIRS):
            continue
        # Skip files loaded via dotted-path settings (serializers, views, etc.
        # imported through REST framework routers and Django URL confs)
        if mod_path.stem in (
            "serializers",
            "views",
            "models",
            "metrics",
            "business_rules",
            "event_types",
            "feature_flags",
        ):
            # These are almost always imported dynamically; flag as
            # "low-confidence orphan" rather than certain dead code
            continue

        module_name = mod_path.stem
        module_dotpath = str(mod_path.with_suffix("")).replace("/", ".")
        is_imported = any(module_name in imp or module_dotpath in imp for imp in imported_modules)
        if not is_imported:
            orphans.append(mod)

    return orphans[:50]  # Cap to top 50 to keep output manageable


def find_commented_out_blocks() -> list[dict]:
    """Find commented-out Python code blocks (≥3 consecutive comment-only lines)."""
    blocks = []
    for py_file in HUB_DIR.rglob("*.py"):
        if "__pycache__" in str(py_file) or "migrations" in str(py_file):
            continue
        try:
            lines = py_file.read_text().split("\n")
        except Exception:
            continue

        i = 0
        while i < len(lines):
            stripped = lines[i].strip()
            if stripped.startswith("#") and not stripped.startswith("##"):
                # Check if this is a comment-only line (not a docstring/inline comment)
                # Skip license headers and section dividers
                if stripped.startswith("# Copyright") or stripped.startswith("# ~"):
                    i += 1
                    continue

                block_start = i + 1  # 1-indexed line number
                while i < len(lines) and (
                    lines[i].strip().startswith("#") and not lines[i].strip().startswith("##")
                ):
                    i += 1
                block_len = i - block_start + 1
                if block_len >= 3:
                    blocks.append(
                        {
                            "file": str(py_file.relative_to(PROJECT_ROOT)),
                            "line": block_start,
                            "lines": block_len,
                            "preview": lines[block_start - 1].strip()[:80],
                        }
                    )
            else:
                i += 1

    return blocks


def find_always_true_flags() -> list[dict]:
    """Find feature flag checks that are always true."""
    results = []
    flag_pattern = re.compile(
        r'feature_flag.*\.(is_enabled|get)\s*\(\s*["\']([\w.]+)["\']',
    )

    for py_file in HUB_DIR.rglob("*.py"):
        if "__pycache__" in str(py_file) or "test" in str(py_file):
            continue
        try:
            content = py_file.read_text()
        except Exception:
            continue

        for m in flag_pattern.finditer(content):
            flag_name = m.group(2)
            if flag_name in ALWAYS_TRUE_FLAGS:
                results.append(
                    {
                        "file": str(py_file.relative_to(PROJECT_ROOT)),
                        "flag": flag_name,
                        "line": content[: m.start()].count("\n") + 1,
                    }
                )

    return results


def audit() -> dict:
    """Run full dead code audit."""
    return {
        "legacy_files": [str(f.relative_to(PROJECT_ROOT)) for f in find_legacy_files()],
        "orphaned_modules": find_orphaned_modules(),
        "commented_out_blocks": find_commented_out_blocks(),
        "always_true_flags": find_always_true_flags(),
        "known_dead_files": KNOWN_DEAD_FILES,
    }


def remove_known_dead_files(dry_run: bool = True) -> list[str]:
    """Remove files known to be dead code. Returns list of removed paths."""
    removed = []
    for rel_path in KNOWN_DEAD_FILES:
        path = PROJECT_ROOT / rel_path
        if path.exists():
            if not dry_run:
                path.unlink()
            removed.append(rel_path)
    return removed


def print_report(results: dict) -> None:
    """Print human-readable dead code audit."""
    print("Dead Code Audit (281.A.1.3)\n")

    lf = results["legacy_files"]
    print(f"Legacy files: {len(lf)}")
    for f in lf:
        size = (PROJECT_ROOT / f).stat().st_size if (PROJECT_ROOT / f).exists() else 0
        print(f"  {f} ({size:,} bytes)")

    orphans = results["orphaned_modules"]
    print(f"\nOrphaned modules (no incoming imports): {len(orphans)}")
    for o in orphans[:20]:
        print(f"  {o}")

    blocks = results["commented_out_blocks"]
    print(f"\nCommented-out code blocks (≥3 lines): {len(blocks)}")
    for b in blocks[:10]:
        print(f"  {b['file']}:{b['line']} ({b['lines']} lines) — {b['preview']}")

    flags = results["always_true_flags"]
    print(f"\nAlways-true feature flag branches: {len(flags)}")
    for f in flags:
        print(f"  {f['file']}:{f['line']} — flag={f['flag']}")

    print("\nKnown dead files ready for removal:")
    for f in KNOWN_DEAD_FILES:
        exists = (PROJECT_ROOT / f).exists()
        status = "EXISTS — ready to remove" if exists else "already removed"
        print(f"  {f} ({status})")


def main():
    remove_mode = "--remove" in sys.argv
    json_mode = "--json" in sys.argv

    if remove_mode:
        removed = remove_known_dead_files(dry_run=False)
        print(f"Removed {len(removed)} dead file(s):")
        for r in removed:
            print(f"  {r}")
    else:
        results = audit()
        if json_mode:
            import json

            print(json.dumps(results, indent=2, default=str))
        else:
            print_report(results)


if __name__ == "__main__":
    main()
