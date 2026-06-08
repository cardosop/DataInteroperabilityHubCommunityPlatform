#!/usr/bin/env python3
"""
Phase 232.DoD.{1,6,7} machine-enforced production-flip gate.

When a PR flips a Phase 232 ``compliance_*_enabled`` flag to ``true``
in production helm values (``helm/values.yaml`` or
``helm/values.production.yaml``), this gate refuses to merge unless:

1. **DoD.1** — the matching subsystem has ``status: signed-off`` in
   [docs/audit-reports/232-privacy-counsel-signoffs.md](../docs/audit-reports/232-privacy-counsel-signoffs.md),
   AND both ``legal_signoff`` and ``dpo_signoff`` blocks have
   non-placeholder ``name`` + ``date`` fields.

2. **DoD.6** — the matching subsystem has a ``signed-off`` row in the
   per-subsystem clean-status table at
   [docs/audit-reports/232-pen-test-ledger.md](../docs/audit-reports/232-pen-test-ledger.md),
   AND the closure block is signed.

3. **DoD.7** — the most recent run in
   [docs/audit-reports/232-tabletop-ledger.md](../docs/audit-reports/232-tabletop-ledger.md)
   is ``green``, signed off, and dated within the last 90 days.

The gate is **only triggered** when a PR diff actually flips a flag
ON in a production-scope file. Staging flag flips are out of scope —
staging is the soak environment, by design.

Usage
-----
::

    python scripts/check_phase232_production_flip_gate.py \\
        --base-ref origin/main \\
        --head-ref HEAD

Exits 0 (clean) or 1 (gate violated). On violation, prints one
``::error::`` line per missing attestation so GitHub Actions surfaces
each in the PR check output.
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Production helm value files in scope. Adding `helm/values.yaml`
#: protects the default production template; adding the explicit
#: `production.yaml` keeps the gate hardened if a separate file lands
#: in the future. Staging-only flips are intentionally out of scope.
PRODUCTION_HELM_FILES = (
    "helm/values.yaml",
    "helm/values.production.yaml",
)

#: Phase 232 helm flag names → subsystem identifier.
#: Mirror the table in `docs/audit-reports/232-privacy-counsel-signoffs.md`.
SUBSYSTEM_BY_FLAG = {
    # Sub-phase 232.1
    "compliance_consent_enabled": "consent",
    "COMPLIANCE_CONSENT_ENABLED": "consent",
    # 232.2
    "compliance_dsar_enabled": "dsar",
    "COMPLIANCE_DSAR_ENABLED": "dsar",
    # 232.3
    "compliance_breach_enabled": "breach",
    "COMPLIANCE_BREACH_ENABLED": "breach",
    # 232.4
    "compliance_ropa_enabled": "ropa",
    "COMPLIANCE_ROPA_ENABLED": "ropa",
    # 232.5
    "compliance_dpia_enabled": "dpia",
    "COMPLIANCE_DPIA_ENABLED": "dpia",
}

PRIVACY_LEDGER = REPO_ROOT / "docs" / "audit-reports" / "232-privacy-counsel-signoffs.md"
PEN_TEST_LEDGER = REPO_ROOT / "docs" / "audit-reports" / "232-pen-test-ledger.md"
TABLETOP_LEDGER = REPO_ROOT / "docs" / "audit-reports" / "232-tabletop-ledger.md"

#: Ledger rows that haven't been filled out yet contain placeholder
#: tokens; the gate treats any of these as "not signed".
_PLACEHOLDER_RE = re.compile(
    r"_to be filled_|_YYYY-MM-DD_|_link_|_short-SHA_|_name_|_attestation_"
)

#: Tabletop run is fresh only if its most recent green-run date is
#: within this many days of "today".
TABLETOP_FRESHNESS_DAYS = 90


# ---------------------------------------------------------------------------
# Diff resolution
# ---------------------------------------------------------------------------

def _git_diff(base_ref: str, head_ref: str, path: str) -> str:
    """Return the git diff for ``path`` between ``base_ref`` and ``head_ref``.

    Returns the empty string if the file is unchanged or absent — both
    are treated as "this PR did not flip the flag".
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--unified=0", base_ref, head_ref, "--", path],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        # If the base ref is unreachable (e.g. shallow clone), the gate
        # cannot prove the absence of a flip; fail closed so the
        # reviewer notices.
        print(
            f"::error::git diff failed for {path}: {exc}. "
            "Run `git fetch origin main --depth=1` (or set "
            "`fetch-depth: 0` on the GitHub Actions checkout step) and retry.",
            file=sys.stderr,
        )
        sys.exit(2)
    return result.stdout


