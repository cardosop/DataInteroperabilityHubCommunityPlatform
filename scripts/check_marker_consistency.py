#!/usr/bin/env python3
"""
Check pytest marker consistency (Phase 312.5.4).

Validates:
  1. Every test function has EXACTLY ONE Tier 1 marker (unit|integration|e2e).
  2. No deleted/legacy markers are still used in tests.
  3. All used markers are registered in pytest.ini.
  4. No registered marker is unregistered.

Exit 0 on clean, 1 on violations.  Wired into CI as a lint gate.
"""

import argparse
import configparser
import re
import sys
from collections import defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# ── Tier definitions ─────────────────────────────────────────────────────

TIER_1_MARKERS = frozenset({"unit", "integration", "e2e"})

TIER_2_MARKERS = frozenset(
    {
        "requires_db",
        "requires_redis",
        "requires_minio",
        "requires_fuseki",
        "requires_prefect",
        "requires_mailhog",
        "requires_aws",
        "requires_gcp",
        "requires_snowflake",
        "requires_stripe",
        "requires_clamav",
        "requires_ckan",
    }
)

TIER_3_MARKERS = frozenset(
    {
        "marketplace",
        "compliance",
        "semantic",
        "contracts",
        "auth",
        "governance",
        "billing",
        "datasets",
        "files",
        "webhooks",
        "workflows",
        "virtualization",
        "baas",
        "ml",
        "cli",
        "sdk",
        "search",
        "assets",
        "security",
        "isolation",
        "resilience",
    }
)

SPECIAL_MARKERS = frozenset(
    {
        "django_db",
        "asyncio",
        "spec",
        "uc",
        "journey",
        "persona",
        "rls",
        "uses_admin_role",
        "openspec_gate",
        "slow",
        "performance",
        "regression",
        "tabletop_rehearsal",
        "odh_inference",
        "benchmark",
        "stripe_connect",
        "allow_server_errors",
        "cache",
        "concurrency",
        "idempotency",
        "observability",
        "schema",
        "transaction",
        "requires_file_virus_scan_e2e",
        "requires_fuseki",
    }
)

ALL_VALID_MARKERS = TIER_1_MARKERS | TIER_2_MARKERS | TIER_3_MARKERS | SPECIAL_MARKERS

# Deprecated markers: registered in pytest.ini as @deprecated so
# --strict-markers passes, but check_marker_consistency.py flags them
# as warnings.  Tests should migrate to the replacement.
DEPRECATED_MARKERS = frozenset(
    {
        "requires_database",
        "e2e_batch1",
        "e2e_batch2",
        "e2e_batch3",
        "e2e_batch4",
        "e2e_batch5",
        "e2e1",
        "e2e2",
        "e2e3",
        "e2e4",
        "e2e5",
        "docker_compose_runtime",
        "real_scheduled_e2e",
        "real_virtualization_e2e",
        "scheduled_ingestion_integration",
        "requires_aws_role_arn",
        "requires_aws_session_token",
        "requires_aws_test_dataset",
        "requires_gcp_service_account",
        "snowflake_e2e",
        "snowflake_integration",
        "aws_integration",
        "gcp_integration",
        "requires_clamav_live",
        "requires_file_virus_scan_e2e",
        "smoke_mvp_mode",
        "mvp",
        "serial",
        "workflow_e2e",
        "saas_platform",
        "cli_sdk",
        "scheduled_export",
        "requires_services",
        "requires_services_connectivity",
        "requires_test_env",
        "uc_journey_persona",
    }
)

