"""CVE triage-wave pins (close-oss-release-conditions P0-2) — Django-free,
CI no-django lint.

These pins keep the pinned-CVE triage waves HONEST:

* the wave ledger exists and records the starting overdue count, the
  wave-1 processed count (at least 25% of the starting set per the
  task's per-wave floor) and the strict-gate end state;
* every ``.trivyignore`` entry is bucketed EXACTLY once in the bucket
  evidence (no un-triaged entry, no double-bucket) with a next-review
  date and a rationale cell;
* every ``.trivyignore`` entry carries a review date in the FUTURE (the
  checker's own parser is the source of truth — a lapsed or missing
  date flips this RED);
* the OSV snapshot the buckets were derived from exists on disk and is
  cited by the wave ledger (the evidence is reproducible, not asserted);
* ``audit_pinned_cves.py --strict`` exits 0 (the authoritative gate —
  the wave is not done until the real checker agrees).
"""

from __future__ import annotations

import datetime
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from audit_pinned_cves import parse_trivyignore  # real parser, no reimplementation

TRIVYIGNORE = REPO_ROOT / ".trivyignore"
TRIAGE_DIR = REPO_ROOT / "docs" / "audits" / "cve-triage-2026"
WAVE_LEDGER = TRIAGE_DIR / "README.md"
WAVE_01 = TRIAGE_DIR / "wave-01.md"
OSV_SNAPSHOT = TRIAGE_DIR / "osv-snapshot-2026-10-18.json"

BUCKET_HEADINGS = (
    "## Bucket 1 — fix released",
    "## Bucket 2 — fix pending",
    "## Bucket 3 — not applicable",
)

CVE_RE = re.compile(r"CVE-\d{4}-\d{3,7}")


def _text(path: Path) -> str:
    assert path.is_file(), f"expected committed artifact: {path}"
    return path.read_text(encoding="utf-8")


def _bucket_cves(heading: str) -> set[str]:
    """Every CVE token under a bucket heading until the next heading."""
    lines = _text(WAVE_01).splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(heading)), None)
    if start is None:
        return set()
    cves: set[str] = set()
    for line in lines[start + 1 :]:
        if line.startswith("## ") and not line.startswith(heading):
            break
        cves.update(CVE_RE.findall(line))
    return cves


def _starting_overdue_count() -> int:
    """The wave ledger's recorded starting overdue count (a fact of the
    pre-wave state — recorded, not recomputed)."""
    match = re.search(r"\*\*Starting overdue count:\*\* (\d+)", _text(WAVE_LEDGER))
    assert match, "wave ledger must record the starting overdue count"
    return int(match.group(1))


def _wave_processed_count() -> int:
    match = re.search(r"\*\*Wave-1 processed count:\*\* (\d+)", _text(WAVE_LEDGER))
    assert match, "wave ledger must record the wave-1 processed count"
    return int(match.group(1))


def test_wave_ledger_records_start_and_processing_floor():
    starting = _starting_overdue_count()
    processed = _wave_processed_count()
    assert starting > 0, "starting overdue count must be positive"
    assert processed >= starting * 0.25, (
        f"wave 1 processed {processed} of {starting} — below the 25% per-wave floor"
    )


def test_every_trivyignore_entry_bucketed_exactly_once():
    entries = {entry.cve for entry in parse_trivyignore(TRIVYIGNORE)}
    buckets = {heading: _bucket_cves(heading) for heading in BUCKET_HEADINGS}
    assert entries, "no .trivyignore entries parsed — did the file disappear?"
    unbucketed = entries - set().union(*buckets.values())
    assert not unbucketed, f".trivyignore entries missing from the buckets: {sorted(unbucketed)}"
    for heading in BUCKET_HEADINGS:
        for other in BUCKET_HEADINGS:
            if heading is not other:
                overlap = buckets[heading] & buckets[other]
                assert not overlap, f"CVEs in two buckets ({heading}): {sorted(overlap)}"


def test_bucket_rows_carry_rationale_and_next_review():
    """A bucket row without a next-review date or a rationale is not
    evidence — it is the rot this gate exists to prevent."""
    lines = _text(WAVE_01).splitlines()
    for index, line in enumerate(lines):
        if not line.strip().startswith("|") or not CVE_RE.search(line):
            continue
        if (index > 0 and lines[index - 1].startswith("|---")) or "---" in line:
            continue
        assert re.search(r"\d{4}-\d{2}-\d{2}", line), f"bucket row lacks a date: {line!r}"
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        assert len(cells) >= 4, f"bucket row malformed: {line!r}"


def test_all_trivyignore_entries_have_future_review_dates():
    today = datetime.date.today()
    for entry in parse_trivyignore(TRIVYIGNORE):
        assert entry.review_by is not None, f"{entry.cve} has no Review by: date"
        assert entry.review_by > today, f"{entry.cve} review date not in the future: {entry.review_by}"


def test_osv_snapshot_exists_and_is_cited():
    _text(OSV_SNAPSHOT)
    assert "osv-snapshot-2026-10-18.json" in _text(WAVE_LEDGER), (
        "wave ledger must cite the OSV snapshot"
    )


def test_strict_gate_clean():
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "audit_pinned_cves.py"), "--strict"],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        "audit_pinned_cves --strict not clean:\n" + result.stderr[-3000:]
    )
