"""W10.5 (oss-release-remediation) — deferred-debt ticket + triage pins.

These pins keep the M5 deferral bookkeeping HONEST (Django-free, CI
no-django lint):

* design.md §8 (the deferral list) is a ticket table: every item row
  carries exactly one ``TICKET=`` ID of the canonical shape and the IDs
  are unique (two deferrals sharing a ticket is a silent merge);
* every §8 row's routing cell is non-empty and the section cites the
  follow-up backlog change (the triage destination);
* every §8 ticket appears in the backlog change's §8 triage table with a
  non-empty routing — a §8 ticket nobody triaged flips this RED (the
  cross-file agreement the ``w105-tickets`` condition promises);
* the seven findings promised "ticket at W10.5" by the W10.2 soak ledger
  (§4) / W10.3 F3 / the estate-migration-surgery condition each carry a
  ticket row in the backlog's carryover table;
* the backlog change passes the repo's openspec structural validator
  (real cross-check — a scaffold-only follow-up change is not a triage);
* tasks.md W10.5 is checked and cites design.md §8, the backlog change
  and this pin;
* the go/no-go ledger's ``w105-tickets`` condition records the execution
  with the same citations (the stop-the-line condition stays honest).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from validate_openspec_change import collect_violations

DESIGN = REPO_ROOT / "openspec" / "changes" / "oss-release-remediation" / "design.md"
TASKS = REPO_ROOT / "openspec" / "changes" / "oss-release-remediation" / "tasks.md"
LEDGER = REPO_ROOT / "docs" / "operations" / "oss-go-nogo-ledger.md"
BACKLOG = REPO_ROOT / "openspec" / "changes" / "track-oss-deferred-debt"
BACKLOG_TASKS = BACKLOG / "tasks.md"

TICKET_RE = re.compile(r"TICKET=([A-Z0-9][A-Z0-9-]*)")
S8_HEADING = "## 8. Deferred to post-release"
S8_TRIAGE_HEADING = "### design.md §8 deferral triage"
CARRIED_HEADING = "### W10.2-carried findings"

# The findings the W10.2 soak ledger §4 / W10.3 F3 / the estate-migration
# condition promised a "ticket at W10.5" for — each must land in the backlog.
CARRIED_TICKETS = {
    "W105-COMPLIANCE-DISPATCH-ENQUEUE",
    "W105-COMPOSE-SUPERVISOR-RESTART",
    "W105-REDIS-AOF-RUNBOOK",
    "W105-ASYNC-LISTENER-LIVENESS",
    "W105-SOAK-72H-REMAINING",
    "W105-BILLING-REFUND-LEDGER",
    "W105-ESTATE-MIGRATION-SURGERY",
}


def _text(path: Path) -> str:
    assert path.is_file(), f"expected committed artifact: {path}"
    return path.read_text(encoding="utf-8")


def _ticket(cells: list[str]) -> str | None:
    for cell in cells:
        match = TICKET_RE.search(cell)
        if match:
            return match.group(1)
    return None


def _is_separator(row: list[str]) -> bool:
    return bool(row) and all(re.fullmatch(r":?-+:?", cell) for cell in row)


def _table_rows(lines: list[str], stop_at_heading: bool = True) -> list[list[str]]:
    """Split table lines into cell lists; drop separator rows and the
    header row (the first non-separator table line, by construction of
    the triage tables)."""
    rows = []
    seen_header = False
    for line in lines:
        if stop_at_heading and line.startswith("#"):
            break
        if not line.strip().startswith("|"):
            continue
        row = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if _is_separator(row):
            continue
        if not seen_header:
            seen_header = True
            continue
        rows.append(row)
    return rows


def _section8() -> list[list[str]]:
    """design.md §8 item rows: the table under the §8 heading until the
    next top-level heading (or EOF)."""
    lines = _text(DESIGN).splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith(S8_HEADING))
    return _table_rows(lines[start + 1 :])


def _backlog_section_rows(heading: str) -> list[list[str]]:
    lines = _text(BACKLOG_TASKS).splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(heading)), None)
    if start is None:
        return []
    return _table_rows(lines[start + 1 :])


def test_section8_every_item_carries_a_unique_canonical_ticket():
    rows = _section8()
    assert len(rows) >= 10, f"§8 must carry the full deferral table (got {len(rows)} rows)"
    tickets = []
    for row in rows:
        assert len(row) >= 4, f"§8 row malformed: {row}"
        ticket = _ticket(row)
        assert ticket, f"§8 item row carries no TICKET= ID: {row}"
        assert re.fullmatch(r"[A-Z0-9][A-Z0-9-]*", ticket), (
            f"non-canonical §8 ticket {ticket!r}"
        )
        tickets.append(ticket)
    assert len(tickets) == len(set(tickets)), f"§8 tickets must be unique: {tickets}"


def test_section8_routing_cites_the_backlog_change():
    rows = _section8()
    routing_cells = [row[3] for row in rows]
    assert all(cell for cell in routing_cells), "every §8 row must have a non-empty routing"
    assert any("track-oss-deferred-debt" in cell for cell in routing_cells), (
        "§8 routing must cite the follow-up backlog change"
    )


def test_every_section8_ticket_is_triaged_in_the_backlog():
    section8_tickets = [_ticket(row) for row in _section8()]
    triage = _backlog_section_rows(S8_TRIAGE_HEADING)
    assert triage, f"backlog must carry the §8 triage table under {S8_TRIAGE_HEADING!r}"
    triaged = {}
    for row in triage:
        ticket = _ticket(row)
        if ticket is not None:
            triaged[ticket] = row[-1]
    missing = [ticket for ticket in section8_tickets if ticket not in triaged]
    assert not missing, f"§8 tickets missing from the backlog triage: {missing}"
    for ticket, routing in triaged.items():
        assert routing, f"backlog triage row for {ticket} has an empty routing"


def test_w102_carried_findings_ticketed_in_the_backlog():
    carried = _backlog_section_rows(CARRIED_HEADING)
    assert carried, f"backlog must carry the carryover table under {CARRIED_HEADING!r}"
    carried_tickets = {_ticket(row) for row in carried}
    missing = CARRIED_TICKETS - carried_tickets
    assert not missing, f"W10.2-carried findings missing their W10.5 tickets: {missing}"


def test_backlog_change_passes_the_openspec_structural_validator():
    violations = collect_violations(BACKLOG)
    assert violations == [], "backlog change structural violations:\n" + "\n".join(violations)


def test_tasks_w105_checked_with_evidence():
    tasks = _text(TASKS)
    match = re.search(r"^- \[([ x])\] W10\.5 .*$", tasks, re.MULTILINE)
    assert match, "tasks.md W10.5 line missing"
    assert match.group(1) == "x", "tasks.md W10.5 must be checked"
    for citation in (
        "design.md",
        "openspec/changes/track-oss-deferred-debt/tasks.md",
        "scripts/tests/test_w105_deferred_debt_triage.py",
    ):
        assert citation in tasks, f"tasks.md W10.5 evidence must cite {citation}"


def test_ledger_w105_condition_records_execution():
    text = _text(LEDGER)
    match = re.search(r"^\|\s*w105-tickets\s*\|(.*)\|\s*$", text, re.MULTILINE)
    assert match, "ledger w105-tickets condition row missing"
    row = match.group(1)
    assert "track-oss-deferred-debt" in row, "ledger must cite the backlog change"
    assert "test_w105_deferred_debt_triage.py" in row, "ledger must cite the W10.5 pin"
