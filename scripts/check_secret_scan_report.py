#!/usr/bin/env python3
"""
GATE-49 (oss-release-remediation W0.2) — the secret-scan report contract
checker.

The committed W0.2 report (docs/audits/secret-scan-2026-10-06.md) must:

- exist and carry the mandated sections — the summary declares
  ``Unremediated HIGH | 0`` (every HIGH finding mapped to a remediation
  workstream), the methodology names both tools with versions, the
  findings inventory is redacted, and the remediation mapping +
  verification sections are present;
- contain no secret-like material: the gate re-scans the report itself
  with gitleaks (default rules, on a temp copy) and fails on any hit —
  the redaction contract is enforced, not assumed;
- carry no TBD/TODO placeholders.

The gate also pins the repo gitleaks config's NON-VACUITY: the W0.2
root-cause finding was a ``.gitleaks.toml`` carrying only an
``[allowlist]`` section — gitleaks treats a config without ``[[rules]]``
as an EMPTY ruleset, which silently disabled every config-based scan
(CI included). The config must parse and carry the merged official
ruleset (>=100 rules) plus a non-empty allowlist.

Exit 0 when the report satisfies the contract; 1 otherwise, each problem
named.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
REPORT_DEFAULT = _ROOT / "docs/audits/secret-scan-2026-10-06.md"
GITLEAKS_CONFIG_DEFAULT = _ROOT / ".gitleaks.toml"
MIN_CONFIG_RULES = 100

REQUIRED_SECTIONS = (
    "## Summary",
    "## Scan methodology",
    "## Findings inventory (redacted)",
    "## Remediation mapping",
    "## Verification",
)

_UNREMEDIATED_HIGH = re.compile(r"^\|\s*Unremediated HIGH\s*\|\s*(\d+)\s*\|", re.M)
_PLACEHOLDER = re.compile(r"\b(TBD|TODO|PLACEHOLDER|XXX)\b", re.I)
_VERSION = re.compile(r"\b\d+\.\d+\.\d+\b")


def _check_config(config_path: Path) -> list[str]:
    """Pin the repo gitleaks config's non-vacuity (the W0.2 root cause)."""
    if not config_path.exists():
        return [f"gitleaks config missing: {config_path}"]
    try:
        cfg = tomllib.loads(config_path.read_text())
    except tomllib.TOMLDecodeError as exc:
        return [f"gitleaks config does not parse: {config_path}: {exc}"]
    problems: list[str] = []
    if len(cfg.get("rules", [])) < MIN_CONFIG_RULES:
        problems.append(
            f"gitleaks config has {len(cfg.get('rules', []))} rules — a config "
            f"without rules makes every gitleaks run vacuous (W0.2 root cause); "
            f"the merged official ruleset needs >= {MIN_CONFIG_RULES}"
        )
    allowlist = cfg.get("allowlist") or {}
    if not allowlist.get("paths"):
        problems.append(
            "gitleaks config has an empty allowlist.paths — the Meshant path allowlists are missing"
        )
    return problems


def _self_scan(report_path: Path) -> list[str]:
    """Re-scan the report copy with gitleaks (default rules, no git).

    The report must itself be free of secret-like material — redaction
    is verified, not assumed. Returns [] when clean.
    """
    gitleaks = shutil.which("gitleaks")
    if gitleaks is None:
        return [
            "gitleaks binary not found — the report self-scan cannot verify "
            "redaction (pre-commit dev toolchain installs it; CI runs "
            "gitleaks-action as the backstop)"
        ]
    with tempfile.TemporaryDirectory() as tmp:
        copy = Path(tmp) / report_path.name
        copy.write_text(report_path.read_text())
        # The `dir` subcommand is the working filesystem scanner on
        # gitleaks 8.21.x — the legacy `detect --no-git` form matches NO
        # rules on this build (vacuity found during W0.2; recorded in
        # the scan report).
        result = subprocess.run(
            [gitleaks, "dir", str(tmp), "--exit-code", "1", "--no-banner"],
            capture_output=True,
            text=True,
            check=False,
        )
    if result.returncode != 0:
        return [
            "the report contains secret-like material (gitleaks self-scan "
            "found findings) — the committed report must stay redacted"
        ]
    return []


def check(report_path: Path, config_path: Path = GITLEAKS_CONFIG_DEFAULT) -> list[str]:
    problems: list[str] = []
    if not report_path.exists():
        return [f"secret-scan report missing: {report_path}"]
    problems.extend(_check_config(config_path))
    text = report_path.read_text()

    for section in REQUIRED_SECTIONS:
        if section not in text:
            problems.append(f"missing mandated section {section!r}")

    match = _UNREMEDIATED_HIGH.search(text)
    if match is None:
        problems.append(
            "missing the summary row `| Unremediated HIGH | 0 |` — the "
            "zero-unremediated-HIGHs declaration is the W0.2 evidence"
        )
    elif match.group(1) != "0":
        problems.append(
            f"summary row `| Unremediated HIGH | {match.group(1)} |` — "
            "every HIGH must be mapped to a remediation workstream"
        )

    methodology = (
        text.split("## Scan methodology", 1)[1].split("## ", 1)[0]
        if "## Scan methodology" in text
        else ""
    )
    for tool in ("gitleaks", "trufflehog"):
        if tool not in methodology:
            problems.append(f"scan methodology does not name the {tool} pass")
    if not _VERSION.search(methodology):
        problems.append("scan methodology does not record tool versions")

    for word in sorted(set(_PLACEHOLDER.findall(text))):
        problems.append(f"unresolved placeholder {word!r} in the report")

    problems.extend(_self_scan(report_path))
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=REPORT_DEFAULT)
    parser.add_argument("--config", type=Path, default=GITLEAKS_CONFIG_DEFAULT)
    args = parser.parse_args()
    problems = check(args.report, args.config)
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        print(f"GATE-49 FAILED: {len(problems)} problem(s)")
        sys.exit(1)
    print(f"GATE-49 PASSED: {args.report} satisfies the scan-report contract")
    sys.exit(0)


if __name__ == "__main__":
    main()