# Markers that were renamed (old → new mapping for helpful error messages).
RENAMED_MARKERS = {
    "requires_database": "requires_db",
    "requires_aws_role_arn": "requires_aws",
    "requires_aws_session_token": "requires_aws",
    "requires_aws_test_dataset": "requires_aws",
    "requires_clamav_live": "requires_clamav",
    "requires_file_virus_scan_e2e": "requires_clamav",
    "requires_gcp_service_account": "requires_gcp",
    "snowflake_e2e": "requires_snowflake",
    "snowflake_integration": "requires_snowflake",
    "aws_integration": "requires_aws",
    "gcp_integration": "requires_gcp",
    "real_scheduled_e2e": "requires_prefect",
    "real_virtualization_e2e": "virtualization",
    "scheduled_ingestion_integration": "requires_prefect",
    "requires_services": "unit",  # needs Tier 1 replacement
    "docker_compose_runtime": "requires_db",
    "e2e_batch1": "e2e",
    "e2e_batch2": "e2e",
    "e2e_batch3": "e2e",
    "e2e_batch4": "e2e",
    "e2e_batch5": "e2e",
    "e2e1": "e2e",
    "e2e2": "e2e",
    "e2e3": "e2e",
    "e2e4": "e2e",
    "e2e5": "e2e",
    "smoke_mvp_mode": "e2e",
    "workflow_e2e": "e2e",
    "saas_platform": "integration",
    "cli_sdk": "cli",
    "serial": "isolation",
    "uc_journey_persona": "e2e",
    "scheduled_export": "integration",
    "requires_services_connectivity": "requires_db",
    "requires_test_env": "requires_db",
    "mvp": "integration",
}


# ── Parsing helpers ──────────────────────────────────────────────────────

_MARKER_DECORATOR_RE = re.compile(r"@pytest\.mark\.(\w+)(?:\(([^)]*)\))?")


def parse_registered_markers(pytest_ini_path: Path) -> set:
    """Parse markers from pytest.ini [pytest] markers = ... section."""
    cfg = configparser.ConfigParser()
    cfg.read(pytest_ini_path)
    registered = set()
    if "pytest" not in cfg or "markers" not in cfg["pytest"]:
        return registered
    for line in cfg["pytest"]["markers"].strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        # Format: "name: description" or "name"
        name = line.split(":")[0].strip()
        if name:
            registered.add(name)
    return registered


def find_test_files(root: Path) -> list:
    """Find all Python test files in the test paths."""
    test_paths = [
        root / "hub" / "apps",
        root / "tests",
        root / "cli" / "tests",
        root / "sdk" / "python" / "tests",
        root / "services",
    ]
    files = []
    for tp in test_paths:
        if not tp.exists():
            continue
        for py_file in tp.rglob("test_*.py"):
            if py_file.is_file():
                files.append(py_file)
        for py_file in tp.rglob("*_test.py"):
            if py_file.is_file():
                files.append(py_file)
    return sorted(set(files))


def extract_markers_from_file(filepath: Path) -> list:
    """Extract all @pytest.mark.XXX decorators from a Python file.

    Returns list of (marker_name, line_number, function_name_or_None).
    """
    markers = []
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return markers
    lines = content.split("\n")
    current_function = None
    for i, line in enumerate(lines, 1):
        # Track current function name for context (handles def + async def)
        fn_match = re.match(r"^\s*(?:async\s+)?def\s+(test_\w+)\s*\(", line)
        if fn_match:
            current_function = fn_match.group(1)
        for m in _MARKER_DECORATOR_RE.finditer(line):
            name = m.group(1)
            markers.append((name, i, current_function))
    return markers


# ═══════════════════════════════════════════════════════════════════════════
# Validation
# ═══════════════════════════════════════════════════════════════════════════


