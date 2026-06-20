#!/usr/bin/env python3
"""Audit pinned CVEs — Phase 225.2.

Cross-references the two places we intentionally carry known-vulnerable
dependencies and reports their review status:

 1. ``requirements.txt`` — lines of the form ``pkg==x.y.z  # CVE-...``
    (version pinned deliberately to dodge a published CVE).
 2. ``.trivyignore`` — CVEs allow-listed from container scans, ideally with
    an adjacent ``# Review by: YYYY-MM-DD`` comment.

Output:
 * stdout — human-readable report grouped by source.
 * Non-zero stderr line per ``overdue`` entry.
 * ``GITHUB_STEP_SUMMARY`` (if set) — markdown report, appended.

Exit codes:
 * ``--non-blocking`` (default in the PR CI): always 0 so the job is
   informational; useful output lands in the step summary.
 * ``--strict``: 1 iff any overdue entry is found — used by the monthly
   scheduled workflow so a missed review breaks CI and opens an issue.

No dependencies outside the Python standard library; safe to invoke from CI
runners that only have `python3` available.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime
import os
import pathlib
import re
import sys
from collections.abc import Iterable

# How many days from ``today`` count as "due soon"; surfaces entries
# approaching the window without yet blocking CI.
DUE_SOON_WINDOW_DAYS = 14

CVE_RE = re.compile(r"CVE-\d{4}-\d{3,7}")
REQ_LINE_RE = re.compile(
    r"""^(?P<pkg>[A-Za-z_][A-Za-z0-9_.\-]*)\s*==\s*(?P<version>[^\s#]+)\s*#\s*(?P<comment>.*)$"""
)
REVIEW_BY_RE = re.compile(r"Review by[:\s]+(\d{4}-\d{2}-\d{2})", re.IGNORECASE)


@dataclasses.dataclass(frozen=True)
class PinnedCVE:
    """A CVE referenced from ``requirements.txt``."""

    package: str
    version: str
    cve: str
    note: str


@dataclasses.dataclass(frozen=True)
class IgnoredCVE:
    """A CVE listed in ``.trivyignore`` with its optional review date."""

    cve: str
    review_by: datetime.date | None


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------


def parse_requirements_cves(path: pathlib.Path) -> list[PinnedCVE]:
    """Return every ``pkg==x.y.z  # CVE-…`` entry in a requirements file."""
    if not path.exists():
        return []
    entries: list[PinnedCVE] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        match = REQ_LINE_RE.match(line)
        if not match:
            continue
        comment = match.group("comment")
        cves = CVE_RE.findall(comment)
        if not cves:
            continue
        # Strip any CVE tokens out of the note to leave a cleaner message.
        note = CVE_RE.sub("", comment).lstrip(" ,:-").strip()
        for cve in cves:
            entries.append(
                PinnedCVE(
                    package=match.group("pkg"),
                    version=match.group("version"),
                    cve=cve,
                    note=note,
                )
            )
    return entries


def parse_trivyignore(path: pathlib.Path) -> list[IgnoredCVE]:
    """Parse ``.trivyignore``. Review dates come from the nearest preceding
    ``# Review by: YYYY-MM-DD`` comment (sticky until another one is seen).
    """
    if not path.exists():
        return []
    current_review: datetime.date | None = None
    entries: list[IgnoredCVE] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            date_match = REVIEW_BY_RE.search(line)
            if date_match:
                try:
                    current_review = datetime.date.fromisoformat(date_match.group(1))
                except ValueError:
                    current_review = None
            continue
        cve_match = CVE_RE.search(line)
        if not cve_match:
            continue
        entries.append(IgnoredCVE(cve=cve_match.group(0), review_by=current_review))
    return entries


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------


def classify_review_status(
    review_by: datetime.date | None,
    *,
    today: datetime.date,
    due_soon_days: int = DUE_SOON_WINDOW_DAYS,
) -> str:
    """Return ``overdue`` / ``due_soon`` / ``ok`` / ``unknown`` for a date."""
    if review_by is None:
        return "unknown"
    delta = (review_by - today).days
    if delta < 0:
        return "overdue"
    if delta <= due_soon_days:
        return "due_soon"
    return "ok"


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------


def _render_report(
    pinned: Iterable[PinnedCVE],
    ignored: Iterable[IgnoredCVE],
    *,
    today: datetime.date,
) -> tuple[str, list[str], list[str]]:
    """Build a markdown report.

    Returns ``(markdown, overdue_lines, unknown_lines)`` — the two lists are
    kept separate so callers (strict CLI, issue-body composer) can report
    them under distinct headings instead of lumping them together.
    """
    lines: list[str] = [
        "# Pinned CVE audit",
        f"_Audit date: {today.isoformat()}_",
        "",
    ]
    overdue: list[str] = []
    unknown: list[str] = []

    pinned_list = list(pinned)
    lines.append(f"## requirements.txt — {len(pinned_list)} pinned CVE reference(s)")
    if pinned_list:
        lines.append("| Package | Version | CVE | Note |")
        lines.append("|---|---|---|---|")
        for pin in sorted(pinned_list, key=lambda e: (e.package.lower(), e.cve)):
            lines.append(f"| {pin.package} | {pin.version} | {pin.cve} | {pin.note} |")
    else:
        lines.append("_No CVE-tagged pins found._")
    lines.append("")

    ignored_list = list(ignored)
    lines.append(f"## .trivyignore — {len(ignored_list)} ignored CVE(s)")
    if ignored_list:
        lines.append("| CVE | Review by | Status |")
        lines.append("|---|---|---|")
        for ign in sorted(
            ignored_list,
            key=lambda e: (e.review_by or datetime.date.max, e.cve),
        ):
            status = classify_review_status(ign.review_by, today=today)
            review_str = ign.review_by.isoformat() if ign.review_by else "—"
            lines.append(f"| {ign.cve} | {review_str} | {status.upper()} |")
            if status == "overdue":
                overdue.append(f"{ign.cve} review overdue (was due {review_str})")
            elif status == "unknown":
                unknown.append(f"{ign.cve} has no 'Review by:' date — add one before merging")
    else:
        lines.append("_No ignored CVEs._")
    lines.append("")

    if overdue:
        lines.append("## ⚠️ Overdue reviews")
        for line in overdue:
            lines.append(f"- {line}")
        lines.append("")

    if unknown:
        lines.append("## ⚠️ Missing 'Review by:' dates")
        for line in unknown:
            lines.append(f"- {line}")
        lines.append("")

    return "\n".join(lines), overdue, unknown


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--requirements",
        default="requirements.txt",
        help="Path to requirements.txt (default: ./requirements.txt)",
    )
    parser.add_argument(
        "--trivyignore",
        default=".trivyignore",
        help="Path to .trivyignore (default: ./.trivyignore)",
    )
    parser.add_argument(
        "--today",
        default=None,
        help="Override 'today' as YYYY-MM-DD (for deterministic CI runs).",
    )
    # `--non-blocking` is the default behavior; the flag is accepted for
    # explicit CI YAML readability but it's a no-op when `--strict` is
    # absent. We intentionally don't put these in a mutex group because
    # argparse mutex groups can't express "strict wins" cleanly when one
    # side has a default.
    parser.add_argument(
        "--non-blocking",
        action="store_true",
        help="Always exit 0 (default — informational PR check).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help=(
            "Exit 1 if any entry is OVERDUE or missing a 'Review by:' date "
            "(UNKNOWN). Used by the scheduled monthly job so indefinite "
            "exceptions surface as failures."
        ),
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    today = datetime.date.fromisoformat(args.today) if args.today else datetime.date.today()
    pinned = parse_requirements_cves(pathlib.Path(args.requirements))
    ignored = parse_trivyignore(pathlib.Path(args.trivyignore))
    report, overdue, unknown = _render_report(pinned, ignored, today=today)

    sys.stdout.write(report + "\n")
    for line in overdue:
        sys.stderr.write(f"OVERDUE: {line}\n")
    for line in unknown:
        sys.stderr.write(f"UNKNOWN: {line}\n")

    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        # Append rather than overwrite; other steps may have written first.
        with open(summary_path, "a", encoding="utf-8") as handle:
            handle.write(report + "\n")

    # Strict mode fails on both overdue AND unknown entries so a CVE added
    # without a 'Review by:' comment cannot slip silently into a permanent
    # exception — the monthly workflow will open the tracking issue either
    # way. Non-blocking mode always exits 0.
    if args.strict and (overdue or unknown):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