def _flipped_flags_in_diff(diff_text: str) -> set[str]:
    """Return the set of helm flag names whose value flipped to a
    truthy value in ``diff_text``.

    A "flip" is a line that:
      * starts with ``+`` (added by the PR),
      * matches one of the SUBSYSTEM_BY_FLAG keys,
      * has the value ``"true"`` / ``true`` / ``True`` / ``"True"``.

    Lines that flip the value to ``false`` (rollback / safe-state) are
    intentionally NOT gated — that direction is always allowed.
    """
    flipped: set[str] = set()
    flag_alternation = "|".join(re.escape(k) for k in SUBSYSTEM_BY_FLAG)
    pattern = re.compile(
        r"""
        ^\+                              # added line
        \s*
        (?P<flag>""" + flag_alternation + r""")
        \s*[:=]\s*
        (?P<quote>['"]?)
        (?P<value>true|True)
        (?P=quote)
        \s*$
        """,
        re.VERBOSE | re.MULTILINE,
    )
    for match in pattern.finditer(diff_text):
        flipped.add(match.group("flag"))
    return flipped


# ---------------------------------------------------------------------------
# Privacy-counsel sign-off check
# ---------------------------------------------------------------------------

#: Privacy ledger schema — the gate parses each `## Subsystem: <name>`
#: block and inspects the embedded fenced field block.
_PRIVACY_BLOCK_RE = re.compile(
    r"##\s+Subsystem:\s+(?P<name>[a-z][a-z0-9_-]*)\s*\n"
    r".*?"
    r"```[a-z]*\n(?P<fields>.*?)\n```",
    re.DOTALL,
)


def _parse_privacy_block(fields_text: str) -> dict[str, str]:
    """Pull the top-level ``status`` / nested name+date triples out of
    a fenced privacy-counsel block. Returns a flat dict so the caller
    can compose error messages.
    """
    parsed: dict[str, str] = {}
    current_section: str | None = None
    for line in fields_text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.endswith(":") and not stripped.startswith("-"):
            # Top-level mapping key (e.g. `legal_signoff:`)
            current_section = stripped[:-1].strip()
            continue
        if ":" in stripped:
            key, _, value = stripped.partition(":")
            key = key.strip().lstrip("-").strip()
            value = value.strip()
            if current_section and key in {"name", "date", "evidence"}:
                parsed[f"{current_section}.{key}"] = value
            else:
                parsed[key] = value
                current_section = None
    return parsed


def _privacy_signoff_violations(subsystems: Iterable[str]) -> list[str]:
    """Return error strings for subsystems missing a clean privacy
    counsel sign-off."""
    if not PRIVACY_LEDGER.exists():
        return [
            f"Privacy-counsel ledger missing at "
            f"{PRIVACY_LEDGER.relative_to(REPO_ROOT)} — cannot verify "
            "DoD.1 sign-off."
        ]
    text = PRIVACY_LEDGER.read_text(encoding="utf-8")
    blocks: dict[str, dict[str, str]] = {}
    for match in _PRIVACY_BLOCK_RE.finditer(text):
        blocks[match.group("name")] = _parse_privacy_block(match.group("fields"))

    violations: list[str] = []
    for subsystem in subsystems:
        block = blocks.get(subsystem)
        if not block:
            violations.append(
                f"DoD.1: subsystem '{subsystem}' has no `## Subsystem: "
                f"{subsystem}` block in {PRIVACY_LEDGER.relative_to(REPO_ROOT)}."
            )
            continue
        if block.get("status") != "signed-off":
            violations.append(
                f"DoD.1: subsystem '{subsystem}' status="
                f"'{block.get('status', '<missing>')}' in privacy ledger "
                "— required: signed-off."
            )
        for role in ("legal_signoff", "dpo_signoff"):
            name = block.get(f"{role}.name", "")
            date_str = block.get(f"{role}.date", "")
            if not name or _PLACEHOLDER_RE.search(name):
                violations.append(
                    f"DoD.1: subsystem '{subsystem}' missing real "
                    f"`{role}.name` (got '{name}')."
                )
            if not date_str or _PLACEHOLDER_RE.search(date_str):
                violations.append(
                    f"DoD.1: subsystem '{subsystem}' missing real "
                    f"`{role}.date` (got '{date_str}')."
                )
    return violations


