#!/usr/bin/env python3
"""Triage tooling for the pinned-CVE waves (close-oss-release-conditions P0-2).

Feeds the triage wave with REAL advisory data, no hand-typed claims:

1. Parses ``.trivyignore`` with the checker's own parser, plus the
   sticky ``[Category-A]`` / ``[Category-B]`` tags (Phase 277.B.002
   taxonomy: A = unreachable from container workloads, B = fix pending
   from the distro).
2. Fetches each CVE's OSV record (https://api.osv.dev) into a committed
   snapshot cache, so the bucket evidence is reproducible offline and a
   re-run costs nothing.
3. Classifies each entry into the three wave buckets:
   * Bucket 1 — fix released upstream (an OSV ``fixed`` event exists)
   * Bucket 2 — fix pending (no fixed event; allowlist with rationale)
   * Bucket 3 — not applicable (Category-A, unreachable component)
4. Emits the snapshot JSON and a bucket-table draft for the wave doc.

Stdlib-only (urllib); safe for CI runners and offline re-runs once the
snapshot is committed. The snapshot is the evidence — never edit it by
hand; re-run this script instead.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from audit_pinned_cves import parse_trivyignore  # the checker's own parser

OSV_API = "https://api.osv.dev/v1/vulns/"
DEFAULT_SNAPSHOT = REPO_ROOT / "docs" / "audits" / "cve-triage-2026" / "osv-snapshot-2026-10-18.json"
CATEGORY_RE = re.compile(r"\[Category-([AB])\]")
CVE_RE = re.compile(r"CVE-\d{4}-\d{3,7}")
REVIEW_BY_RE = re.compile(r"Review by[:\s]+\d{4}-\d{2}-\d{2}", re.IGNORECASE)


def parse_categories(trivyignore: Path) -> dict[str, str]:
    """CVE → category ('A'/'B') from the sticky [Category-X] tags."""
    lines = trivyignore.read_text(encoding="utf-8").splitlines()
    current: str | None = None
    categories: dict[str, str] = {}
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            match = CATEGORY_RE.search(line)
            if match:
                current = match.group(1)
            continue
        cve_match = CVE_RE.search(line)
        if cve_match and current is not None:
            categories[cve_match.group(0)] = current
    return categories


def fetch_osv(cve: str, cache: dict, *, offline: bool) -> dict | None:
    """Return the OSV record; hit the API once per run, cache thereafter."""
    if cve in cache:
        return cache[cve]
    if offline:
        return None
    request = urllib.request.Request(OSV_API + cve, headers={"User-Agent": "hub-cve-triage/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            record = json.loads(response.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 — network boundary, cache fallback
        record = {"_fetch_error": f"{type(exc).__name__}: {exc}"}
    cache[cve] = record
    time.sleep(0.15)  # be polite to the public API
    return record


def summarize(record: dict | None) -> dict:
    """Summary fields the buckets need: summary, top severity, fixed events."""
    if not record or "_fetch_error" in record:
        return {"summary": str((record or {}).get("_fetch_error", "no data")), "severity": "", "fixed": []}
    severities = [
        f"{item.get('type')}:{item.get('score')}"
        for item in record.get("severity", [])
        if item.get("type") == "CVSS_V3" or item.get("type") == "CVSS_V4"
    ]
    fixed = []
    for affected in record.get("affected", []):
        for rng in affected.get("ranges", []):
            fixed.extend(event.get("fixed") for event in rng.get("events", []) if "fixed" in event)
    return {
        "summary": (record.get("summary") or record.get("details") or "")[:200],
        "severity": severities[0] if severities else "",
        "fixed": sorted({value for value in fixed if value}),
    }


VERSION_RE = re.compile(r"^\d+(?:\.\d+)+[0-9a-z.+~-]*$")


def classify(category: str, summary: dict) -> int:
    """Bucket number: 1 fix-released (a RELEASED upstream version exists —
    kernel commit SHAs do not count: the distro may not have shipped them),
    2 fix-pending, 3 not-applicable (Category-A)."""
    if category == "A":
        return 3
    if any(VERSION_RE.fullmatch(value) for value in summary["fixed"]):
        return 1
    return 2


def rewrite_trivyignore(trivyignore: Path, snapshot: Path, today: str) -> str:
    """Emit the re-dated .trivyignore: entries grouped by bucket, original
    comment lines preserved (they carry the Category tags + rationale),
    one sticky ``Review by:`` date per bucket section. Old review-date
    comment lines are STRIPPED from entry blocks — a stale date inside a
    block would otherwise win the sticky-date parse and re-mark the entry
    overdue."""
    import datetime as _dt

    def strip_dates(lines: list[str]) -> list[str]:
        return [line for line in lines if not REVIEW_BY_RE.search(line)]

    categories = parse_categories(trivyignore)
    raw_lines = trivyignore.read_text(encoding="utf-8").splitlines()
    # Leading header comments: everything before the first CVE line or
    # the first [Category- tag (newlines preserved this time).
    first_cve_index = next(i for i, line in enumerate(raw_lines) if CVE_RE.search(line))
    header_candidates = raw_lines[:first_cve_index]
    header = []
    for line in header_candidates:
        if line.startswith("# [Category") and REVIEW_BY_RE.search(line):
            continue
        if REVIEW_BY_RE.search(line) and "# Review" in line:
            continue
        header.append(line)

    blocks: list[tuple[list[str], str]] = []  # (comment lines, cve line)
    comments: list[str] = []
    for raw in raw_lines[first_cve_index:]:
        stripped = raw.strip()
        if not stripped:
            comments.append(raw)
            continue
        if stripped.startswith("#"):
            comments.append(raw)
            continue
        match = CVE_RE.search(stripped)
        if match:
            blocks.append((strip_dates(comments), stripped))
            comments = []

    snapshot_data = json.loads(snapshot.read_text(encoding="utf-8"))
    buckets: dict[int, list[tuple[list[str], str]]] = {1: [], 2: [], 3: []}
    for comments_block, cve_line in blocks:
        cve = CVE_RE.search(cve_line).group(0)
        summary = summarize(snapshot_data.get(cve))
        buckets[classify(categories.get(cve, "B"), summary)].append((comments_block, cve_line))

    names = {
        1: "Bucket 1 — upstream fix released (version event in OSV); verify/bump at the "
           "next image rebuild and remove the entry once the trivy scan clears it",
        2: "Bucket 2 — fix pending for our images (upstream commit only / no released "
           "version / not yet in OSV); keep allowlisted with rationale",
        3: "Bucket 3 — not applicable (Category-A: unreachable from container "
           "workloads — justification in the comment block)",
    }
    dates = {
        1: (_dt.date.fromisoformat(today) + _dt.timedelta(days=30)).isoformat(),
        2: (_dt.date.fromisoformat(today) + _dt.timedelta(days=90)).isoformat(),
        3: (_dt.date.fromisoformat(today) + _dt.timedelta(days=180)).isoformat(),
    }
    out = ["\n".join(header).rstrip() if header else ""]
    out.append("#")
    out.append("# Re-dated by the CVE triage wave 1 (close-oss-release-conditions P0-2, 2026-10-18)")
    out.append("# via scripts/triage_pinned_cves.py --rewrite-trivyignore; evidence:")
    out.append("# docs/audits/cve-triage-2026/ (wave ledger + buckets + OSV snapshot).")
    out.append("#")
    for bucket in (1, 2, 3):
        rows = buckets[bucket]
        if not rows:
            continue
        out.append("")
        out.append("# =============================================================================")
        out.append(f"# [Wave-1] {names[bucket]}")
        out.append(f"# [Wave-1] Review by: {dates[bucket]}")
        out.append("# =============================================================================")
        for comments_block, cve_line in rows:
            for line in comments_block:
                out.append(line)
            out.append(cve_line)
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trivyignore", type=Path, default=REPO_ROOT / ".trivyignore")
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--offline", action="store_true", help="use only the cached snapshot")
    parser.add_argument("--emit-buckets", action="store_true", help="print the bucket-table draft")
    parser.add_argument(
        "--rewrite-trivyignore",
        action="store_true",
        help="print the re-dated .trivyignore (grouped by bucket; do not modify "
        "dates manually — the wave evidence and this tooling are the record)",
    )
    parser.add_argument("--today", default=None, help="override today as YYYY-MM-DD")
    args = parser.parse_args(argv)

    snapshot = {}
    if args.snapshot.exists():
        snapshot = json.loads(args.snapshot.read_text(encoding="utf-8"))

    categories = parse_categories(args.trivyignore)
    entries = {entry.cve for entry in parse_trivyignore(args.trivyignore)}
    all_cves = sorted(categories.keys() | entries)
    untagged = [cve for cve in entries if cve not in categories]
    if untagged:
        print(f"WARN: entries without a [Category-X] tag: {sorted(untagged)}", file=sys.stderr)

    rows = []
    for cve in all_cves:
        record = fetch_osv(cve, snapshot, offline=args.offline)
        summary = summarize(record)
        bucket = classify(categories.get(cve, "B"), summary)
        rows.append((cve, categories.get(cve, "?"), bucket, summary))

    args.snapshot.parent.mkdir(parents=True, exist_ok=True)
    args.snapshot.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"snapshot: {args.snapshot} ({len(snapshot)} CVE records)")

    if args.emit_buckets:
        names = {
            1: "## Bucket 1 — fix released",
            2: "## Bucket 2 — fix pending",
            3: "## Bucket 3 — not applicable",
        }
        review_dates = {1: "2026-11-17", 2: "2027-01-16", 3: "2027-04-16"}
        for bucket in (1, 2, 3):
            # The heading names are the pin's contract (test_cve_triage_waves.py
            # BUCKET_HEADINGS) — changing them breaks the cross-file agreement.
            print(f"\n{names[bucket]}")
            for cve, category, number, summary in sorted(rows):
                if number != bucket:
                    continue
                versions = [value for value in summary["fixed"] if VERSION_RE.fullmatch(value)]
                fixed = versions[0] if versions else (summary["fixed"][0] if summary["fixed"] else "")
                print(f"| {cve} | {category} | {summary['severity'] or '-'} | "
                      f"{fixed or '-'} | {summary['summary'][:100]} | {review_dates[bucket]} |")

    if args.rewrite_trivyignore:
        today = args.today or __import__("datetime").date.today().isoformat()
        sys.stdout.write(rewrite_trivyignore(args.trivyignore, args.snapshot, today))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
