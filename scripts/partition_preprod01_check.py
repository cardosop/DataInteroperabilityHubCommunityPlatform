#!/usr/bin/env python3
"""
Partition guard for the preprod01 working tree (pilot-readiness task 1.1).

Enforces the agreed campaign partition of the ~3,000-file diff:

* Run artefacts (batch logs, backup files, report directories, stray probe
  files) must never be part of the campaign diff — they are gitignored
  (kept on disk) or removed from the index.
* Every remaining untracked file must look like real source/docs — an
  unclassified file means a human must decide whether it belongs.

Usage:
    scripts/partition_preprod01_check.py            # live `git status --porcelain`
    scripts/partition_preprod01_check.py snapshot   # a saved porcelain dump

Exit 0 when the tree satisfies the partition; exit 1 with a report otherwise.

Pure classification lives in module-level functions so
scripts/tests/test_partition_preprod01_check.py can pin every branch
(TDD: tests written before this file existed).
"""

from __future__ import annotations

import re
import subprocess
import sys
from dataclasses import dataclass

# Root-level run logs the batch/seed workflow writes next to the repo
# (e.g. b12.txt, b101a.txt, f3.txt, f8.txt, e2e-results-b5.txt).
# Deliberately NOT `*.txt` — LICENSE.txt and requirements*.txt are real
# repo files.
ARTIFACT_ROOT_FILE_RE = re.compile(
    r"^(?:b|f)\d+[a-z]?\.txt$"
    r"|^e2e-results-[a-z0-9-]+\.txt$"
    r"|^(?:testci|cilint)\.txt$"
    r"|^OK$"
)

# Frontend run logs captured in the frontend/ dir by tee'd npm scripts
# (fcomp.txt, fdimensions.txt, frontcomp.txt, frontlint.txt, frontrun.txt,
# fronttypecheck.txt, funit.txt, ...).
FRONTEND_RUNLOG_RE = re.compile(r"^frontend/(?:f|front)[a-z0-9]+\.txt$")

# Prefix families that are pure outputs wherever they appear.
IGNORED_ARTIFACT_PREFIXES = (
    "test_reports_e2e/",
    "test_reports_integration/",
    "test_reports_performance/",
    "test-results/",
    "dlt-staging/",
)

# Backup/dot-probe files that must not be committed.
ARTIFACT_NAME_RES = (
    re.compile(r"^\.env\.test\.bak-"),
    re.compile(r"/\.ta002-probe\."),
)

SOURCE_EXTENSIONS = (
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".cjs",
    ".mjs",
    ".css",
    ".scss",
    ".html",
    ".md",
    ".rst",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".sh",
    ".bash",
    ".tf",
    ".tftpl",
    # Visual-regression baselines and static assets are committed content.
    ".png",
    ".svg",
)


@dataclass
class Verdict:
    kind: str  # "ok" | "artifacts" | "unclassified"
    reason: str


def classify_line(porcelain_line: str) -> tuple[str, str]:
    """Classify one `git status --porcelain` line (minus trailing newline)."""
    if not porcelain_line or len(porcelain_line) < 4:
        return "ok", ""
    path = porcelain_line[3:].strip()
    if " -> " in path:
        path = path.split(" -> ", 1)[1]

    state = porcelain_line[:2]
    is_artifact_path = bool(
        ARTIFACT_ROOT_FILE_RE.match(path)
        or FRONTEND_RUNLOG_RE.match(path)
        or any(path.startswith(prefix) for prefix in IGNORED_ARTIFACT_PREFIXES)
        or any(rx.match(path) or rx.search(path) for rx in ARTIFACT_NAME_RES)
    )
    if is_artifact_path:
        if state.strip() == "D":
            # Staged deletion of an artefact is the cleanup IN PROGRESS — the
            # desired end state, not a violation.
            return "ok", f"artifact removal staged: {path}"
        if state.strip() == "R":
            return "ok", f"artifact rename (review in 1.2): {path}"
        return "artifacts", f"run-log / report / stray file: {path}"

    # Tracked-modified files are someone's committed content — leave them to
    # the domain commits (task 1.2). Only untracked files need the source
    # heuristic (they would otherwise slip into `git add .` un-reviewed).
    if state.strip() == "??" and not path.endswith(SOURCE_EXTENSIONS):
        return "unclassified", f"untracked file with non-source extension: {path}"
    return "ok", ""


def summarize(porcelain_dump: str) -> dict[str, int]:
    counts = {"ok": 0, "artifacts": 0, "unclassified": 0}
    for line in porcelain_dump.splitlines():
        kind, _reason = classify_line(line)
        counts[kind] += 1
    return counts


def _collect_violations(porcelain_dump: str) -> list[tuple[str, str]]:
    violations: list[tuple[str, str]] = []
    for line in porcelain_dump.splitlines():
        kind, reason = classify_line(line)
        if kind in ("artifacts", "unclassified"):
            violations.append((kind, reason))
    return violations


def live_status() -> str:
    # -uall: expand untracked directories into individual files so every
    # path is judged (porcelain otherwise collapses them to `dir/` lines).
    proc = subprocess.run(
        ["git", "status", "--porcelain", "-uall"],
        capture_output=True,
        text=True,
        check=True,
    )
    return proc.stdout


def main(argv: list[str]) -> int:
    if len(argv) > 1 and argv[1]:
        with open(argv[1], encoding="utf-8") as fh:
            dump = fh.read()
        source = argv[1]
    else:
        dump = live_status()
        source = "git status --porcelain"

    counts = summarize(dump)
    violations = _collect_violations(dump)
    print(
        f"partition check ({source}): "
        f"ok={counts['ok']} artifacts={counts['artifacts']} "
        f"unclassified={counts['unclassified']}",
        file=sys.stderr,
    )
    for kind, reason in violations[:30]:
        print(f"  [{kind}] {reason}", file=sys.stderr)
    if len(violations) > 30:
        print(f"  ... and {len(violations) - 30} more", file=sys.stderr)
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