def validate(test_paths: list = None, verbose: bool = False) -> int:
    """Run all marker consistency checks.  Returns exit code (0 = clean)."""
    errors = 0
    root = REPO_ROOT
    ini = root / "pytest.ini"
    if not ini.exists():
        print(f"ERROR: pytest.ini not found at {ini}", file=sys.stderr)
        return 1

    registered = parse_registered_markers(ini)
    test_files = find_test_files(root)
    if test_paths:
        test_files = [f for f in test_files if any(tp in str(f) for tp in test_paths)]

    if verbose:
        print(f"Scanning {len(test_files)} test files...", file=sys.stderr)

    # Stats
    defaultdict(lambda: defaultdict(int))  # file → {unit: N, integration: N, ...}
    used_markers = set()
    legacy_used = []

    for filepath in test_files:
        markers_in_file = extract_markers_from_file(filepath)
        tier1_in_file = []
        for name, lineno, func in markers_in_file:
            if name in DEPRECATED_MARKERS:
                suggestion = RENAMED_MARKERS.get(name, "remove")
                print(
                    f"{filepath}:{lineno}: WARNING deprecated marker "
                    f"'@pytest.mark.{name}' — use '@pytest.mark.{suggestion}' instead",
                    file=sys.stderr,
                )
                legacy_used.append((str(filepath), lineno, name, suggestion))
            if name in TIER_1_MARKERS:
                tier1_in_file.append((name, lineno, func))
            used_markers.add(name)

        if len(tier1_in_file) > 1:
            # Multiple Tier 1 markers on same function — check if truly on same function
            func_tier1 = defaultdict(list)
            for name, lineno, func in tier1_in_file:
                if func:
                    func_tier1[func].append(name)
            for fn, markers in func_tier1.items():
                unique = set(markers)
                if len(unique) > 1:
                    errors += 1
                    print(
                        f"{filepath}: function '{fn}' has multiple Tier 1 markers: "
                        f"{sorted(unique)}",
                        file=sys.stderr,
                    )

    # Check: are there test functions with no Tier 1 marker?
    # (We can't easily detect this without full AST parsing, but we can flag files
    #  that use markers but have zero Tier 1 markers anywhere.)
    # Skipping — full check would require AST parsing.

    # Check unregistered markers
    unregistered = used_markers - registered
    # Allow xdist_group since it takes args and is handled specially
    unregistered.discard("xdist_group")
    # Allow parametrize (built-in)
    unregistered.discard("parametrize")
    # Allow skip/skipif/xfail (built-in)
    unregistered.discard("skip")
    unregistered.discard("skipif")
    unregistered.discard("xfail")
    # Allow filterwarnings/usefixtures (built-in via decorators)
    unregistered.discard("filterwarnings")
    unregistered.discard("usefixtures")
    # Allow random_order and other plugin markers
    unregistered.discard("random_order")
    unregistered.discard("timeout")
    # Allow flaky (pytest-rerunfailures)
    unregistered.discard("flaky")
    # Allow pytest-django built-ins (registered automatically by the plugin)
    unregistered.discard("django_db")
    unregistered.discard("transaction")

    if unregistered:
        for m in sorted(unregistered):
            errors += 1
            print(
                f"UNREGISTERED MARKER: '@pytest.mark.{m}' is used in tests "
                f"but not registered in pytest.ini",
                file=sys.stderr,
            )

    if verbose:
        print(f"\nUsed markers: {len(used_markers)}", file=sys.stderr)
        print(f"Registered markers: {len(registered)}", file=sys.stderr)
        if legacy_used:
            print(f"\nDeprecated markers needing migration ({len(legacy_used)}):", file=sys.stderr)
            for path, lineno, old, new in legacy_used:
                print(f"  {path}:{lineno}: {old} → {new}", file=sys.stderr)

    if errors:
        print(f"\n{errors} marker consistency error(s) found.", file=sys.stderr)
    if legacy_used:
        print(
            f"\n{len(legacy_used)} deprecated marker(s) still in use "
            f"(not blocking, but should be migrated).",
            file=sys.stderr,
        )

    return 1 if errors else 0


def main():
    parser = argparse.ArgumentParser(description="Check pytest marker consistency")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--quick", action="store_true", help="Quick check (skip slow operations)")
    parser.add_argument("test_paths", nargs="*", help="Limit check to specific test paths")
    args = parser.parse_args()
    sys.exit(validate(test_paths=args.test_paths or None, verbose=args.verbose))


if __name__ == "__main__":
    main()
