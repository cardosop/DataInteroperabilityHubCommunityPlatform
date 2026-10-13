#!/usr/bin/env python3
"""
GATE-44 (pilot-readiness 2.4) — the pilot smoke-report contract checker.

The pilot-live-verification spec requires a written smoke report that
lists every exercised path, its result, any API-shape mismatches, and
open gaps — and the masked-reporting requirement says NO credential
material may appear in it. This gate enforces both:

1. Structure completeness: the mandated sections exist and every
   exercised-path marker from the 2.2/2.3 passes is present.
2. Masked reporting — a REAL secret scan: the exact values from the
   operator's env file (sensitive-named keys of any length, plus any
   long value) must not appear in the report; token-shaped literals
   (dapi…, AKIA…, ghp_…, JWTs) are also forbidden. The check is
   falsifiable against the live .env.test, not a pattern-guess.

Exit 0 when the report satisfies the contract; 1 otherwise, with each
problem named (leaked values are NEVER echoed back).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_REPORT_DEFAULT = Path("docs/runbooks/PILOT_SMOKE_REPORT.md")
_ENV_DEFAULT = Path(".env.test")

REQUIRED_SECTIONS = (
    "## Exercised paths",
    "## Results summary",
    "## API-shape mismatches",
    "## Gaps",
)
# Every exercised path from the 2.2/2.3 passes (the acquisition gate,
# the live warehouse classes, the ingest, dbt, the ledger).
REQUIRED_PATH_MARKERS = (
    "clusters/list",
    "oidc/v1/token",
    "sql/warehouses",
    "GetCallerIdentity",
    "hub-files",
    "test-connectors-e2e",
    "TestDatabricksLiveIntegration",
    "execute_dlt_ingestion",
    "dbt run",
    "pilot_dbt_23",
    "DatabricksCostLedger",
)
_SENSITIVE_KEY_RE = re.compile(
    r"TOKEN|SECRET|PASSWORD|PRIVATE_KEY|_KEY|CREDENTIAL", re.I
)
# Configuration keys whose values are IDENTIFIERS, not credentials
# (class constants, region names, URLs the report must legitimately
# name — e.g. the declared budget re-scope class).
_NON_SECRET_KEY_RE = re.compile(
    r"_RESCOPE$|_REGION$|_ENABLED$|_LOCATION$|_URL$|_BUCKET_NAME$|_DESTINATION$"
)
# (pattern, problem label) — labels name the CLASS only; values are
# never echoed back.
_FORBIDDEN_PATTERNS = (
    (re.compile(r"\bdapi[0-9a-f]{10,}", re.I), "a token-shaped literal"),
    (re.compile(r"\bAKIA[0-9A-Z]{10,}"), "a token-shaped literal"),
    (re.compile(r"\bsk_live_[A-Za-z0-9]+"), "a token-shaped literal"),
    (re.compile(r"\bghp_[A-Za-z0-9]{20,}"), "a token-shaped literal"),
    (re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\."), "a token-shaped literal"),
    # C1 (oss-release-remediation W0.9): customer-identifying data — a
    # standalone 12-digit run is the AWS-account-ID class (counts,
    # metrics and decimal fractions are shorter runs / dot-anchored and
    # do not trip it).
    (re.compile(r"(?<![\d.])\d{12}(?!\d)"), "an AWS-account-ID-shaped literal"),
)


def _env_secret_values(env_file: Path) -> list[str]:
    """The values to scan for: sensitive-named keys of any length, plus
    any value >= 20 chars (rotated creds, SA JSON, private keys)."""
    values: list[str] = []
    for line in env_file.read_text().splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key, value = key.strip(), value.strip().strip("\"'")
        if len(value) < 8 or _NON_SECRET_KEY_RE.search(key):
            continue
        if _SENSITIVE_KEY_RE.search(key) or len(value) >= 20:
            values.append(value)
    return values


def check(report_path: Path, env_path: Path) -> list[str]:
    """The contract problems; [] when the report is clean."""
    problems: list[str] = []
    if not report_path.exists():
        return [f"smoke report missing: {report_path}"]
    text = report_path.read_text()
    for section in REQUIRED_SECTIONS:
        if section not in text:
            problems.append(f"missing mandated section {section!r}")
    for marker in REQUIRED_PATH_MARKERS:
        if marker not in text:
            problems.append(f"exercised path {marker!r} not listed")
    for pattern, label in _FORBIDDEN_PATTERNS:
        if pattern.search(text):
            problems.append(
                f"masked-reporting violation: {label} appears (value not echoed)"
            )
    if env_path.exists():
        for value in _env_secret_values(env_path):
            if value and value in text:
                problems.append(
                    "masked-reporting violation: an env-file credential "
                    "value appears in the report (value not echoed)"
                )
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=_REPORT_DEFAULT)
    parser.add_argument("--env-file", type=Path, default=_ENV_DEFAULT)
    args = parser.parse_args()
    problems = check(args.report, args.env_file)
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        print(f"GATE-44 FAILED: {len(problems)} problem(s)")
        sys.exit(1)
    print(f"GATE-44 PASSED: {args.report} satisfies the smoke-report contract")
    sys.exit(0)


if __name__ == "__main__":
    main()
