#!/usr/bin/env python3
"""
TR.H.5 — CI lint: new Django model without paired factory class.

Checks that every non-abstract Django model with a ``tenant_id`` FK
has a corresponding ``*Factory`` class in ``tests/factories.py``.

Informational for 30 days (until 2026-06-21), then blocking.

Usage:
    python scripts/lint_factory_coverage.py
    python scripts/lint_factory_coverage.py --blocking
    python scripts/lint_factory_coverage.py --json
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

FACTORIES_FILE = "tests/factories.py"
APPS_DIR = "hub/apps"
BLOCKING_DATE = datetime(2026, 6, 21, tzinfo=timezone.utc)


def _is_django_model(node: ast.ClassDef) -> bool:
    for base in node.bases:
        if isinstance(base, ast.Attribute) and base.attr == "Model":
            return True
        if isinstance(base, ast.Name) and base.id == "Model":
            return True
    return False


def _has_tenant_id(node: ast.ClassDef) -> bool:
    for item in ast.walk(node):
        if isinstance(item, ast.Call):
            for kw in getattr(item, "keywords", []):
                if kw.arg in ("to",) and hasattr(kw.value, "id"):
                    if kw.value.id == "Tenant" or "Tenant" in str(getattr(kw.value, "attr", "")):
                        return True
    return False


def _is_abstract(node: ast.ClassDef) -> bool:
    for child in node.body:
        if isinstance(child, ast.ClassDef) and child.name == "Meta":
            for stmt in child.body:
                if isinstance(stmt, ast.Assign):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name) and target.id == "abstract":
                            try:
                                if ast.literal_eval(stmt.value) is True:
                                    return True
                            except Exception:
                                pass
    return False


def _find_tenant_models(apps_dir: Path) -> dict[str, str]:
    """Return {model_name: app_name} for all tenant-scoped models."""
    models: dict[str, str] = {}
    for app_dir in sorted(apps_dir.iterdir()):
        if not app_dir.is_dir() or app_dir.name.startswith("_"):
            continue
        models_file = app_dir / "models.py"
        if not models_file.exists():
            continue
        try:
            tree = ast.parse(models_file.read_text())
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and _is_django_model(node):
                if _is_abstract(node):
                    continue
                if _has_tenant_id(node):
                    models[node.name] = app_dir.name
    return models


def _find_factory_classes(factories_file: Path) -> set[str]:
    """Return set of model names that have factory classes."""
    if not factories_file.exists():
        return set()
    content = factories_file.read_text()
    # Match "class XxxFactory(DjangoModelFactory):" and extract the model
    # from "class Meta: model = ModelName"
    factories: set[str] = set()
    for match in re.finditer(r"class\s+(\w+Factory)\s*\(.*DjangoModelFactory", content):
        factory_name = match.group(1)
        # Find the model line in the class body
        start = match.end()
        body = content[start:start + 500]
        model_match = re.search(r"model\s*=\s*(\w+)", body)
        if model_match:
            factories.add(model_match.group(1))
        elif "User" in factory_name:
            factories.add("User")
        elif "Tenant" in factory_name:
            factories.add("Tenant")
    return factories


def run_lint(
    repo_root: Path,
    blocking: bool = False,
    json_output: bool = False,
) -> int:
    apps_dir = repo_root / APPS_DIR
    factories_file = repo_root / FACTORIES_FILE

    tenant_models = _find_tenant_models(apps_dir)
    factory_models = _find_factory_classes(factories_file)

    uncovered = {
        name: app for name, app in tenant_models.items()
        if name not in factory_models
        and name not in ("User", "Tenant")  # User handled by get_user_model()
    }

    now = datetime.now(timezone.utc)
    is_blocking = blocking or now >= BLOCKING_DATE

    if json_output:
        print(json.dumps({
            "status": "fail" if (uncovered and is_blocking) else ("warn" if uncovered else "ok"),
            "total_models": len(tenant_models),
            "with_factories": len(factory_models),
            "uncovered": len(uncovered),
            "blocking": is_blocking,
            "uncovered_models": [
                {"model": name, "app": app} for name, app in sorted(uncovered.items())
            ],
        }, indent=2))
    else:
        print(f"Factory Coverage Check")
        print(f"  Tenant-scoped models: {len(tenant_models)}")
        print(f"  With factory classes: {len(factory_models)}")
        print(f"  Uncovered: {len(uncovered)}")
        mode = "BLOCKING" if is_blocking else "INFORMATIONAL"
        print(f"  Mode: {mode} (until {BLOCKING_DATE.strftime('%Y-%m-%d')})")
        if uncovered:
            print(f"\n  Models without factories:")
            for name, app in sorted(uncovered.items()):
                print(f"    - {name} ({app})")

    if uncovered and is_blocking:
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="TR.H.5 — Factory coverage lint")
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--blocking", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    return run_lint(args.repo_root, args.blocking, args.json)


if __name__ == "__main__":
    raise SystemExit(main())
