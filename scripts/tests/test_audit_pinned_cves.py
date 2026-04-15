"""Tests for ``scripts/audit_pinned_cves.py`` — Phase 225.2.

Drives the pinned-CVE tracker via TDD:
 * Parses CVE comments in ``requirements.txt`` (``pkg==1.2.3  # CVE-…``).
 * Parses ``.trivyignore`` for CVE ids + "Review by: <date>" markers.
 * Computes review status (``overdue`` / ``due_soon`` / ``ok``) relative to a
   configurable "today" so tests are deterministic.
 * Exits 0 on ``--non-blocking`` (default CI mode) even when overdue entries
   exist — it prints the summary and sets ``GITHUB_STEP_SUMMARY`` if the env
   var is set.
 * Exits 1 in strict mode (``--strict``) when any overdue entry is found so
   the monthly scheduled workflow actually breaks and opens an issue.

No mocks: all tests hit real files created in ``tmp_path``.
"""
from __future__ import annotations

import datetime
import importlib.util
import pathlib
import subprocess
import sys
import textwrap

import pytest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parents[1]
SCRIPT_PATH = SCRIPTS_DIR / "audit_pinned_cves.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("audit_pinned_cves", SCRIPT_PATH)
    assert spec and spec.loader, "audit_pinned_cves.py missing"
    module = importlib.util.module_from_spec(spec)
    # Register before exec so `@dataclass` can resolve the module lazily —
    # the dataclass decorator looks up ``cls.__module__`` in ``sys.modules``
    # while processing the class body.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def mod():
    return _load_module()


# ---------------------------------------------------------------------------
# parse_requirements_cves
# ---------------------------------------------------------------------------


def test_parse_requirements_extracts_single_cve(tmp_path, mod):
    req = tmp_path / "requirements.txt"
    req.write_text("PyJWT==2.12.0  # CVE-2026-32597: accepts unknown crit header\n")
    entries = mod.parse_requirements_cves(req)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.package == "PyJWT"
    assert entry.version == "2.12.0"
    assert entry.cve == "CVE-2026-32597"
    assert "accepts unknown crit" in entry.note


def test_parse_requirements_extracts_multiple_cves_from_one_line(tmp_path, mod):
    req = tmp_path / "requirements.txt"
    req.write_text(
        "cryptography==46.0.5  # CVE-2026-26007, CVE-2026-26008: subgroup attack\n"
    )
    entries = mod.parse_requirements_cves(req)
    assert {e.cve for e in entries} == {"CVE-2026-26007", "CVE-2026-26008"}


def test_parse_requirements_ignores_lines_without_cve(tmp_path, mod):
    req = tmp_path / "requirements.txt"
    req.write_text(
        textwrap.dedent(
            """
            Django==5.2.1
            # comment-only line
            requests==2.32.3  # not a CVE reference
            flask==3.0.0  # CVE-2026-99999: pinned
            """
        ).strip()
    )
    entries = mod.parse_requirements_cves(req)
    assert [e.cve for e in entries] == ["CVE-2026-99999"]


def test_parse_requirements_skips_missing_file(tmp_path, mod):
    entries = mod.parse_requirements_cves(tmp_path / "does-not-exist.txt")
    assert entries == []


# ---------------------------------------------------------------------------
# parse_trivyignore
# ---------------------------------------------------------------------------


def test_parse_trivyignore_captures_cves_and_review_date(tmp_path, mod):
    ti = tmp_path / ".trivyignore"
    ti.write_text(
        textwrap.dedent(
            """
            # Added: 2026-04-03 (Phase 211 pipeline unblock)
            # Review by: 2026-05-03
            CVE-2026-24882
            CVE-2026-4046

            # Added: 2026-04-09 (worker-service trivy gate failure — 4th consecutive)
            # Review by: 2026-05-09
            CVE-2026-31411
            """
        ).strip()
    )
    entries = mod.parse_trivyignore(ti)
    by_cve = {e.cve: e for e in entries}
    assert by_cve["CVE-2026-24882"].review_by == datetime.date(2026, 5, 3)
    assert by_cve["CVE-2026-4046"].review_by == datetime.date(2026, 5, 3)
    assert by_cve["CVE-2026-31411"].review_by == datetime.date(2026, 5, 9)


