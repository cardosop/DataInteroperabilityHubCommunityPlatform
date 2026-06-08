#!/usr/bin/env python3
"""
TR.A.10 — CI lint rule for dual-channel E2E backend verification.

Checks that E2E feature spec files under ``frontend/e2e/features/``
include at least one ``verifyViaApi`` or ``verifyAuditEvent`` call.
New E2E spec files without backend verification get an informational
warning for the first 30 days, then the check becomes blocking.

Usage:
    python scripts/lint_e2e_backend_verification.py              # check all
    python scripts/lint_e2e_backend_verification.py --blocking    # fail on violation
    python scripts/lint_e2e_backend_verification.py --json        # JSON for CI
    python scripts/lint_e2e_backend_verification.py --since 7d   # only new/modified files
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

E2E_FEATURES_DIR = "frontend/e2e/features"
GRACE_PERIOD_DAYS = 30
BLOCKING_DATE = datetime(2026, 6, 20, tzinfo=timezone.utc)  # 30 days from now

REQUIRED_PATTERNS = [
    re.compile(r"\bverifyViaApi\b"),
    re.compile(r"\bverifyAuditEvent\b"),
    re.compile(r"\bverifySemantic\b"),
]

# Specs that are exempt (infrastructure, helpers, non-feature tests)
EXEMPT_FILES = {
    "accessibility.spec.ts",  # a11y tests, not feature-specific
}


def _git_modified_files(repo_root: Path, since_days: int | None) -> list[str]:
    """Return recently modified E2E spec files."""
    if since_days is None:
        return []
    since_date = (datetime.now(timezone.utc) - timedelta(days=since_days)).strftime(
        "%Y-%m-%d"
    )
    result = subprocess.run(
        [
            "git", "-C", str(repo_root), "log",
            f"--since={since_date}",
            "--name-only", "--pretty=format:",
            "--", f"{E2E_FEATURES_DIR}/*.spec.ts",
        ],
        text=True, capture_output=True,
    )
    return sorted(set(
        line.strip() for line in result.stdout.splitlines()
        if line.strip().endswith(".spec.ts")
    ))


def _find_spec_files(repo_root: Path) -> list[str]:
    """Find all E2E feature spec files."""
    features_dir = repo_root / E2E_FEATURES_DIR
    if not features_dir.is_dir():
        return []
    return sorted(
        f.name for f in features_dir.glob("*.spec.ts")
        if f.name not in EXEMPT_FILES
    )


def _has_verification(filepath: Path) -> bool:
    """Check if a spec file contains at least one verification call."""
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return False
    return any(pat.search(content) for pat in REQUIRED_PATTERNS)


def run_lint(
    repo_root: Path,
    blocking: bool = False,
    json_output: bool = False,
    since_days: int | None = None,
) -> int:
    """Run the lint check. Returns exit code."""
    spec_files = _find_spec_files(repo_root)

    # If --since is specified, only check recently modified files
    if since_days is not None:
        modified = _git_modified_files(repo_root, since_days)
        modified_basenames = {os.path.basename(f) for f in modified}
        spec_files = [f for f in spec_files if f in modified_basenames]
        if not spec_files:
            if json_output:
                print(json.dumps({"status": "ok", "message": "No recently modified spec files"}))
            else:
                print("No recently modified E2E spec files to check.")
            return 0

    missing: list[str] = []
    covered: list[str] = []

    for fname in spec_files:
        filepath = repo_root / E2E_FEATURES_DIR / fname
        if _has_verification(filepath):
            covered.append(fname)
        else:
            missing.append(fname)

    now = datetime.now(timezone.utc)
    is_blocking = blocking or now >= BLOCKING_DATE

    if json_output:
        print(json.dumps({
            "status": "fail" if (missing and is_blocking) else ("warn" if missing else "ok"),
            "total": len(spec_files),
            "covered": len(covered),
            "missing": len(missing),
            "blocking": is_blocking,
            "missing_files": missing,
            "covered_files": covered,
        }, indent=2))
    else:
        print(f"E2E Backend Verification Check")
        print(f"  Total spec files: {len(spec_files)}")
        print(f"  With verification: {len(covered)}")
        print(f"  Missing verification: {len(missing)}")
        if is_blocking:
            print(f"  Mode: BLOCKING (fail on violation)")
        else:
            print(f"  Mode: INFORMATIONAL (until {BLOCKING_DATE.strftime('%Y-%m-%d')})")

        if missing:
            print(f"\n  Files missing backend verification:")
            for f in missing:
                print(f"    - {f}")
            print(f"\n  Add verifyViaApi, verifyAuditEvent, or verifySemantic to these files.")
            print(f"  Import from '../fixtures/verifyBackend'.")

    if missing and is_blocking:
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="TR.A.10 — E2E backend verification lint")
    parser.add_argument(
        "--repo-root", type=Path, default=Path.cwd(),
        help="Repository root path.",
    )
    parser.add_argument(
        "--blocking", action="store_true", default=False,
        help="Exit non-zero on violation (default: informational).",
    )
    parser.add_argument(
        "--json", action="store_true", default=False,
        help="Output results as JSON.",
    )
    parser.add_argument(
        "--since", type=int, default=None,
        help="Only check files modified in last N days.",
    )
    args = parser.parse_args()

    return run_lint(
        repo_root=args.repo_root,
        blocking=args.blocking,
        json_output=args.json,
        since_days=args.since,
    )


if __name__ == "__main__":
    raise SystemExit(main())
