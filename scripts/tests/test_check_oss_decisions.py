"""
Contract tests for scripts/check_oss_decisions.py (oss-release-remediation
M0, GATE-47).

The M0 decision record (openspec/changes/oss-release-remediation/decisions.md)
must, for every decision row in proposal.md's "Decisions required" table:

- carry a ``## D<n>`` section and a summary-table row (no invented
  decisions, none missing);
- repeat the proposal's owner role letters (U/D/O/L/P, token-compared);
- D1-D8 are DECIDED: a **Chosen option**, an ISO **Decision date** that
  parses and is not in the future, and no TBD/TODO placeholders — the
  summary-table row carries the same option cell and the same date;
- D1 names its W9 drop-dead date in the **Drop-dead date:** field;
- D9 is SCHEDULED and names its decision point W11.14 (M5b).

Plus the Makefile wiring pin: GATE-47 runs in ``quality-gates`` after the
other pilot-record gates.
"""

import importlib.util
import re
import sys
from datetime import date
from pathlib import Path

import pytest

scripts_dir = Path(__file__).parent.parent
sys.path.insert(0, str(scripts_dir))

script_path = scripts_dir / "check_oss_decisions.py"
spec = importlib.util.spec_from_file_location("check_oss_decisions", script_path)
check = importlib.util.module_from_spec(spec)
spec.loader.exec_module(check)

ROOT = scripts_dir.parent
MAKEFILE = ROOT / "Makefile"
TODAY = date(2026, 10, 6)

# The live proposal rows, in mini form: (id, title, owner cell).
DECISION_ROWS = [
    ("D1", "License", "L + U"),
    ("D2", "RLS on the HTTP path", "D + U"),
    ("D3", "SDK publish strategy", "D"),
    ("D4", "SSO fix vs disable", "D + U (IdP)"),
    ("D5", "Paid-feature annotation", "D"),
    ("D6", "dlt metadata-only ingestion", "P + D"),
    ("D7", "Public-remote freeze", "O"),
    ("D8", "Program sequencing (pilot vs OSS)", "U"),
    ("D9", "Third-party pentest before GA", "U"),
]

D1_DROP_DEAD = (
    "- **Drop-dead date:** W9 — final before the W9.1 first semver tag "
    "(order-based target window 2026-11-23 .. 2026-11-29)"
)
D9_LINES = ["- **Decision point:** W11.14 (M5b)", "- **Recommendation recorded:** yes"]


def _proposal(rows=None):
    """A proposal.md-shaped fixture: the Decisions-required table only."""
    rows = DECISION_ROWS if rows is None else rows
    table = "".join(
        f"| {did} | {title} | **Rec** for {did} | {owner} | Blocks |\n"
        for did, title, owner in rows
    )
    return (
        "# Change: probe\n\n## Why\n\nreason.\n\n## What Changes\n\nwork.\n\n"
        "## Impact\n\nnone.\n\n"
        "## Decisions required (blocking the named workstream)\n\n"
        "| # | Decision | Recommendation | Owner | Blocks |\n"
        "|---|---|---|---|---|\n" + table
    )


def _record(spec=None):
    """A decisions.md-shaped fixture; per-decision overrides via spec[did]."""
    spec = spec or {}
    sections = []
    table_rows = []
    for did, title, owner in DECISION_ROWS:
        over = spec.get(did, {})
        if over.get("skip"):
            continue
        status = over.get(
            "status",
            "DECIDED" if did != "D9" else "SCHEDULED — decision point W11.14 (M5b)",
        )
        section_lines = [
            f"## {did} — {title}",
            "",
            f"- **Owner:** {owner}",
            f"- **Status:** {status}",
        ]
        if did == "D9":
            option, decision_date = None, None
        else:
            option = over.get("option", f"Chosen option for {did}")
            decision_date = over.get("date", "2026-10-06")
        if option is not None:
            section_lines.append(f"- **Chosen option:** {option}")
        if decision_date is not None:
            section_lines.append(f"- **Decision date:** {decision_date}")
        if did == "D1":
            section_lines.extend(over.get("extra", [D1_DROP_DEAD]))
        elif did == "D9":
            section_lines.extend(over.get("extra", D9_LINES))
        else:
            section_lines.extend(over.get("extra", []))
        sections.append("\n".join(section_lines) + "\n")

        if not over.get("skip_table"):
            status_cell = over.get("table_status", status.split(None, 1)[0])
            option_cell = (
                over.get("table_option", "Recommendation: yes")
                if did == "D9"
                else over.get("table_option", option)
            )
            date_cell = (
                over.get("table_date", "at W11.14")
                if did == "D9"
                else over.get("table_date", decision_date)
            )
            table_rows.append(
                f"| {did} | {title} | {owner} | {status_cell} | {option_cell} | {date_cell} |"
            )

    if "extra_sections" in spec:
        sections.extend(spec["extra_sections"])
    if "extra_table_rows" in spec:
        table_rows.extend(spec["extra_table_rows"])
    return (
        "# Decisions record — probe\n\n"
        "## Decision summary\n\n"
        "| # | Decision | Owner | Status | Chosen option | Decision date |\n"
        "|---|---|---|---|---|---|\n"
        + "\n".join(table_rows)
        + "\n\n"
        + "\n".join(sections)
    )