def test_parse_trivyignore_handles_cves_without_review_date(tmp_path, mod):
    ti = tmp_path / ".trivyignore"
    ti.write_text("CVE-2020-12345\n")
    entries = mod.parse_trivyignore(ti)
    assert entries[0].cve == "CVE-2020-12345"
    assert entries[0].review_by is None


def test_parse_trivyignore_skips_missing_file(tmp_path, mod):
    assert mod.parse_trivyignore(tmp_path / "nope") == []


# ---------------------------------------------------------------------------
# classify_review_status
# ---------------------------------------------------------------------------


def test_classify_overdue(mod):
    today = datetime.date(2026, 6, 1)
    s = mod.classify_review_status(datetime.date(2026, 5, 3), today=today)
    assert s == "overdue"


def test_classify_due_soon(mod):
    today = datetime.date(2026, 4, 20)
    s = mod.classify_review_status(datetime.date(2026, 5, 3), today=today)
    assert s == "due_soon"  # 13 days <= 14-day window


def test_classify_ok_far_future(mod):
    today = datetime.date(2026, 4, 1)
    s = mod.classify_review_status(datetime.date(2026, 5, 3), today=today)
    assert s == "ok"


def test_classify_none_review_date_returns_unknown(mod):
    s = mod.classify_review_status(None, today=datetime.date(2026, 4, 1))
    assert s == "unknown"


# ---------------------------------------------------------------------------
# main (CLI): exit codes and GITHUB_STEP_SUMMARY output
# ---------------------------------------------------------------------------


def _run(tmp_path: pathlib.Path, *args: str, env: dict | None = None):
    """Run the script from tmp_path so it picks up fixture files."""
    cmd = [sys.executable, str(SCRIPT_PATH), *args]
    return subprocess.run(
        cmd,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        env={**(env or {})},
    )


def _write_fixtures(tmp_path, *, review_by: str = "2026-05-03"):
    (tmp_path / "requirements.txt").write_text(
        "PyJWT==2.12.0  # CVE-2026-32597: pinned fix\n"
    )
    (tmp_path / ".trivyignore").write_text(
        f"# Review by: {review_by}\nCVE-2026-24882\n"
    )


def test_cli_non_blocking_exits_zero_even_when_overdue(tmp_path):
    _write_fixtures(tmp_path, review_by="2020-01-01")  # long past
    result = _run(tmp_path, "--today", "2026-04-15", "--non-blocking")
    assert result.returncode == 0
    assert "OVERDUE" in result.stdout.upper() or "OVERDUE" in result.stderr.upper()


def test_cli_strict_exits_nonzero_when_overdue(tmp_path):
    _write_fixtures(tmp_path, review_by="2020-01-01")
    result = _run(tmp_path, "--today", "2026-04-15", "--strict")
    assert result.returncode != 0


def test_cli_strict_exits_zero_when_clean(tmp_path):
    _write_fixtures(tmp_path, review_by="2099-01-01")
    result = _run(tmp_path, "--today", "2026-04-15", "--strict")
    assert result.returncode == 0


def test_cli_strict_fails_on_unknown_review_date(tmp_path):
    """An ignored CVE missing a 'Review by:' comment must fail --strict so
    indefinite exceptions cannot slip past the monthly audit silently."""
    (tmp_path / "requirements.txt").write_text("")
    (tmp_path / ".trivyignore").write_text("CVE-2020-99999\n")  # no date
    result = _run(tmp_path, "--today", "2026-04-15", "--strict")
    assert result.returncode != 0
    assert "UNKNOWN" in (result.stdout + result.stderr).upper()


def test_cli_non_blocking_exits_zero_on_unknown(tmp_path):
    """Non-blocking still exits 0 so UNKNOWN entries only surface in the
    job step summary at PR time, not fail the PR build."""
    (tmp_path / "requirements.txt").write_text("")
    (tmp_path / ".trivyignore").write_text("CVE-2020-99999\n")
    result = _run(tmp_path, "--today", "2026-04-15", "--non-blocking")
    assert result.returncode == 0


def test_cli_writes_github_step_summary(tmp_path):
    summary = tmp_path / "summary.md"
    _write_fixtures(tmp_path, review_by="2026-05-03")
    result = _run(
        tmp_path,
        "--today",
        "2026-04-15",
        "--non-blocking",
        env={"GITHUB_STEP_SUMMARY": str(summary)},
    )
    assert result.returncode == 0
    text = summary.read_text()
    assert "Pinned CVE audit" in text
    assert "CVE-2026-24882" in text or "CVE-2026-32597" in text