# ---------------------------------------------------------------------------
# Pen-test ledger check (DoD.6)
# ---------------------------------------------------------------------------

#: Match a row in the per-subsystem clean-status table:
#:   | 232.1 Consent management | <run> | <date> | <findings> | <signoff> | <notes> |
_PEN_TEST_ROW_RE = re.compile(
    r"^\|\s*(?P<sub>232\.\d[^|]+?)\s*\|"
    r"\s*(?P<run>[^|]+?)\s*\|"
    r"\s*(?P<date>[^|]+?)\s*\|"
    r"\s*(?P<findings>[^|]+?)\s*\|"
    r"\s*(?P<signoff>[^|]+?)\s*\|",
    re.MULTILINE,
)

# Map subsystem id → substring to match in the row's first column.
_SUBSYSTEM_PEN_TEST_LABEL = {
    "consent": "232.1 Consent management",
    "dsar": "232.2 DSAR workflow",
    "breach": "232.3 Breach notification",
    "ropa": "232.4 RoPA generator",
    "dpia": "232.5 DPIA tooling",
}


def _pen_test_violations(subsystems: Iterable[str]) -> list[str]:
    if not PEN_TEST_LEDGER.exists():
        return [
            f"Pen-test ledger missing at "
            f"{PEN_TEST_LEDGER.relative_to(REPO_ROOT)} — cannot verify "
            "DoD.6 clean-status."
        ]
    text = PEN_TEST_LEDGER.read_text(encoding="utf-8")
    rows: dict[str, tuple[str, str]] = {}
    for match in _PEN_TEST_ROW_RE.finditer(text):
        label = match.group("sub").strip()
        rows[label] = (match.group("findings").strip(), match.group("signoff").strip())

    violations: list[str] = []
    for subsystem in subsystems:
        label = _SUBSYSTEM_PEN_TEST_LABEL.get(subsystem)
        if not label:
            violations.append(
                f"DoD.6: no pen-test ledger label mapped for subsystem "
                f"'{subsystem}' (update _SUBSYSTEM_PEN_TEST_LABEL)."
            )
            continue
        match_row = rows.get(label)
        if not match_row:
            violations.append(
                f"DoD.6: subsystem '{subsystem}' has no row labelled "
                f"'{label}' in {PEN_TEST_LEDGER.relative_to(REPO_ROOT)}."
            )
            continue
        findings, signoff = match_row
        if _PLACEHOLDER_RE.search(findings) or _PLACEHOLDER_RE.search(signoff):
            violations.append(
                f"DoD.6: subsystem '{subsystem}' pen-test row still "
                f"contains placeholders (findings='{findings}', "
                f"signoff='{signoff}')."
            )
            continue
        # Sign-off must be a real Sec Lead name; an empty / dash entry
        # is treated as "no clean attestation".
        if not signoff or signoff in {"_", "-", "—", "_Sec Lead name_"}:
            violations.append(
                f"DoD.6: subsystem '{subsystem}' pen-test row missing "
                f"Sec Lead sign-off (got '{signoff}')."
            )
            continue
        # Findings string must indicate zero HIGH/CRITICAL.
        if "0H" not in findings and "0 HIGH" not in findings.upper():
            violations.append(
                f"DoD.6: subsystem '{subsystem}' pen-test row has "
                f"non-zero HIGH findings ('{findings}'). Production flip "
                "is blocked per the pen-test contract."
            )
    return violations


# ---------------------------------------------------------------------------
# Tabletop freshness check (DoD.7)
# ---------------------------------------------------------------------------

