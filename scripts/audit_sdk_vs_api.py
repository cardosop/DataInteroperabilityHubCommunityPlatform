#!/usr/bin/env python3
"""
283.2.1 — SDK vs API Gap Matrix.

Audits every Python SDK method against the backend API surface and
reports which API endpoints are NOT yet exposed in the SDK.

Produces a per-module gap report feeding Phase 3–5 work assignments.

Usage:
  python scripts/audit_sdk_vs_api.py                 # human-readable
  python scripts/audit_sdk_vs_api.py --json          # JSON for CI
  python scripts/audit_sdk_vs_api.py --summary       # counts only
"""

import ast
import json
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SDK_DIR = PROJECT_ROOT / "sdk" / "python" / "datahub_interoperability"
HUB_URLS_DIR = PROJECT_ROOT / "hub"

# ── Extract SDK public methods ────────────────────────────────────────────


def extract_sdk_methods() -> dict[str, set[str]]:
    """Return {module_name: {method_name, ...}} for the SDK."""
    methods = defaultdict(set)
    if not SDK_DIR.is_dir():
        return methods

    for py_file in sorted(SDK_DIR.rglob("*.py")):
        if py_file.name.startswith("_") or py_file.name == "__init__.py":
            continue
        module = py_file.stem
        try:
            tree = ast.parse(py_file.read_text())
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if not node.name.startswith("_"):
                    methods[module].add(node.name)
    return dict(methods)


# ── Extract API endpoints from Django URL patterns ────────────────────────


def extract_api_endpoints() -> dict[str, set[str]]:
    """Return {prefix: {endpoint_pattern, ...}} for the backend API."""
    endpoints = defaultdict(set)

    for url_file in HUB_URLS_DIR.rglob("urls.py"):
        if "migrations" in str(url_file) or "__pycache__" in str(url_file):
            continue

        try:
            content = url_file.read_text()
        except Exception:
            continue

        # Extract path patterns from urlpatterns
        # Match: path("prefix/", ...) or re_path(r"prefix/", ...)
        import re

        for m in re.finditer(
            r'(?:path|re_path)\s*\(\s*["\']([^"\']+)["\']',
            content,
        ):
            pattern = m.group(1)
            # Determine prefix from the app structure
            rel = str(url_file.relative_to(PROJECT_ROOT))
            if "hub/apps/" in rel:
                app = rel.split("hub/apps/")[1].split("/")[0]
                endpoints[app].add(pattern)

    return dict(endpoints)


# ── Extract API endpoints from URL conf hub/urls.py ───────────────────────


def extract_api_prefixes() -> dict[str, list[str]]:
    """Return {prefix: [endpoint, ...]} from the root URL configuration."""
    prefixes = defaultdict(list)
    url_conf = HUB_URLS_DIR / "urls.py"

    if not url_conf.exists():
        return dict(prefixes)

    content = url_conf.read_text()
    import re

    # Find include() calls with namespace hints
    for m in re.finditer(
        r'path\s*\(\s*["\']([^"\']+)["\']\s*,\s*include\s*\(\s*["\']([^"\']+)["\']',
        content,
    ):
        prefix = m.group(1)
        included = m.group(2)
        prefixes[prefix].append(included)

    return dict(prefixes)


# ── Gap analysis ─────────────────────────────────────────────────────────

SDK_TO_API_MAP = {
    "assets": "/api/v1/assets",
    "contracts": "/api/v1/contracts",
    "datasets": "/api/v1/datasets",
    "files": "/api/v1/files",
    "marketplace": "/api/v1/marketplace",
    "search": "/api/v1/search",
    "semantic": "/api/v1/semantic",
    "compliance": "/api/v1/compliance",
    "governance": "/api/v1/governance",
    "webhooks": "/api/v1/webhooks",
    "tenants": "/api/v1/tenants",
    "billing": "/api/v1/billing",
    "jobs": "/api/v1/jobs",
    "dq": "/api/v1/dq",
    "lineage": "/api/v1/lineage",
    "audit": "/api/v1/audit",
    "notifications": "/api/v1/notifications",
    "scheduled_ingestion": "/api/v1/scheduled-ingestion",
    "scheduled_export": "/api/v1/scheduled-export",
    "transformations": "/api/v1/transformations",
    "warehouses": "/api/v1/warehouses",
    "users": "/api/v1/users",
    "health": "/health",
}


