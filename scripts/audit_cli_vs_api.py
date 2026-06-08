#!/usr/bin/env python3
"""
283.2.2 — CLI vs API Gap Matrix.

Audits every CLI command against the backend API surface and reports
which API prefixes are NOT yet exposed via CLI commands.

Produces a per-prefix gap report feeding Phase 3–5 work assignments.

Usage:
  python scripts/audit_cli_vs_api.py                 # human-readable
  python scripts/audit_cli_vs_api.py --json          # JSON for CI
  python scripts/audit_cli_vs_api.py --summary       # counts only
"""
import ast
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CLI_COMMANDS_DIR = PROJECT_ROOT / "cli" / "datahub_cli" / "commands"
HUB_URLS_DIR = PROJECT_ROOT / "hub"

# ── Extract CLI commands ──────────────────────────────────────────────────

def extract_cli_commands() -> dict[str, set[str]]:
    """Return {module: {command_name, ...}} for the CLI."""
    commands = defaultdict(set)
    if not CLI_COMMANDS_DIR.is_dir():
        return commands

    for py_file in sorted(CLI_COMMANDS_DIR.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        module = py_file.stem

        try:
            content = py_file.read_text()
        except Exception:
            continue

        # Find @click.command() decorated functions
        # Pattern: @click.command(...) \n def name(...)
        for m in re.finditer(
            r'@(?:click\.)?(?:group|command)\s*\([^)]*\)\s*\n\s*def\s+(\w+)',
            content,
        ):
            commands[module].add(m.group(1))

        # Also find @<group>.command() patterns
        for m in re.finditer(
            r'@(\w+)\.command\s*\([^)]*\)\s*\n\s*def\s+(\w+)',
            content,
        ):
            commands[module].add(m.group(2))

    return dict(commands)


# ── Extract API endpoints ─────────────────────────────────────────────────

def extract_api_endpoints() -> dict[str, set[str]]:
    """Return {prefix: {endpoint, ...}} from the backend API."""
    endpoints = defaultdict(set)

    for url_file in HUB_URLS_DIR.rglob("urls.py"):
        if "migrations" in str(url_file) or "__pycache__" in str(url_file):
            continue
        try:
            content = url_file.read_text()
        except Exception:
            continue

        for m in re.finditer(
            r'(?:path|re_path)\s*\(\s*["\']([^"\']+)["\']',
            content,
        ):
            pattern = m.group(1)
            rel = str(url_file.relative_to(PROJECT_ROOT))
            if "hub/apps/" in rel:
                app = rel.split("hub/apps/")[1].split("/")[0]
                endpoints[app].add(pattern)

    return dict(endpoints)


# ── Gap analysis ─────────────────────────────────────────────────────────

CLI_TO_API_MAP = {
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
    "health": "/health",
    "users": "/api/v1/users",
    "config": "/api/v1/config",
    "baas": "/api/v1/baas",
    "gdpr": "/api/v1/gdpr",
    "ml": "/api/v1/ml",
    "observability": "/api/v1/observability",
    "mesh": "/api/v1/mesh",
    "scheduled_export": "/api/v1/scheduled-export",
    "scheduled_ingestion": "/api/v1/scheduled-ingestion",
    "transformation": "/api/v1/transformation",
}


def run_gap_analysis() -> dict:
    """Run the full CLI vs API gap analysis."""
    cli_commands = extract_cli_commands()
    api_endpoints = extract_api_endpoints()

    total_cli = sum(len(v) for v in cli_commands.values())
    total_api = sum(len(v) for v in api_endpoints.values())

    cli_modules = set(cli_commands.keys())
    api_modules = set(api_endpoints.keys())

    modules_only_api = api_modules - cli_modules
    modules_only_cli = cli_modules - api_modules
    modules_shared = cli_modules & api_modules

    gaps = {}
    for module in sorted(modules_only_api):
        ep_count = len(api_endpoints.get(module, set()))
        gaps[module] = {
            "status": "NO_CLI_COVERAGE",
            "api_endpoints": ep_count,
            "cli_commands": 0,
            "gap_pct": 100,
        }

    for module in sorted(modules_shared):
        api_count = len(api_endpoints.get(module, set()))
        cli_count = len(cli_commands.get(module, set()))
        if api_count > 0:
            coverage_pct = min(100, (cli_count / api_count) * 100)
            gaps[module] = {
                "status": "COVERED" if cli_count >= api_count * 0.8 else "UNDER_COVERED",
                "api_endpoints": api_count,
                "cli_commands": cli_count,
                "gap_pct": round(100 - coverage_pct, 1),
            }

    return {
        "summary": {
            "total_cli_commands": total_cli,
            "total_api_endpoints": total_api,
            "cli_modules": len(cli_modules),
            "api_modules": len(api_modules),
            "modules_without_cli": len(modules_only_api),
            "modules_shared": len(modules_shared),
        },
        "per_module": gaps,
        "cli_modules_list": sorted(cli_modules),
        "cli_only_modules": sorted(modules_only_cli),
    }


def print_report(results: dict) -> None:
    """Print human-readable gap report."""
    s = results["summary"]
    print("CLI vs API Gap Matrix (283.2.2)\n")
    print(f"  CLI commands:    {s['total_cli_commands']}")
    print(f"  API endpoints:   {s['total_api_endpoints']}")
    print(f"  CLI modules:     {s['cli_modules']}")
    print(f"  API modules:     {s['api_modules']}")
    print(f"  No CLI coverage: {s['modules_without_cli']} modules")
    print()

    print("  Per-Module Gap Summary:")
    for module, info in sorted(results["per_module"].items()):
        bar = "█" * max(1, int(info.get("gap_pct", 0) / 5))
        print(f"    {module:25s} CLI={info['cli_commands']:3d}  API={info['api_endpoints']:3d}  "
              f"gap={info['gap_pct']:5.1f}%  {bar}  [{info['status']}]")

    print(f"\n  CLI-covered modules: {', '.join(results['cli_modules_list'])}")
    if results["cli_only_modules"]:
        print(f"  CLI-only (no API match): {', '.join(results['cli_only_modules'])}")


def main():
    results = run_gap_analysis()

    if "--json" in sys.argv:
        print(json.dumps(results, indent=2, default=str))
    elif "--summary" in sys.argv:
        s = results["summary"]
        print(f"cli={s['total_cli_commands']} api={s['total_api_endpoints']} "
              f"no_cli={s['modules_without_cli']}")
    else:
        print_report(results)


if __name__ == "__main__":
    main()
