#!/usr/bin/env python3
"""
GATE-52 (oss-release-remediation W0.6) — the tag-archive manifest +
blocking-scan contract checker.

The committed manifest (docs/audits/tag-archive-manifest-2026-10-06.md)
must:

- exist and carry the mandated sections — the archive destination (bucket
  name REDACTED per the W0.9 contract), one row per canonical tag tree
  (the 17 ``backup-staging-*`` tags) and per canonical backup directory
  (the 19 ``backups/staging_*`` restore points), each row carrying a
  sha256 + ``verified: yes`` + ``deleted: yes`` — the gate is HONEST:
  any row not fully resolved fails it (the GATE-51 precedent — a gate
  that tolerates PENDING is vacuous);
- be backed by the W0.6 gitignore entries (``*.key``, ``*.pem``,
  ``infrastructure/staging/secrets/``) and the BLOCKING pre-commit
  gitleaks hook (no ``exit 0`` fallback on a missing binary — the W0.2
  vacuity class);
- carry no TBD/TODO placeholders.

Exit 0 when the record satisfies the contract; 1 otherwise, each problem
named.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
RECORD_DEFAULT = _ROOT / "docs" / "audits" / "tag-archive-manifest-2026-10-06.md"
_GITIGNORE = _ROOT / ".gitignore"
_PRECOMMIT = _ROOT / ".pre-commit-config.yaml"

REQUIRED_SECTIONS = ("## Archive destination", "## Tag trees", "## Backup directories")

# The canonical surfaces (W0.6): all 17 backup-staging-* tags and all 19
# backups/staging_* restore-point dirs (two dirs — _195434, _195457 —
# never had a matching tag; they are restore points under the same S5
# rationale and are archived the same way).
TAG_NAMES = (
    "backup-staging-20251207_194944",
    "backup-staging-20251207_195141",
    "backup-staging-20251207_200213",
    "backup-staging-20251207_200633",
    "backup-staging-20251207_201334",
    "backup-staging-20251207_201512",
    "backup-staging-20251207_203026",
    "backup-staging-20251208_032012",
    "backup-staging-20251208_033706",
    "backup-staging-20251208_040204",
    "backup-staging-20251208_042829",
    "backup-staging-20251208_050033",
    "backup-staging-20251208_053421",
    "backup-staging-20251208_065403",
    "backup-staging-20251208_070728",
    "backup-staging-20251208_074900",
    "backup-staging-20251208_093914",
)
BACKUP_NAMES = (
    "staging_20251207_194944",
    "staging_20251207_195141",
    "staging_20251207_195434",
    "staging_20251207_195457",
    "staging_20251207_200213",
    "staging_20251207_200633",
    "staging_20251207_201334",
    "staging_20251207_201512",
    "staging_20251207_203026",
    "staging_20251208_032012",
    "staging_20251208_033706",
    "staging_20251208_040204",
    "staging_20251208_042829",
    "staging_20251208_050033",
    "staging_20251208_053421",
    "staging_20251208_065403",
    "staging_20251208_070728",
    "staging_20251208_074900",
    "staging_20251208_093914",
)

_PLACEHOLDER = re.compile(r"\b(TBD|TODO|PLACEHOLDER|XXX)\b", re.I)
_ROW = re.compile(r"^- (?P<name>\S+) .*?verified: (?P<verified>\w+) — deleted: (?P<deleted>\w+)$")
_GITIGNORE_ENTRIES = ("*.key", "*.pem", "infrastructure/staging/secrets/")


def _rows(text: str) -> dict[str, str]:
    """Row name -> 'verified: x — deleted: y' tail (rows only)."""
    result: dict[str, str] = {}
    for line in text.splitlines():
        if not line.startswith("- "):
            continue
        match = _ROW.match(line)
        if match:
            result[match.group("name")] = (
                f"verified: {match.group('verified')} — deleted: {match.group('deleted')}"
            )
    return result


def _gitignore_problems_for(path: Path) -> list[str]:
    problems = []
    if not path.is_file():
        return [f"{path} missing — cannot verify the W0.6 gitignore entries"]
    text = path.read_text()
    for entry in _GITIGNORE_ENTRIES:
        if entry not in text.splitlines() and entry not in text:
            problems.append(f".gitignore is missing the W0.6 entry {entry!r}")
    return problems


def _hook_problems_for(path: Path) -> list[str]:
    problems = []
    if not path.is_file():
        return [f"{path} missing — cannot verify the blocking pre-commit hook"]
    lines = path.read_text().splitlines()
    entry_lines = []
    in_hook = False
    for line in lines:
        if line.strip() == "- id: gitleaks":
            in_hook = True
        elif in_hook and line.startswith(("      -", "    -")) and "gitleaks" not in line:
            in_hook = False
        if in_hook:
            entry_lines.append(line)
    if not entry_lines:
        return ["the pre-commit config has no gitleaks hook"]
    joined = "\n".join(entry_lines)
    if "exit 0" in joined:
        problems.append(
            "the gitleaks pre-commit hook still falls back to exit 0 on a "
            "missing binary — a silently-skipping secret scan is the W0.2 "
            "vacuity class; the hook must be blocking"
        )
    if "gitleaks detect" not in joined:
        problems.append("the gitleaks pre-commit hook entry carries no detect invocation")
    return problems


def _gitignore_problems() -> list[str]:
    return _gitignore_problems_for(_GITIGNORE)


def _hook_problems() -> list[str]:
    return _hook_problems_for(_PRECOMMIT)


def check(record_path: Path) -> list[str]:
    problems: list[str] = []
    if not record_path.exists():
        return [f"tag-archive manifest missing: {record_path}"]
    text = record_path.read_text()

    for section in REQUIRED_SECTIONS:
        if section not in text:
            problems.append(f"missing mandated section {section!r}")

    rows = _rows(text)
    for name in TAG_NAMES:
        tail = rows.get(name)
        if tail is None:
            problems.append(f"missing tag-tree row {name!r}")
            continue
        if "verified: yes" not in tail or "deleted: yes" not in tail:
            problems.append(
                f"tag-tree row {name!r} is not fully resolved ({tail}) — "
                "the honest gate blocks until every row is verified+deleted"
            )
        line = next(ln for ln in text.splitlines() if ln.startswith(f"- {name} "))
        if not re.search(r"sha256 [0-9a-f]{64}", line):
            problems.append(f"tag-tree row {name!r} carries no valid sha256")

    for name in BACKUP_NAMES:
        tail = rows.get(name)
        if tail is None:
            problems.append(f"missing backup-directory row {name!r}")
            continue
        if "verified: yes" not in tail or "deleted: yes" not in tail:
            problems.append(
                f"backup-directory row {name!r} is not fully resolved ({tail}) — "
                "the honest gate blocks until every row is verified+deleted"
            )
        line = next(ln for ln in text.splitlines() if ln.startswith(f"- {name} "))
        if not re.search(r"sha256 [0-9a-f]{64}", line):
            problems.append(f"backup-directory row {name!r} carries no valid sha256")

    problems.extend(_gitignore_problems())
    problems.extend(_hook_problems())

    for word in sorted(set(_PLACEHOLDER.findall(text))):
        problems.append(f"unresolved placeholder {word!r} in the manifest")

    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, default=RECORD_DEFAULT)
    args = parser.parse_args()
    problems = check(args.record)
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        print(f"GATE-52 FAILED: {len(problems)} problem(s)")
        sys.exit(1)
    print(f"GATE-52 PASSED: {args.record} satisfies the tag-archive contract")
    sys.exit(0)


if __name__ == "__main__":
    main()