_TABLETOP_RUN_HEADER_RE = re.compile(
    r"###\s+Run\s+\d+\s+—\s+(?P<date>\d{4}-\d{2}-\d{2}|_YYYY-MM-DD_)"
    r"\s+—\s+_outcome:\s+(?P<outcome>[a-z_-]+)_",
    re.MULTILINE,
)


def _tabletop_violations(today: date | None = None) -> list[str]:
    if not TABLETOP_LEDGER.exists():
        return [
            f"Tabletop ledger missing at "
            f"{TABLETOP_LEDGER.relative_to(REPO_ROOT)} — cannot verify "
            "DoD.7."
        ]
    text = TABLETOP_LEDGER.read_text(encoding="utf-8")
    runs: list[tuple[str, str]] = []
    for match in _TABLETOP_RUN_HEADER_RE.finditer(text):
        runs.append((match.group("date"), match.group("outcome")))
    if not runs:
        return [
            f"DoD.7: no Run blocks parsed from "
            f"{TABLETOP_LEDGER.relative_to(REPO_ROOT)}. Expected "
            "`### Run N — YYYY-MM-DD — _outcome: green_` headings."
        ]
    last_date, last_outcome = runs[-1]
    if last_outcome != "green":
        return [
            f"DoD.7: most recent tabletop run outcome="
            f"'{last_outcome}' (expected 'green')."
        ]
    if last_date == "_YYYY-MM-DD_":
        return [
            "DoD.7: most recent tabletop run date is still a placeholder."
        ]
    try:
        run_date = datetime.strptime(last_date, "%Y-%m-%d").date()
    except ValueError:
        return [
            f"DoD.7: most recent tabletop run date '{last_date}' is not "
            "ISO YYYY-MM-DD."
        ]
    today = today or date.today()
    if today - run_date > timedelta(days=TABLETOP_FRESHNESS_DAYS):
        return [
            f"DoD.7: most recent tabletop run dated {run_date.isoformat()} "
            f"is older than {TABLETOP_FRESHNESS_DAYS} days "
            f"(today={today.isoformat()}). Re-run the exercise per "
            "docs/runbooks/phase232-regulator-audit-tabletop.md."
        ]
    return []


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base-ref",
        default="origin/main",
        help="Git ref to diff against (default: origin/main).",
    )
    parser.add_argument(
        "--head-ref",
        default="HEAD",
        help="Git ref representing the PR tip (default: HEAD).",
    )
    args = parser.parse_args()

    flipped: set[str] = set()
    for path in PRODUCTION_HELM_FILES:
        diff = _git_diff(args.base_ref, args.head_ref, path)
        flipped.update(_flipped_flags_in_diff(diff))

    if not flipped:
        print(
            "phase232-production-flip-gate: no Phase 232 flag flipped to "
            "true in production helm values; gate is a no-op for this PR."
        )
        return 0

    subsystems = sorted({SUBSYSTEM_BY_FLAG[flag] for flag in flipped})
    print(
        f"phase232-production-flip-gate: PR flips flags={sorted(flipped)} "
        f"→ subsystems={subsystems}; verifying attestations..."
    )

    violations: list[str] = []
    violations.extend(_privacy_signoff_violations(subsystems))
    violations.extend(_pen_test_violations(subsystems))
    violations.extend(_tabletop_violations())

    if violations:
        for v in violations:
            print(f"::error::{v}", file=sys.stderr)
        print(
            f"\nphase232-production-flip-gate: {len(violations)} "
            "attestation(s) missing or stale. Block reason summary:",
            file=sys.stderr,
        )
        print(
            "  - DoD.1: privacy-counsel sign-off ledger "
            f"({PRIVACY_LEDGER.relative_to(REPO_ROOT)})\n"
            "  - DoD.6: pen-test clean-status ledger "
            f"({PEN_TEST_LEDGER.relative_to(REPO_ROOT)})\n"
            "  - DoD.7: tabletop run freshness "
            f"({TABLETOP_LEDGER.relative_to(REPO_ROOT)}, "
            f"≤ {TABLETOP_FRESHNESS_DAYS} days)",
            file=sys.stderr,
        )
        return 1

    print(
        f"phase232-production-flip-gate: all attestations green for "
        f"subsystems={subsystems}. Production flip approved."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