@pytest.fixture
def fixture_files(tmp_path):
    record = tmp_path / "decisions.md"
    record.write_text(_record())
    proposal = tmp_path / "proposal.md"
    proposal.write_text(_proposal())
    return record, proposal


def _run(record, proposal, today=TODAY):
    return check.check(record, proposal, today=today)


def test_valid_record_passes(fixture_files):
    problems = _run(*fixture_files)
    assert problems == []


def test_missing_record_fails(tmp_path):
    proposal = tmp_path / "proposal.md"
    proposal.write_text(_proposal())
    problems = _run(tmp_path / "decisions.md", proposal)
    assert any("record missing" in p for p in problems)


def test_missing_proposal_fails(tmp_path):
    record = tmp_path / "decisions.md"
    record.write_text(_record())
    problems = _run(record, tmp_path / "proposal.md")
    assert any("proposal missing" in p for p in problems)


def test_missing_decision_section_fails(fixture_files):
    record, proposal = fixture_files
    record.write_text(_record({"D5": {"skip": True, "skip_table": True}}))
    problems = _run(record, proposal)
    assert any("D5" in p and "no `## D5`" in p for p in problems)


def test_invented_section_fails(fixture_files):
    record, proposal = fixture_files
    record.write_text(
        _record(
            {
                "extra_sections": [
                    "## D10 — Invented\n\n- **Owner:** D\n- **Status:** DECIDED\n"
                    "- **Chosen option:** x\n- **Decision date:** 2026-10-06\n"
                ]
            }
        )
    )
    problems = _run(record, proposal)
    assert any("D10" in p and "proposal" in p for p in problems)


def test_invented_table_row_fails(fixture_files):
    record, proposal = fixture_files
    record.write_text(
        _record(
            {"extra_table_rows": ["| D10 | Invented | D | DECIDED | x | 2026-10-06 |"]}
        )
    )
    problems = _run(record, proposal)
    assert any("D10" in p for p in problems)


def test_owner_mismatch_fails(fixture_files):
    record, proposal = fixture_files
    record.write_text(
        _record({"D6": {"option": None}}).replace(
            "- **Owner:** P + D", "- **Owner:** D", 1
        )
    )
    problems = _run(record, proposal)
    assert any("D6" in p and "owner" in p for p in problems)


def test_status_not_decided_fails(fixture_files):
    record, proposal = fixture_files
    record.write_text(_record({"D3": {"status": "SCHEDULED — decision point later"}}))
    problems = _run(record, proposal)
    assert any("D3" in p and "DECIDED" in p for p in problems)


def test_missing_option_fails(fixture_files):
    record, proposal = fixture_files
    record.write_text(_record({"D2": {"option": None}}))
    problems = _run(record, proposal)
    assert any("D2" in p and "Chosen option" in p for p in problems)


def test_placeholder_option_fails(fixture_files):
    record, proposal = fixture_files
    record.write_text(_record({"D2": {"option": "TODO decide later"}}))
    problems = _run(record, proposal)
    assert any("D2" in p and "placeholder" in p for p in problems)


def test_missing_date_fails(fixture_files):
    record, proposal = fixture_files
    record.write_text(_record({"D2": {"date": None}}))
    problems = _run(record, proposal)
    assert any("D2" in p and "Decision date" in p for p in problems)


def test_malformed_date_fails(fixture_files):
    record, proposal = fixture_files
    record.write_text(_record({"D2": {"date": "2026-10-6"}}))
    problems = _run(record, proposal)
    assert any("D2" in p and "YYYY-MM-DD" in p for p in problems)


def test_impossible_date_fails(fixture_files):
    record, proposal = fixture_files
    record.write_text(_record({"D2": {"date": "2026-99-99"}}))
    problems = _run(record, proposal)
    assert any("D2" in p and "not a real date" in p for p in problems)


def test_future_date_fails(fixture_files):
    record, proposal = fixture_files
    record.write_text(_record({"D2": {"date": "2099-01-01"}}))
    problems = _run(record, proposal)
    assert any("D2" in p and "future" in p for p in problems)


def test_d1_without_w9_in_drop_dead_fails(fixture_files):
    record, proposal = fixture_files
    record.write_text(
        _record(
            {"D1": {"extra": ["- **Drop-dead date:** before the first semver tag"]}}
        )
    )
    problems = _run(record, proposal)
    assert any("D1" in p and "W9" in p for p in problems)


