#!/usr/bin/env python3
"""PR-level test-risk signal (Phase T.6 / W18).

Turns the three test-debt growth classes into a ROUTED, NON-BLOCKING
signal on every PR (a signal, not a gate — the gates already block; this
tells the owning team BEFORE review):

  * added skip sites    — the W16/W17 debt class growing;
  * removed assertions  — a test silently weakened;
  * introduced broad    — ``except Exception`` / bare ``except:`` in a
    excepts              test file (the BLE001 anti-pattern class).

Only TEST files are analyzed (``test_*.py`` / ``*_test.py`` /
``conftest.py`` / ``tests/**`` / ``*.spec.ts`` / ``*.test.ts(x)``).

Each finding is routed to the owning team resolved from CODEOWNERS
(last-order-wins longest-prefix match; unmatched → "unowned"). The CI
workflow posts the report as a PR comment via ``actions/github-script``.

Exit code is ALWAYS 0 on success — signals do not block merges.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CODEOWNERS = Path(__file__).resolve().parent.parent / ".github" / "CODEOWNERS"

_TEST_FILE_RE = re.compile(
    r"(^|/)(test_[^/]*\.py$|[^/]*_test\.py$|conftest\.py$|"
    r".*\.(spec|test)\.tsx?$)"
)

_ADDED_SKIP_RE = re.compile(
    r"^\+\s*(@pytest\.mark\.(skip|skipif|xfail)|pytest\.(skip|xfail)\(|"
    r"@unittest\.skip|test\.(skip|fixme)\(|describe\.skip\(|it\.skip\()"
)
_REMOVED_ASSERT_RE = re.compile(r"^-\s*(assert\b|self\.assert|expect\s*\()")
_ADDED_BROAD_EXCEPT_RE = re.compile(r"^\+\s*except\s*(\(?\s*(Exception|BaseException)\b|:)")


@dataclass
class Finding:
    file: str
    line: int
    kind: str  # added-skip | removed-assertion | broad-except
    detail: str


def _is_test_file(path: str) -> bool:
    return bool(_TEST_FILE_RE.search(path))


def analyze_diff(diff_text: str) -> list[Finding]:
    """Scan unified-diff text for the three risk classes in test files."""
    findings: list[Finding] = []
    current_file: str | None = None
    new_line_no = 0
    old_line_no = 0
    for raw in diff_text.splitlines():
        if raw.startswith("+++ b/"):
            current_file = raw[6:]
            new_line_no = 0
            old_line_no = 0
            continue
        if raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            new_line_no = int(m.group(1)) - 1 if m else 0
            m = re.search(r"-(\d+)", raw)
            old_line_no = int(m.group(1)) - 1 if m else 0
            continue
        if current_file is None or not _is_test_file(current_file):
            continue
        if raw.startswith("+"):
            new_line_no += 1
            if _ADDED_SKIP_RE.match(raw):
                findings.append(Finding(current_file, new_line_no, "added-skip", raw[1:].strip()))
            elif _ADDED_BROAD_EXCEPT_RE.match(raw):
                findings.append(Finding(current_file, new_line_no, "broad-except", raw[1:].strip()))
        elif raw.startswith("-"):
            old_line_no += 1
            if _REMOVED_ASSERT_RE.match(raw):
                findings.append(
                    Finding(current_file, old_line_no, "removed-assertion", raw[1:].strip())
                )
        else:
            new_line_no += 1
            old_line_no += 1
    return findings


def _parse_owner_rules(codeowners: Path | str) -> list[tuple[str, list[str]]]:
    """(pattern, owners) rules in document order (last-order-wins applies
    during resolution)."""
    codeowners = Path(codeowners)
    rules: list[tuple[str, list[str]]] = []
    if not codeowners.exists():
        return rules
    for raw in codeowners.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith(("#", "!")):
            continue
        parts = line.split()
        if len(parts) >= 2:
            rules.append((parts[0], parts[1:]))
    return rules


def _pattern_matches(pattern: str, path: str) -> bool:
    """CODEOWNERS pattern → path match (prefix + single-star globs)."""
    if pattern.endswith("/"):
        return path.startswith(pattern)
    if pattern.startswith("/"):
        pattern = pattern[1:]
    if "*" in pattern:
        regex = re.escape(pattern).replace(r"\*", "[^/]*")
        return re.match(rf"^{regex}$", path) is not None
    return path == pattern or path.startswith(pattern.rstrip("/") + "/")


def resolve_owner(path: str, codeowners: Path | str) -> list[str]:
    """Owning teams for a repo-relative path (last-order-wins)."""
    owners: list[str] = []
    for pattern, rule_owners in _parse_owner_rules(codeowners):
        if _pattern_matches(pattern, path):
            owners = rule_owners
    return owners


def _route(findings: list[Finding], codeowners: Path | str) -> dict[str, list[Finding]]:
    routed: dict[str, list[Finding]] = {}
    for finding in findings:
        owners = resolve_owner(finding.file, codeowners) or ["unowned"]
        for owner in owners:
            routed.setdefault(owner, []).append(finding)
    return routed


def format_report(routed: dict[str, list[Finding]]) -> str:
    if not routed:
        return (
            "Test-risk signal: no added skips, removed assertions, or broad excepts in test files."
        )
    lines: list[str] = ["Test-risk signal — routed to owning teams:"]
    for owner in sorted(routed):
        lines.append(f"  {owner}:")
        for finding in routed[owner]:
            lines.append(
                f"    {finding.file}:{finding.line} [{finding.kind}] {finding.detail[:100]}"
            )
    return "\n".join(lines)


def report_for_range(
    codeowners: Path | str, base: str, head: str | None = None, cwd: str | None = None
) -> str:
    """Run `git diff base [head]` in cwd and return the routed report."""
    cmd = ["git", "diff", "--no-color", base]
    if head:
        cmd.append(head)
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=True)
    findings = analyze_diff(result.stdout)
    return format_report(_route(findings, codeowners))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="PR-level test-risk signal (routed to CODEOWNERS teams; non-blocking)."
    )
    parser.add_argument("--codeowners", type=Path, default=DEFAULT_CODEOWNERS)
    parser.add_argument("--base", default="origin/main", help="diff base ref")
    parser.add_argument("--head", default=None, help="diff head ref (default: working tree)")
    parser.add_argument("--cwd", default=None, help="git working directory")
    args = parser.parse_args(argv)

    report = report_for_range(args.codeowners, args.base, args.head, args.cwd)
    print(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
