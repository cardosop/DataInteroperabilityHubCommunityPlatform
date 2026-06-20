#!/usr/bin/env python3
"""
Phase 277.B.083 — CLI / SDK ↔ OpenAPI parity gate.

Extracts every API endpoint path from the CLI source, the Python SDK,
and the JavaScript SDK, then compares each set against the committed
OpenAPI YAML baseline.  Reports uncovered paths and stale references.

Usage:
    python scripts/lint_cli_sdk_openapi_parity.py
    python scripts/lint_cli_sdk_openapi_parity.py --json
    python scripts/lint_cli_sdk_openapi_parity.py --check openapi

Exit 0 = full coverage for requested checks.  Exit 1 = gaps found.

CI integration:
    The ``lint-cli-sdk-openapi-parity`` job in ci.yml runs this script
    on every PR touching hub/, cli/, or sdk/.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

# ── Path sets ────────────────────────────────────────────────────────────────

CLI_SRC = PROJECT_ROOT / "cli" / "datahub_cli"
PY_SDK_SRC = PROJECT_ROOT / "sdk" / "python" / "datahub_interoperability"
JS_SDK_SRC = PROJECT_ROOT / "sdk" / "js" / "src"
OPENAPI_YAML = PROJECT_ROOT / "docs" / "api" / "openapi.yaml"

# ── Regex: extract literal endpoint strings from HTTP client calls ───────────
#
# Matches patterns like:
#   api_client.get("assets/")
#   api_client.post(f"assets/{asset_id}/")
#   self.client.patch('contracts/{id}/')
#   this.client.delete(`assets/${id}/`)
#
# Group 1 captures the leading literal portion (before any interpolation).

_RE_CLI_PATH = re.compile(
    r"""api_client\.(?:get|post|patch|delete|put|request)\s*\(\s*(?:f?["'`])([^"'`{]+)""",
    re.MULTILINE,
)

_RE_PY_SDK_PATH = re.compile(
    r"""self\.client\.(?:get|post|patch|delete|put|request)\s*\(\s*(?:f?["'`])([^"'`{]+)""",
    re.MULTILINE,
)

_RE_JS_SDK_PATH = re.compile(
    r"""this\.client\.(?:get|post|patch|delete|put|request)\s*\(\s*(?:f?['"`])([^'"`{]+)""",
    re.MULTILINE,
)

# Additional pattern: f-string / template literal with interpolation
# Captures the leading literal part before the first {
_RE_CLI_FSTRING = re.compile(
    r"""api_client\.(?:get|post|patch|delete|put)\s*\(\s*f["']([^"'{]+)""",
    re.MULTILINE,
)
_RE_PY_FSTRING = re.compile(
    r"""self\.client\.(?:get|post|patch|delete|put)\s*\(\s*f["']([^"'{]+)""",
    re.MULTILINE,
)
_RE_JS_TEMPLATE = re.compile(
    r"""this\.client\.(?:get|post|patch|delete|put)\s*\(\s*`([^`${]+)""",
    re.MULTILINE,
)

# MVP-gated prefixes — these are expected to NOT have full CLI/SDK coverage
# and are excluded from the "missing from CLI/SDK" report.
_MVP_GATED_PREFIXES: set[str] = {
    "mesh/",
    "virtualization/",
    "integrations/",
    "baas/",
    "ml/",
    "ai/",
    "transformation/",
    "social/",
    "scheduled-ingestions/",
    "scheduled-exports/",
}

# Non-MVP but intentionally not in CLI/SDK (internal/health/system paths)
_EXCLUDED_PATH_PREFIXES: set[str] = {
    "admin/",  # Admin-only endpoints
    "internal/",  # Internal worker endpoints
    "health/",  # Health check endpoints
    "auth/",  # Auth endpoints (CLI has separate login flow, not per-path)
    "api-keys/",  # API key management (CLI config-managed)
    "sso/",  # SSO (browser-only)
}


def _load_openapi_paths() -> set[str]:
    """Parse the committed OpenAPI YAML and return the set of API paths.

    Paths are relative to /api/v1/ (the leading prefix is stripped).
    """
    if not OPENAPI_YAML.is_file():
        print(f"ERROR: OpenAPI YAML baseline not found at {OPENAPI_YAML}", file=sys.stderr)
        print("Run: python scripts/generate_openapi_yaml.py", file=sys.stderr)
        sys.exit(2)

    paths: set[str] = set()
    with open(OPENAPI_YAML) as f:
        for line in f:
            stripped = line.rstrip()
            # YAML paths section starts with lines like "  /api/v1/assets/:" or
            # "  /api/v1/assets/{id}/activate/:" (2-space indent).
            if stripped.startswith("  /api/v1/") and stripped.endswith(":"):
                path = stripped.strip().rstrip(":")
                # Strip /api/v1/ prefix for comparison with CLI/SDK paths
                rel = path[len("/api/v1/") :]
                paths.add(rel)
    return paths


def _extract_paths_from_source(
    src_dir: Path,
    primary_re: re.Pattern,
    fstring_re: re.Pattern,
) -> set[str]:
    """Walk *src_dir* and extract all API endpoint paths."""
    paths: set[str] = set()
    if not src_dir.is_dir():
        return paths

    for py_file in src_dir.rglob("*.py"):
        try:
            content = py_file.read_text(encoding="utf-8")
        except Exception:
            continue

        # Literal paths: "assets/", 'contracts/'
        for match in primary_re.finditer(content):
            raw = match.group(1).strip().rstrip("/")
            if raw and not raw.startswith(("http", "//", "#")):
                paths.add(raw + "/")

        # f-string / template paths: f"assets/{id}/"
        for match in fstring_re.finditer(content):
            raw = match.group(1).strip().rstrip("/")
            if raw and not raw.startswith(("http", "//", "#")):
                paths.add(raw + "{id}/")

    return paths


def _extract_js_paths(src_dir: Path) -> set[str]:
    """Extract API endpoint paths from TypeScript/JavaScript source files."""
    paths: set[str] = set()
    if not src_dir.is_dir():
        return paths

    for file in src_dir.rglob("*.ts"):
        try:
            content = file.read_text(encoding="utf-8")
        except Exception:
            continue

        # Literal: this.client.get('assets/')
        for match in _RE_JS_SDK_PATH.finditer(content):
            raw = match.group(1).strip().rstrip("/")
            if raw and not raw.startswith(("http", "//", "#")):
                paths.add(raw + "/")

        # Template literal: this.client.get(`assets/${id}/`)
        for match in _RE_JS_TEMPLATE.finditer(content):
            raw = match.group(1).strip().rstrip("/")
            if raw and not raw.startswith(("http", "//", "#")):
                paths.add(raw + "{id}/")

    return paths


def _normalize_sdk_path(path: str) -> str:
    """Normalize a path for comparison with OpenAPI paths.

    Replaces common variable names in f-strings with the Django URL
    pattern placeholder ``{id}``.
    """
    # Replace common variable interpolation patterns
    replacements = [
        (r"\{asset_id\}", "{id}"),
        (r"\{contract_id\}", "{id}"),
        (r"\{id\}", "{id}"),
        (r"\{key\}", "{id}"),
        (r"\{pk\}", "{id}"),
        (r"\{run_id\}", "{id}"),
        (r"\{job_id\}", "{id}"),
        (r"\{webhook_id\}", "{id}"),
        (r"\{user_id\}", "{id}"),
        (r"\{tenant_id\}", "{id}"),
        (r"\{dataset_id\}", "{id}"),
        (r"\{file_id\}", "{id}"),
        (r"\{model_id\}", "{id}"),
        (r"\{pipeline_id\}", "{id}"),
        (r"\{deployment_id\}", "{id}"),
        (r"\{listing_id\}", "{id}"),
        (r"\{order_id\}", "{id}"),
        (r"\{connection_id\}", "{id}"),
    ]
    result = path.rstrip("/") + "/"
    for pattern, replacement in replacements:
        result = re.sub(pattern, replacement, result)
    return result


def _is_mvp_gated(path: str) -> bool:
    """Return True if *path* is under an MVP-gated prefix."""
    return any(path.startswith(p) for p in _MVP_GATED_PREFIXES)


def _is_excluded(path: str) -> bool:
    """Return True if *path* is intentionally excluded from CLI/SDK coverage."""
    return any(path.startswith(p) for p in _EXCLUDED_PATH_PREFIXES)


def _should_report_missing(path: str) -> bool:
    """Return True if missing coverage for *path* should be reported."""
    return not _is_mvp_gated(path) and not _is_excluded(path)


def run_parity_check() -> dict:
    """Run the full CLI/SDK ↔ OpenAPI parity check.

    Returns a dict with coverage stats and lists of uncovered paths.
    """
    openapi_paths = _load_openapi_paths()

    cli_raw = _extract_paths_from_source(CLI_SRC, _RE_CLI_PATH, _RE_CLI_FSTRING)
    py_sdk_raw = _extract_paths_from_source(PY_SDK_SRC, _RE_PY_SDK_PATH, _RE_PY_FSTRING)
    js_sdk_raw = _extract_js_paths(JS_SDK_SRC)

    cli_paths = {_normalize_sdk_path(p) for p in cli_raw}
    py_sdk_paths = {_normalize_sdk_path(p) for p in py_sdk_raw}
    js_sdk_paths = {_normalize_sdk_path(p) for p in js_sdk_raw}

    # ── Coverage gaps ────────────────────────────────────────────────────
    openapi_missing_cli = sorted(
        p for p in openapi_paths if p not in cli_paths and _should_report_missing(p)
    )
    openapi_missing_py_sdk = sorted(
        p for p in openapi_paths if p not in py_sdk_paths and _should_report_missing(p)
    )
    openapi_missing_js_sdk = sorted(
        p for p in openapi_paths if p not in js_sdk_paths and _should_report_missing(p)
    )

    # ── Stale paths (in CLI/SDK but NOT in OpenAPI) ──────────────────────
    cli_extra = sorted(p for p in cli_paths if p not in openapi_paths and not _is_excluded(p))
    py_sdk_extra = sorted(p for p in py_sdk_paths if p not in openapi_paths and not _is_excluded(p))
    js_sdk_extra = sorted(p for p in js_sdk_paths if p not in openapi_paths and not _is_excluded(p))

    total_openapi = len(openapi_paths)
    reportable = sum(1 for p in openapi_paths if _should_report_missing(p))

    return {
        "openapi_total_paths": total_openapi,
        "openapi_reportable_paths": reportable,
        "cli_paths_found": len(cli_paths),
        "py_sdk_paths_found": len(py_sdk_paths),
        "js_sdk_paths_found": len(js_sdk_paths),
        "cli_missing": openapi_missing_cli,
        "py_sdk_missing": openapi_missing_py_sdk,
        "js_sdk_missing": openapi_missing_js_sdk,
        "cli_extra": cli_extra,
        "py_sdk_extra": py_sdk_extra,
        "js_sdk_extra": js_sdk_extra,
        "cli_coverage_pct": (
            round((1 - len(openapi_missing_cli) / reportable) * 100, 1) if reportable > 0 else 100.0
        ),
        "py_sdk_coverage_pct": (
            round((1 - len(openapi_missing_py_sdk) / reportable) * 100, 1)
            if reportable > 0
            else 100.0
        ),
        "js_sdk_coverage_pct": (
            round((1 - len(openapi_missing_js_sdk) / reportable) * 100, 1)
            if reportable > 0
            else 100.0
        ),
    }


def _print_human(result: dict) -> None:
    """Print human-readable parity report."""
    print("CLI / SDK ↔ OpenAPI Parity Report")
    print("=" * 72)
    print(f"  OpenAPI paths (total):       {result['openapi_total_paths']}")
    print(f"  OpenAPI paths (reportable):  {result['openapi_reportable_paths']}")
    print()
    print(f"  CLI paths extracted:         {result['cli_paths_found']}")
    print(f"  CLI coverage:                {result['cli_coverage_pct']}%")
    print(f"  CLI missing ({len(result['cli_missing'])}):")
    for p in result["cli_missing"]:
        print(f"    - {p}")
    if result["cli_extra"]:
        print(f"  CLI extra / stale ({len(result['cli_extra'])}):")
        for p in result["cli_extra"]:
            print(f"    - {p}")
    print()
    print(f"  Python SDK paths extracted:  {result['py_sdk_paths_found']}")
    print(f"  Python SDK coverage:         {result['py_sdk_coverage_pct']}%")
    print(f"  Python SDK missing ({len(result['py_sdk_missing'])}):")
    for p in result["py_sdk_missing"]:
        print(f"    - {p}")
    if result["py_sdk_extra"]:
        print(f"  Python SDK extra / stale ({len(result['py_sdk_extra'])}):")
        for p in result["py_sdk_extra"]:
            print(f"    - {p}")
    print()
    print(f"  JS SDK paths extracted:      {result['js_sdk_paths_found']}")
    print(f"  JS SDK coverage:             {result['js_sdk_coverage_pct']}%")
    print(f"  JS SDK missing ({len(result['js_sdk_missing'])}):")
    for p in result["js_sdk_missing"]:
        print(f"    - {p}")
    if result["js_sdk_extra"]:
        print(f"  JS SDK extra / stale ({len(result['js_sdk_extra'])}):")
        for p in result["js_sdk_extra"]:
            print(f"    - {p}")

    total_missing = (
        len(result["cli_missing"]) + len(result["py_sdk_missing"]) + len(result["js_sdk_missing"])
    )
    total_extra = (
        len(result["cli_extra"]) + len(result["py_sdk_extra"]) + len(result["js_sdk_extra"])
    )

    print()
    if total_missing == 0 and total_extra == 0:
        print("✓ All reportable OpenAPI paths are covered by CLI, Python SDK, and JS SDK.")
    else:
        if total_missing > 0:
            print(f"✗ {total_missing} uncovered path(s) across CLI/SDK.")
        if total_extra > 0:
            print(f"✗ {total_extra} stale/extra path(s) in CLI/SDK not in OpenAPI.")


def main() -> int:
    parser = argparse.ArgumentParser(description="CLI / SDK ↔ OpenAPI parity checker (277.B.083)")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results as JSON instead of human-readable.",
    )
    args = parser.parse_args()

    # Ensure we're running from the project root
    os.chdir(PROJECT_ROOT)

    result = run_parity_check()

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        _print_human(result)

    total_missing = (
        len(result["cli_missing"]) + len(result["py_sdk_missing"]) + len(result["js_sdk_missing"])
    )
    total_extra = (
        len(result["cli_extra"]) + len(result["py_sdk_extra"]) + len(result["js_sdk_extra"])
    )

    return 0 if (total_missing == 0 and total_extra == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
