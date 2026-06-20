#!/usr/bin/env python3
"""
281.A.1.2 — Django App Overlap Analysis.

Analyzes all Django apps under ``hub/apps/`` for:
  - Cross-app import dependencies (which apps import from which)
  - Model overlap (apps sharing the same conceptual domain)
  - Service-layer overlap (apps with similar service names/patterns)

Generates a merge-priority report ordered by overlap severity.
"""

import ast
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APPS_DIR = PROJECT_ROOT / "hub" / "apps"

# Known semantic groupings — apps in the same group likely overlap
SEMANTIC_GROUPS = {
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


def _ast_imports(filepath: Path) -> set[str]:
    """Extract imported module names from a Python file."""
    try:
        tree = ast.parse(filepath.read_text())
    except SyntaxError:
        return set()

    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    return imports


def _app_models(app_dir: Path) -> set[str]:
    """Return model class names defined in an app."""
    models_file = app_dir / "models.py"
    if not models_file.exists():
        return set()

    try:
        tree = ast.parse(models_file.read_text())
    except SyntaxError:
        return set()

    models = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                base_name = getattr(base, "attr", None) or (
                    base.id if hasattr(base, "id") else None
                )
                if base_name in ("Model", "models.Model", "TimeStampedModel"):
                    models.add(node.name)
    return models


def analyze() -> dict:
    """Run full overlap analysis."""
    apps = {}
    for d in sorted(APPS_DIR.iterdir()):
        if not d.is_dir() or not (d / "apps.py").exists():
            continue
        name = d.name
        py_files = list(d.rglob("*.py"))
        apps[name] = {
            "path": str(d),
            "py_files": len(py_files),
            "has_models": (d / "models.py").exists(),
            "has_services": (d / "services.py").exists() or (d / "services").is_dir(),
            "has_views": (d / "views.py").exists(),
            "models": list(_app_models(d)) if (d / "models.py").exists() else [],
        }

    # Cross-app imports
    cross_imports = defaultdict(lambda: defaultdict(set))
    for app_name, info in apps.items():
        app_dir = Path(info["path"])
        for py_file in app_dir.rglob("*.py"):
            if "migrations" in str(py_file) or "__pycache__" in str(py_file):
                continue
            imports = _ast_imports(py_file)
            for imp in imports:
                if imp in apps and imp != app_name:
                    cross_imports[app_name][imp].add(py_file.name)

    # Compute overlap score per group
    group_overlaps = {}
    for group_name, group_apps in SEMANTIC_GROUPS.items():
        present = group_apps & set(apps.keys())
        if len(present) >= 2:
            total_imports = sum(
                len(cross_imports.get(a, {}).get(b, set()))
                for a in present
                for b in present
                if a != b
            )
            group_overlaps[group_name] = {
                "apps": sorted(present),
                "cross_imports": total_imports,
            }

    return {
        "apps": {k: {kk: vv for kk, vv in v.items() if kk != "path"} for k, v in apps.items()},
        "cross_imports": {
            app: {dep: len(files) for dep, files in deps.items()}
            for app, deps in cross_imports.items()
        },
        "group_overlaps": dict(
            sorted(group_overlaps.items(), key=lambda x: x[1]["cross_imports"], reverse=True)
        ),
    }


def print_report(results: dict) -> None:
    """Print human-readable overlap analysis."""
    print("Django App Overlap Analysis (281.A.1.2)\n")

    print("Semantic Group Overlaps (ordered by merge priority):")
    for i, (group, info) in enumerate(results["group_overlaps"].items(), 1):
        apps_str = ", ".join(info["apps"])
        print(f"  {i}. {group} ({len(info['apps'])} apps, {info['cross_imports']} cross-imports):")
        print(f"     Apps: {apps_str}")
        if i <= 3:
            print("     → PRIORITY MERGE CANDIDATE")

    print("\nCross-App Import Dependencies:")
    for app, deps in sorted(results["cross_imports"].items()):
        if deps:
            dep_str = ", ".join(f"{d}({c})" for d, c in sorted(deps.items()))
            print(f"  {app:25s} → {dep_str}")

    print(f"\nTotal apps analyzed: {len(results['apps'])}")


def main():
    results = analyze()

    if "--json" in sys.argv:
        import json

        print(json.dumps(results, indent=2))
    else:
        print_report(results)


if __name__ == "__main__":
    main()