def test_d1_without_drop_dead_field_fails(fixture_files):
    record, proposal = fixture_files
    record.write_text(_record({"D1": {"extra": []}}))
    problems = _run(record, proposal)
    assert any("D1" in p and "Drop-dead date" in p for p in problems)


def test_d9_decided_fails(fixture_files):
    record, proposal = fixture_files
    record.write_text(
        _record(
            {
                "D9": {
                    "status": "DECIDED",
                    "option": "yes",
                    "date": "2026-10-06",
                    "extra": [],
                }
            }
        )
    )
    problems = _run(record, proposal)
    assert any("D9" in p and "SCHEDULED" in p for p in problems)


def test_d9_without_decision_point_fails(fixture_files):
    record, proposal = fixture_files
    # Drop both the Decision point line and the W11.14 mention in the
    # status — the section must name the point itself.
    record.write_text(_record({"D9": {"extra": [], "status": "SCHEDULED"}}))
    problems = _run(record, proposal)
    assert any("D9" in p and "W11.14" in p for p in problems)
    assert any("D9" in p and "Decision point" in p for p in problems)


def test_missing_table_row_fails(fixture_files):
    record, proposal = fixture_files
    record.write_text(_record({"D4": {"skip_table": True}}))
    problems = _run(record, proposal)
    assert any("D4" in p and "summary-table row" in p for p in problems)


def test_table_date_mismatch_fails(fixture_files):
    record, proposal = fixture_files
    record.write_text(_record({"D2": {"table_date": "2026-10-05"}}))
    problems = _run(record, proposal)
    assert any("D2" in p and "table date" in p for p in problems)


def test_table_status_mismatch_fails(fixture_files):
    record, proposal = fixture_files
    record.write_text(_record({"D2": {"table_status": "PENDING"}}))
    problems = _run(record, proposal)
    assert any("D2" in p and "status" in p for p in problems)


def test_table_option_placeholder_fails(fixture_files):
    record, proposal = fixture_files
    record.write_text(_record({"D2": {"table_option": "TBD"}}))
    problems = _run(record, proposal)
    assert any("D2" in p and "table" in p and "placeholder" in p for p in problems)


def test_d9_table_date_needs_w11_14(fixture_files):
    record, proposal = fixture_files
    record.write_text(_record({"D9": {"table_date": "2027-01-01"}}))
    problems = _run(record, proposal)
    assert any("D9" in p and "W11.14" in p for p in problems)


def test_proposal_without_decision_rows_fails(tmp_path):
    record = tmp_path / "decisions.md"
    record.write_text(_record())
    proposal = tmp_path / "proposal.md"
    proposal.write_text(_proposal(rows=[]))
    problems = _run(record, proposal)
    assert any("no decision rows" in p for p in problems)


def test_default_paths_exist():
    assert (ROOT / "openspec/changes/oss-release-remediation/decisions.md").exists()
    assert (ROOT / "openspec/changes/oss-release-remediation/proposal.md").exists()


class TestMainContract:
    def test_problems_exit_1(self, fixture_files, monkeypatch):
        record, proposal = fixture_files
        record.write_text(_record({"D2": {"option": None}}))
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "check_oss_decisions.py",
                "--record",
                str(record),
                "--proposal",
                str(proposal),
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            check.main()
        assert exc_info.value.code == 1

    def test_clean_exits_0(self, fixture_files, monkeypatch):
        record, proposal = fixture_files
        monkeypatch.setattr(
            sys,
            "argv",
            [
                "check_oss_decisions.py",
                "--record",
                str(record),
                "--proposal",
                str(proposal),
            ],
        )
        with pytest.raises(SystemExit) as exc_info:
            check.main()
        assert exc_info.value.code == 0


def _quality_gates_recipe() -> list[str]:
    text = MAKEFILE.read_text()
    match = re.search(r"^quality-gates:.*\n((?:\t.*\n)+)", text, re.MULTILINE)
    assert match, "quality-gates target not found in Makefile"
    return list(match.group(1).splitlines())


class TestQualityGatesWiring:
    def test_gate47_wired_into_quality_gates(self):
        recipe = _quality_gates_recipe()
        joined = "\n".join(recipe)
        assert "check_oss_decisions.py" in joined, "GATE-47 must run in quality-gates"

    def test_gate47_runs_after_the_pilot_record_gates(self):
        recipe = _quality_gates_recipe()
        gate47 = next(
            i for i, ln in enumerate(recipe) if "check_oss_decisions.py" in ln
        )
        # The GATE-46 line lands with the pilot's quality-gates block; the
        # ordering assertion applies once both gates are wired.
        gate46 = [i for i, ln in enumerate(recipe) if "check_privacy_pack.py" in ln]
        if gate46:
            assert (
                gate46[0] < gate47
            ), "the decisions gate runs after the privacy-pack gate"
