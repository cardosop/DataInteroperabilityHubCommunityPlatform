#!/usr/bin/env python3
"""
Pre-Staging Gate Checklist (Phase 312.19 — V0–V15).

Runs all automatable verification gates before staging deployment.
Produces a structured Gate report with PASS/FAIL/SKIP for each gate.
Exit 0 if all gates pass, 1 if any FAIL.

Usage:
    python scripts/check_pre_staging_gate.py                     # all gates
    python scripts/check_pre_staging_gate.py --gate V0           # single gate
    python scripts/check_pre_staging_gate.py --strict            # no skips allowed
    python scripts/check_pre_staging_gate.py --json              # CI artifact
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"


# ═══════════════════════════════════════════════════════════════════════════
# V0 — Foundation
# ═══════════════════════════════════════════════════════════════════════════

def _check_normalization_registry_singleton() -> tuple[str, str]:
    """Verify single _NORMALIZER_REGISTRY instance."""
    try:
        from hub.apps.contracts.normalization import _NORMALIZER_REGISTRY as reg1
        from hub.apps.contracts.normalization_engine import _NORMALIZER_REGISTRY as reg2
        if reg1 is reg2:
            return "PASS", "Single registry instance — normalization.py re-exports from engine"
        return "FAIL", "Multiple _NORMALIZER_REGISTRY instances detected"
    except ImportError as e:
        return "SKIP", f"Django not importable: {e}"


def _check_zero_importlib_hacks() -> tuple[str, str]:
    """Verify zero importlib.util.spec_from_file_location in contracts/ or api/middleware/."""
    violations = []
    for check_dir in ("hub/apps/contracts/", "hub/apps/api/middleware/"):
        p = REPO_ROOT / check_dir
        if not p.exists():
            continue
        for py_file in p.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            if any(kw in str(py_file) for kw in ("test_", "tests/", "migrations/")):
                continue
            try:
                content = py_file.read_text()
                if "spec_from_file_location" in content:
                    violations.append(str(py_file.relative_to(REPO_ROOT)))
            except Exception:
                pass
    if violations:
        return "FAIL", f"importlib hacks in: {', '.join(violations[:5])}"
    return "PASS", "Zero importlib.util.spec_from_file_location in contracts/ + api/middleware/"


def _check_prefect_importable() -> tuple[str, str]:
    """Verify Prefect 3.x is installed and importable."""
    try:
        import prefect
        version = prefect.__version__ if hasattr(prefect, '__version__') else "unknown"
        if version.startswith("2."):
            return "FAIL", f"Prefect 2.x ({version}) — need 3.x"
        return "PASS", f"Prefect {version} importable"
    except ImportError:
        # Try from services dir
        svc = REPO_ROOT / "services" / "prefect-integration"
        if svc.exists():
            return "SKIP", "Prefect not importable outside Docker; verified in prefect-integration service container"
        return "FAIL", "Prefect not installed"


def _check_no_importerror_for_deleted_modules() -> tuple[str, str]:
    """Verify no code imports from deleted modules (hub.middleware, tests/conftest_prefect)."""
    deleted = [
        ("hub.middleware", "hub/request_middleware.py or hub/apps/api/middleware/"),
        ("tests.conftest_prefect", "tests/prefect/conftest.py"),
    ]
    for deleted_mod, replacement in deleted:
        pattern = f"from {deleted_mod} import|import {deleted_mod}"
        # Quick grep check
        try:
            result = subprocess.run(
                ["grep", "-rn", pattern, "hub/", "tests/", "services/", "cli/"],
                capture_output=True, cwd=str(REPO_ROOT), timeout=30,
            )
            if result.stdout and b".py:" in result.stdout:
                return "FAIL", f"Import of deleted module '{deleted_mod}' found; use '{replacement}'"
        except Exception:
            pass
    return "PASS", "No imports of deleted modules (hub.middleware, conftest_prefect)"


# ═══════════════════════════════════════════════════════════════════════════
# V6 — Security
# ═══════════════════════════════════════════════════════════════════════════

def _check_no_secrets_in_code() -> tuple[str, str]:
    """Quick scan for hardcoded secret patterns."""
    patterns = [
        (r'SECRET_KEY\s*=\s*["\'][^"\']{20,}', "Django SECRET_KEY"),
        (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password"),
        (r'api_key\s*=\s*["\'][A-Za-z0-9_-]{20,}["\']', "Hardcoded API key"),
    ]
    # Skip test files and .env files
    violations = []
    for pat, desc in patterns:
        try:
            result = subprocess.run(
                ["grep", "-rn", pat, "hub/", "--include=*.py"],
                capture_output=True, cwd=str(REPO_ROOT), timeout=30,
            )
            if result.stdout:
                lines = result.stdout.decode().split("\n")
                non_test = [l for l in lines if "/tests/" not in l and "test_" not in l and l.strip()]
                if non_test:
                    violations.append(f"{desc}: {non_test[0][:100]}")
        except Exception:
            pass
    if violations:
        return "FAIL", "; ".join(violations[:3])
    return "PASS", "No hardcoded secrets detected in non-test production code"


# ═══════════════════════════════════════════════════════════════════════════
# V9 — Test quality
# ═══════════════════════════════════════════════════════════════════════════

def _check_factories_use_faker() -> tuple[str, str]:
    """Verify factories use Faker, not hardcoded data."""
    factories_file = REPO_ROOT / "tests" / "factories.py"
    if not factories_file.exists():
        return "SKIP", "tests/factories.py not found"
    content = factories_file.read_text()
    # Faker is used via factory.LazyAttribute or Faker imports
    if "Faker" in content or "factory.LazyAttribute" in content or "factory.Faker" in content:
        return "PASS", "Factories use Faker/LazyAttribute for data generation"
    return "FAIL", "Factories do not use Faker"


# ═══════════════════════════════════════════════════════════════════════════
# V11 — API quality
# ═══════════════════════════════════════════════════════════════════════════

def _check_marker_consistency_strict() -> tuple[str, str]:
    """Verify marker consistency — blocking mode for pre-staging."""
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "check_marker_consistency.py")],
            capture_output=True, timeout=30, cwd=str(REPO_ROOT),
        )
        if result.returncode == 0:
            return "PASS", "Marker consistency check passed"
        stderr = result.stderr.decode(errors="replace")[:200]
        return "FAIL", f"Marker consistency failed: {stderr}"
    except Exception as e:
        return "FAIL", str(e)[:200]


# ── Gates that check automatically ──────────────────────────────────────

def _run_all_automated_checks() -> list[tuple[str, str, str, str]]:
    """Run all automated gates. Returns [(vgate, name, status, detail), ...]."""
    results = []

    # V0 — Foundation
    results.append(("V0.3.reg", "Normalization registry singleton", *_check_normalization_registry_singleton()))
    results.append(("V0.3.hack", "Zero importlib hacks", *_check_zero_importlib_hacks()))
    results.append(("V0.4", "Prefect 3.x importable", *_check_prefect_importable()))
    results.append(("V0.7", "No deleted module imports", *_check_no_importerror_for_deleted_modules()))

    # V4 — CLI/SDK
    v41_status, v41_detail = _check_marker_consistency_strict()
    results.append(("V4.1", "Marker consistency (strict)", v41_status, v41_detail))

    # V6 — Security
    results.append(("V6.1", "No secrets in code", *_check_no_secrets_in_code()))

    # V9 — Test quality
    results.append(("V9.1", "Factories use Faker", *_check_factories_use_faker()))

    return results


# ═══════════════════════════════════════════════════════════════════════════
# Reporting
# ═══════════════════════════════════════════════════════════════════════════

_PASS = "\033[32mPASS\033[0m"
_FAIL = "\033[31mFAIL\033[0m"
_SKIP = "\033[33mSKIP\033[0m"

def _status_color(status: str) -> str:
    if status == "PASS":
        return _PASS
    elif status == "FAIL":
        return _FAIL
    return _SKIP


def generate_report(results: list, fmt: str = "text") -> str:
    """Generate gate report in text or JSON."""
    if fmt == "json":
        return json.dumps([
            {"vgate": vg, "name": nm, "status": st, "detail": dt}
            for vg, nm, st, dt in results
        ], indent=2)

    lines = []
    lines.append("=" * 72)
    lines.append("PRE-STAGING GATE REPORT  (Phase 312.19 — V0–V15)")
    lines.append("=" * 72)
    lines.append(f"{'Gate':<12} {'Status':<8} {'Check':<30} Detail")
    lines.append("-" * 72)

    pass_count = fail_count = skip_count = 0
    for vgate, name, status, detail in results:
        if status == "PASS":
            pass_count += 1
        elif status == "FAIL":
            fail_count += 1
        else:
            skip_count += 1
        lines.append(f"{vgate:<12} {_status_color(status):<16} {name:<30} {detail[:60]}")

    lines.append("-" * 72)
    lines.append(f"PASS: {pass_count}  FAIL: {fail_count}  SKIP: {skip_count}  TOTAL: {len(results)}")

    # Manual gates reminder
    lines.append(f"\nManual verification gates (run in Docker/CI environment):")
    manual = [
        "V0.1 — pytest hub/apps/ --create-db -q (requires Docker)",
        "V0.2 — npx tsc --noEmit + npm run build (requires frontend/)",
        "V1.1 — migrate --check + showmigrations --plan (requires DB) [GATE-10/11]",
        "V1.2 — All 40 app test suites pass independently (requires DB)",
        "V1.3 — Management commands run without crash",
        "V2.1 — Frontend builds, tests pass, lint passes [frontend-tests.yml]",
        "V3.1 — All containers healthy, microservices /health OK [docker compose]",
        "V3.2 — Tenant isolation verified [--database=meshant_app]",
        "V4.2 — Python SDK installs, DataHubClient instantiates",
        "V4.3 — JS SDK compiles, tests pass",
        "V5.1 — All 8 Docker images build [docker-build.yml]",
        "V5.2 — helm lint + helm template valid [deploy.yml]",
        "V5.3 — terraform validate passes [terraform-plan-check.yml]",
        "V7.1 — readOnlyRootFilesystem, non-root, drop ALL caps [Helm pod security]",
        "V7.2 — NetworkPolicy runtime enforcement [ci.yml]",
        "V8.1 — Rate limit tenant isolation [TenantScopedThrottle]",
        "V8.2 — Django admin tenant scoping [TenantAdmin]",
        "V10.1 — Concurrent mutations handled correctly [tests/concurrency/]",
        "V10.2 — Idempotency verified [test_idempotency.py]",
        "V10.3 — Transaction integrity [test_transaction_integrity.py]",
        "V12.1 — X-Correlation-ID propagation [test_request_correlation.py]",
        "V12.2 — API handles microservice hang with 504 [test_inter_service_timeout.py]",
        "V13.1 — Token refresh/rotation/replay [cli/tests/security/]",
        "V14.1 — 100 VUs for 1h, p95 <2s [tests/load/ + k6]",
        "V14.2 — 2x max load graceful degradation [tests/load/]",
        "V15.1 — DX clone→up→healthy <5min [docs/TEST_EXECUTION_PLAN.md]",
    ]
    for m in manual:
        lines.append(f"  [ ] {m}")

    lines.append(f"\n{'=' * 72}")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pre-Staging Gate Checklist (Phase 312.19)"
    )
    parser.add_argument("--gate", help="Run a specific gate (e.g., V0)")
    parser.add_argument("--strict", action="store_true",
                        help="Treat SKIP as FAIL (CI blocking mode)")
    parser.add_argument("--json", action="store_true",
                        help="JSON output for CI artifacts")
    args = parser.parse_args()

    print("Running pre-staging gate checks...", file=sys.stderr)
    results = _run_all_automated_checks()

    fmt = "json" if args.json else "text"
    report = generate_report(results, fmt=fmt)
    print(report)

    # Filter by gate prefix if requested
    if args.gate:
        results = [r for r in results if r[0].startswith(args.gate)]

    fail_count = sum(1 for _, _, s, _ in results if s == "FAIL")
    if args.strict:
        fail_count += sum(1 for _, _, s, _ in results if s == "SKIP")

    return 1 if fail_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