def run_gap_analysis() -> dict:
    """Run the full SDK vs API gap analysis."""
    sdk_methods = extract_sdk_methods()
    api_endpoints = extract_api_endpoints()
    api_prefixes = extract_api_prefixes()

    # Per-module gap summary
    gaps = {}
    total_sdk = sum(len(v) for v in sdk_methods.values())
    total_api = sum(len(v) for v in api_endpoints.values())

    # Modules with API endpoints but no SDK methods
    sdk_modules = set(sdk_methods.keys())
    api_modules = set(api_endpoints.keys())

    modules_only_api = api_modules - sdk_modules
    sdk_modules - api_modules
    modules_shared = sdk_modules & api_modules

    for module in sorted(modules_only_api):
        ep_count = len(api_endpoints.get(module, set()))
        gaps[module] = {
            "status": "NO_SDK_COVERAGE",
            "api_endpoints": ep_count,
            "sdk_methods": 0,
            "gap_pct": 100,
        }

    for module in sorted(modules_shared):
        api_count = len(api_endpoints.get(module, set()))
        sdk_count = len(sdk_methods.get(module, set()))
        if api_count > 0:
            coverage_pct = min(100, (sdk_count / api_count) * 100)
            gaps[module] = {
                "status": "COVERED" if sdk_count >= api_count * 0.8 else "UNDER_COVERED",
                "api_endpoints": api_count,
                "sdk_methods": sdk_count,
                "gap_pct": round(100 - coverage_pct, 1),
            }

    return {
        "summary": {
            "total_sdk_methods": total_sdk,
            "total_api_endpoints": total_api,
            "sdk_modules": len(sdk_modules),
            "api_modules": len(api_modules),
            "modules_without_sdk": len(modules_only_api),
            "modules_shared": len(modules_shared),
        },
        "per_module": gaps,
        "api_prefixes": api_prefixes,
        "sdk_modules_list": sorted(sdk_modules),
    }


def print_report(results: dict) -> None:
    """Print human-readable gap report."""
    s = results["summary"]
    print("SDK vs API Gap Matrix (283.2.1)\n")
    print(f"  SDK methods:     {s['total_sdk_methods']}")
    print(f"  API endpoints:   {s['total_api_endpoints']}")
    print(f"  SDK modules:     {s['sdk_modules']}")
    print(f"  API modules:     {s['api_modules']}")
    print(f"  No SDK coverage: {s['modules_without_sdk']} modules")
    print()

    print("  Per-Module Gap Summary:")
    for module, info in sorted(results["per_module"].items()):
        bar = "█" * max(1, int(info.get("gap_pct", 0) / 5))
        status = info["status"]
        print(
            f"    {module:25s} SDK={info['sdk_methods']:3d}  API={info['api_endpoints']:3d}  "
            f"gap={info['gap_pct']:5.1f}%  {bar}  [{status}]"
        )

    print(f"\n  SDK-covered modules: {', '.join(results['sdk_modules_list'])}")


def main():
    results = run_gap_analysis()

    if "--json" in sys.argv:
        print(json.dumps(results, indent=2, default=str))
    elif "--summary" in sys.argv:
        s = results["summary"]
        print(
            f"sdk={s['total_sdk_methods']} api={s['total_api_endpoints']} "
            f"no_sdk={s['modules_without_sdk']}"
        )
    else:
        print_report(results)


if __name__ == "__main__":
    main()
