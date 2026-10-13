#!/usr/bin/env python3
"""
GATE-47 (oss-release-remediation M0) — the D1-D9 decision-record contract
checker.

The M0 decision record (openspec/changes/oss-release-remediation/decisions.md)
must, for every decision row in proposal.md's "Decisions required" table:

- carry a ``## D<n>`` section and a summary-table row (no invented
  decisions, none missing);
- repeat the proposal's owner role letters (U/D/O/L/P, token-compared —
  the record's owners must come from proposal.md);
- D1-D8 are DECIDED: a **Chosen option**, an ISO **Decision date** that
  parses and is not in the future, and no TBD/TODO placeholders — the
  summary-table row carries the same option cell and the same date;
- D1 names its W9 drop-dead date in the **Drop-dead date:** field (the
  M0 evidence requirement);
- D9 is SCHEDULED and names its decision point W11.14 (M5b) — the pentest
  call is taken there, not at M0.

Exit 0 when the record satisfies the contract; 1 otherwise, each problem
named.
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
RECORD_DEFAULT = _ROOT / "openspec/changes/oss-release-remediation/decisions.md"
PROPOSAL_DEFAULT = _ROOT / "openspec/changes/oss-release-remediation/proposal.md"

# Roles recognized by the proposal's owner legend. Word boundaries keep
# "(IdP)" in "D + U (IdP)" from contributing a phantom "P" owner.
_OWNER_TOKEN = re.compile(r"\b[UDOLP]\b")

# The M0 task records D1-D8 as decided; D9's decision point is W11.14
# (M5b) per proposal.md's Blocks column and tasks.md W11.14.
_DECIDED_AT_M0 = {f"D{i}" for i in range(1, 9)}
_D9_DECISION_POINT = "W11.14"

_PROPOSAL_ROW = re.compile(r"^\|\s*(D\d+)\s*\|")
_SECTION = re.compile(r"^##\s+(D\d+)\b")
_TABLE_ROW = re.compile(r"^\|\s*(D\d+)\s*\|")
_FIELD = re.compile(r"^-\s+\*\*([A-Za-z][A-Za-z -]*?):\*\*\s?(.*)$")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_PLACEHOLDER = re.compile(r"\b(TBD|TODO|PLACEHOLDER|XXX)\b", re.I)


def _proposal_decisions(text: str) -> tuple[dict[str, tuple[str, set[str]]], list[str]]:
    """id -> (title, owner tokens) parsed from the Decisions-required table."""
    decisions: dict[str, tuple[str, set[str]]] = {}
    problems: list[str] = []
    for line in text.splitlines():
        match = _PROPOSAL_ROW.match(line)
        if not match:
            continue
        did = match.group(1)
        cells = line.split("|")
        if len(cells) < 6:
            problems.append(f"proposal row {did} is malformed ({len(cells)} cells)")
            continue
        title = cells[2].strip()
        owner_tokens = set(_OWNER_TOKEN.findall(cells[4]))
        if not owner_tokens:
            problems.append(
                f"proposal row {did} has no owner role letters in {cells[4]!r}"
            )
            continue
        decisions[did] = (title, owner_tokens)
    return decisions, problems


def _record_sections(text: str) -> dict[str, str]:
    """id -> section body (lines between the heading and the next one)."""
    sections: dict[str, str] = {}
    current: str | None = None
    body: list[str] = []
    for line in text.splitlines():
        match = _SECTION.match(line)
        if match:
            if current is not None:
                sections[current] = "\n".join(body)
            current = match.group(1)
            body = []
        elif current is not None:
            body.append(line)
    if current is not None:
        sections[current] = "\n".join(body)
    return sections


def _fields(section: str) -> dict[str, str]:
    """Bulleted ``**Name:** value`` lines inside one decision section."""
    fields: dict[str, str] = {}
    for line in section.splitlines():
        match = _FIELD.match(line)
        if match:
            fields[match.group(1).strip()] = match.group(2).strip()
    return fields


def _table_rows(text: str) -> dict[str, list[str]]:
    """id -> split cells for the summary-table rows."""
    rows: dict[str, list[str]] = {}
    for line in text.splitlines():
        match = _TABLE_ROW.match(line)
        if match:
            rows[match.group(1)] = line.split("|")
    return rows


def _decided_checks(did: str, fields: dict[str, str], today: date) -> list[str]:
    """The option + date requirements for a DECIDED row."""
    problems: list[str] = []
    option = fields.get("Chosen option", "")
    if not option:
        problems.append(f"decision {did}: missing **Chosen option:**")
    elif _PLACEHOLDER.search(option):
        problems.append(f"decision {did}: unresolved placeholder in the chosen option")
    date_cell = fields.get("Decision date", "")
    iso = _ISO_DATE.match(date_cell)
    if not iso:
        problems.append(
            f"decision {did}: **Decision date:** must be ISO YYYY-MM-DD, found {date_cell!r}"
        )
        return problems
    try:
        decided = date.fromisoformat(date_cell)
    except ValueError:
        problems.append(
            f"decision {did}: **Decision date:** {date_cell!r} is not a real date"
        )
        return problems
    if decided > today:
        problems.append(
            f"decision {did}: decision date {decided} is in the future (today {today})"
        )
    return problems


def _check_section(
    did: str, owner_tokens: set[str], section: str, fields: dict[str, str], today: date
) -> list[str]:
    problems: list[str] = []
    owner_match = set(_OWNER_TOKEN.findall(fields.get("Owner", "")))
    if owner_match != owner_tokens:
        problems.append(
            f"decision {did}: owner {sorted(owner_match)!r} does not match proposal owner "
            f"{sorted(owner_tokens)!r}"
        )
    status = fields.get("Status", "").strip()
    status_word = status.split(None, 1)[0] if status else ""
    if did in _DECIDED_AT_M0:
        if status_word != "DECIDED":
            problems.append(
                f"decision {did}: M0 requires Status DECIDED, found {status!r}"
            )
        problems.extend(_decided_checks(did, fields, today))
        if did == "D1":
            drop_dead = fields.get("Drop-dead date", "")
            if not drop_dead:
                problems.append("decision D1: missing **Drop-dead date:** field")
            elif "W9" not in drop_dead:
                problems.append(
                    "decision D1: the **Drop-dead date:** field does not name W9 "
                    "(evidence: 'D1 has a W9 drop-dead date')"
                )
    elif did == "D9":
        if status_word != "SCHEDULED":
            problems.append(
                f"decision D9: expected Status SCHEDULED (decision point "
                f"{_D9_DECISION_POINT}), found {status!r}"
            )
        if _D9_DECISION_POINT not in section:
            problems.append(
                f"decision D9: the {_D9_DECISION_POINT} decision point is not named"
            )
        if not fields.get("Decision point"):
            problems.append("decision D9: missing **Decision point:** field")
    elif status_word == "DECIDED":
        # Future decisions: DECIDED needs option + date; SCHEDULED needs a
        # named decision point.
        problems.extend(_decided_checks(did, fields, today))
    elif status_word == "SCHEDULED":
        if not fields.get("Decision point"):
            problems.append(
                f"decision {did}: SCHEDULED requires a **Decision point:** field"
            )
    else:
        problems.append(
            f"decision {did}: Status must be DECIDED or SCHEDULED, found {status!r}"
        )
    for word in sorted(set(_PLACEHOLDER.findall(section))):
        problems.append(
            f"decision {did}: unresolved placeholder {word!r} in the section"
        )
    return problems


def _check_table_row(
    did: str, fields: dict[str, str], cells: list[str] | None
) -> list[str]:
    problems: list[str] = []
    if cells is None:
        problems.append(f"decision {did}: missing summary-table row")
        return problems
    if len(cells) < 7:
        problems.append(
            f"decision {did}: summary-table row is malformed ({len(cells)} cells)"
        )
        return problems
    status_cell = cells[4].strip()
    section_status = fields.get("Status", "").strip()
    expected_status = section_status.split(None, 1)[0] if section_status else ""
    if status_cell != expected_status:
        problems.append(
            f"decision {did}: table status {status_cell!r} != section status {expected_status!r}"
        )
    option_cell = cells[5].strip()
    date_cell = cells[6].strip()
    if did in _DECIDED_AT_M0:
        if not option_cell:
            problems.append(
                f"decision {did}: summary-table chosen-option cell is empty"
            )
        elif _PLACEHOLDER.search(option_cell):
            problems.append(
                f"decision {did}: summary-table chosen-option cell has an unresolved placeholder"
            )
        if date_cell != fields.get("Decision date", ""):
            problems.append(
                f"decision {did}: summary-table date {date_cell!r} != section date "
                f"{fields.get('Decision date')!r}"
            )
    elif did == "D9":
        if _D9_DECISION_POINT not in date_cell:
            problems.append(
                f"decision D9: summary-table date cell must name "
                f"{_D9_DECISION_POINT}, found {date_cell!r}"
            )
    return problems


def check(
    record_path: Path, proposal_path: Path, today: date | None = None
) -> list[str]:
    today = today or date.today()
    if not proposal_path.exists():
        return [f"proposal missing: {proposal_path}"]
    if not record_path.exists():
        return [f"decision record missing: {record_path}"]
    decisions, problems = _proposal_decisions(proposal_path.read_text())
    if not decisions:
        problems.append(
            "no decision rows parsed from the proposal's Decisions-required table"
        )
        return problems
    text = record_path.read_text()
    sections = _record_sections(text)
    table = _table_rows(text)
    for did, (title, owner_tokens) in decisions.items():
        section = sections.get(did)
        if section is None:
            problems.append(
                f"decision {did} ({title}) has no `## {did}` section in the record"
            )
            continue
        fields = _fields(section)
        problems.extend(_check_section(did, owner_tokens, section, fields, today))
        problems.extend(_check_table_row(did, fields, table.get(did)))
    for did in sorted(set(sections) - set(decisions)):
        problems.append(
            f"recorded decision {did} has no row in the proposal's Decisions-required table"
        )
    for did in sorted(set(table) - set(decisions)):
        problems.append(
            f"summary-table row {did} has no row in the proposal's Decisions-required table"
        )
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--record", type=Path, default=RECORD_DEFAULT)
    parser.add_argument("--proposal", type=Path, default=PROPOSAL_DEFAULT)
    args = parser.parse_args()
    problems = check(args.record, args.proposal)
    if problems:
        for problem in problems:
            print(f"FAIL: {problem}")
        print(f"GATE-47 FAILED: {len(problems)} problem(s)")
        sys.exit(1)
    print(f"GATE-47 PASSED: {args.record} satisfies the decision-record contract")
    sys.exit(0)


if __name__ == "__main__":
    main()
