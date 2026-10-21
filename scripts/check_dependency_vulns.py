#!/usr/bin/env python3
"""
GATE-47 (pilot-readiness 4.2) — the dependency-vulnerability policy gate.

Policy (the recorded 4.2 decision): **block on MEDIUM+** — implemented
as "every pip-audit finding must be TRIAGED". The allowlist
(``.pip-audit-allowlist.yaml``) is the triage record: each entry names
the vuln id + package with a severity, a rationale, and a review date
(the ``.trivyignore`` Review-by convention). Consequences:

- a finding NOT in the allowlist blocks (exit 1) regardless of
  severity — an untriaged finding's severity is unknown, and unknown
  severity is treated as blocking (the MEDIUM+ floor);
- an allowlisted entry whose review date has passed blocks again
  (expired triage);
- the FULL triage list is printed — never truncated (the 4.2
  truncated-audit-log fix);
- LOW findings pass only when explicitly allowlisted with rationale.

Input: pip-audit's JSON output. When ``--audit-json`` is not given the
script runs ``pip-audit -r requirements.txt --format=json`` itself; if
pip-audit is not installed, the W16 environment policy applies (CI
raises, local skips with exit 0).

Usage:
    python scripts/check_dependency_vulns.py --strict          # CI gate
    python scripts/check_dependency_vulns.py --audit-json reports/pip-audit.json
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))  # envpolicy lives at the repo root

REQUIREMENTS_DEFAULT = Path("requirements.txt")
ALLOWLIST_DEFAULT = Path(".pip-audit-allowlist.yaml")


def _load_audit(audit_json: Path) -> tuple[list[str], dict[str, dict]]:
    """Return (problems, vulns) where vulns maps (id, package) -> row."""
    if not audit_json.exists():
        return [f"pip-audit JSON missing: {audit_json}"], {}
    try:
        data = json.loads(audit_json.read_text())
    except json.JSONDecodeError as exc:
        return [f"pip-audit JSON is malformed: {exc}"], {}
    vulns: dict[str, dict] = {}
    for dep in data.get("dependencies", []):
        for vuln in dep.get("vulns", []):
            vulns[f"{vuln.get('id')}:{dep.get('name')}"] = {
                "id": vuln.get("id"),
                "package": dep.get("name"),
                "version": dep.get("version"),
                "fix_versions": vuln.get("fix_versions", []),
            }
    return [], vulns


def _load_allowlist(path: Path) -> tuple[list[str], dict[str, dict]]:
    if not path.exists():
        return [f"allowlist missing: {path}"], {}
    try:
        import yaml
    except ImportError:
        return ["pyyaml is required to read the allowlist"], {}
    try:
        data = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        return [f"allowlist is malformed: {exc}"], {}
    entries: dict[str, dict] = {}
    for entry in data.get("allowlist", []):
        key = f"{entry.get('id')}:{entry.get('package')}"
        entries[key] = {
            "id": entry.get("id"),
            "package": entry.get("package"),
            "severity": entry.get("severity", "UNKNOWN"),
            "rationale": entry.get("rationale", ""),
            "review_by": entry.get("review_by", ""),
        }
    return [], entries


def check(
    *,
    audit_json: Path,
    allowlist_path: Path,
    today: str,
) -> list[str]:
    problems: list[str] = []
    audit_problems, vulns = _load_audit(audit_json)
    problems.extend(audit_problems)
    allowlist_problems, allowlist = _load_allowlist(allowlist_path)
    problems.extend(allowlist_problems)
    if audit_problems or allowlist_problems:
        return problems

    today_d = date.fromisoformat(today)
    for key, vuln in sorted(vulns.items()):
        entry = allowlist.get(key)
        if entry is None:
            problems.append(
                f"UNTRIAGED {vuln['package']} {vuln['version']} {vuln['id']} "
                f"(fix: {', '.join(vuln['fix_versions']) or 'none known'}) — "
                f"add it to {allowlist_path} with a rationale + review date"
            )
            continue
        try:
            # yaml.safe_load parses YYYY-MM-DD scalars into date objects —
            # normalize either form back to an ISO string.
            review = date.fromisoformat(str(entry["review_by"]))
        except ValueError:
            problems.append(
                f"{key}: review_by {entry['review_by']!r} is not a date "
                f"(YYYY-MM-DD)"
            )
            continue
        if review < today_d:
            problems.append(
                f"EXPIRED {key}: triaged {entry['severity']} review passed "
                f"{entry['review_by']} — re-review or fix"
            )
    return problems


def _run_pip_audit(requirements: Path) -> Path:
    """Run pip-audit live; W16 policy on missing/unusable pip-audit."""
    from envpolicy import environment_guard

    try:
        # pip-audit exits 1 when vulns are found — the JSON is still
        # written, so check=False and the exit code is ignored on
        # purpose (the gate's verdict comes from the triage logic).
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip_audit",
                "-r",
                str(requirements),
                "--format=json",
                "--output",
                "/tmp/pip-audit-gate.json",
            ],
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
    except FileNotFoundError:
        environment_guard("pip-audit is not installed (4.2 gate)")
        print("SKIP: pip-audit is not installed (4.2 gate)")
        sys.exit(0)
    except subprocess.TimeoutExpired:
        environment_guard("pip-audit timed out (4.2 gate)")
        print("SKIP: pip-audit timed out (4.2 gate)")
        sys.exit(0)
    return Path("/tmp/pip-audit-gate.json")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--requirements", type=Path, default=REQUIREMENTS_DEFAULT)
    parser.add_argument("--allowlist", type=Path, default=ALLOWLIST_DEFAULT)
    parser.add_argument("--audit-json", type=Path, default=None)
    parser.add_argument("--today", default=date.today().isoformat())
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    audit_json = args.audit_json or _run_pip_audit(args.requirements)
    problems = check(audit_json=audit_json, allowlist_path=args.allowlist, today=args.today)
    if problems:
        print(f"GATE-47: {len(problems)} untriaged/expired finding(s) — full list:")
        for problem in problems:
            print(f"FAIL: {problem}")
        sys.exit(1)
    print(
        f"GATE-47 PASSED: every pip-audit finding is triaged "
        f"(allowlist {args.allowlist}, reviewed as of {args.today})"
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
