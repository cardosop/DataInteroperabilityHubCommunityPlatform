"""
W7.2 (oss-release-remediation) — paid annotations + traceability drift pins.

D5 / R2-M3 / G9 contract:
- the two canonical registries (USER_JOURNEYS.md, USE_CASES.md) carry a
  PAID column and every paid-tagged ID row is marked;
- the critical registry's curated counts are honest (35 UC + 29 journey);
- the core-scope gates stop absorbing the paid Databricks IDs;
- the persona-journey mapping regenerator reproduces the committed file;
- JOURNEY-EXPORT-001 has exactly ONE spec.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
JOURNEYS_DOC = REPO / "docs" / "USER_JOURNEYS.md"
UC_DOC = REPO / "docs" / "USE_CASES.md"
CRITICAL_YAML = REPO / "docs" / "CRITICAL_UC_JOURNEY_IDS.yaml"
MAPPING_YAML = REPO / "docs" / "mvpdocs" / "_meta" / "persona-journey-mapping.yaml"

_DB_PAID_IDS = {
    "JOURNEY-DB-001",
    "JOURNEY-DB-003",
    "JOURNEY-DB-007",
    "JOURNEY-DB-008",
    "UC-DB-007",
    "UC-DB-008",
}


def paid_ids() -> set[str]:
    data = yaml.safe_load(CRITICAL_YAML.read_text()) or {}
    return {str(i).strip() for i in data.get("paid_ids") or []}


def doc_table_rows(doc: Path) -> list[str]:
    """The ID-led table data rows (first cell matches the ID shape)."""
    rows = []
    for line in doc.read_text().splitlines():
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if cells and re.match(r"^(JOURNEY|UC)-", cells[0]):
                rows.append(line)
    return rows


def doc_paid_column_cells(doc: Path) -> list[str]:
    """The PAID-column cell of every ID-led data row (last cell)."""
    cells = []
    for line in doc_table_rows(doc):
        parts = [c.strip() for c in line.strip("|").split("|")]
        cells.append(parts[-1] if len(parts) >= 2 else "")
    return cells


# ---------------------------------------------------------------------------
# 1. duplicate EXPORT-001 spec
# ---------------------------------------------------------------------------


def test_export001_spec_is_unique():
    specs = list((REPO / "frontend" / "e2e").rglob("JOURNEY-EXPORT-001.spec.ts"))
    assert len(specs) == 1, f"duplicate EXPORT-001 specs: {specs}"
    # The surviving spec is the REAL one, imported by its persona aggregator.
    assert "journeys/de/" in str(specs[0])


# ---------------------------------------------------------------------------
# 2. honest counts (registries + critical header)
# ---------------------------------------------------------------------------


def test_registry_totals_match_actual_rows():
    journeys = len(doc_table_rows(JOURNEYS_DOC))
    m = re.search(r"\*\*Total journeys\*\*:\s*(\d+)", JOURNEYS_DOC.read_text())
    assert m and int(m.group(1)) == journeys, (
        f"Total journeys claims {m.group(1) if m else '?'}, actual {journeys}"
    )
    ucs = len(doc_table_rows(UC_DOC))
    m2 = re.search(r"\*\*Total use cases\*\*:\s*(\d+)", UC_DOC.read_text())
    assert m2 and int(m2.group(1)) == ucs, (
        f"Total use cases claims {m2.group(1) if m2 else '?'}, actual {ucs}"
    )


def test_critical_registry_counts_are_honest():
    data = yaml.safe_load(CRITICAL_YAML.read_text()) or {}
    ucs = data.get("critical_use_cases") or []
    journeys = data.get("critical_journeys") or []
    assert len(ucs) == 35
    assert len(journeys) == 29
    # The architecture doc + repo CLAUDE.md must agree with the registry.
    arch = (REPO / "docs" / "TRACEABILITY_ARCHITECTURE.md").read_text()
    assert "35 UC + 29 journey" in arch, "architecture doc carries the stale 37/33 claim"
    claude = (REPO / "CLAUDE.md").read_text()
    assert "35 UC + 29 journey" in claude, "CLAUDE.md carries the stale 37/33 claim"


# ---------------------------------------------------------------------------
# 3. PAID column + annotations
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("doc", [JOURNEYS_DOC, UC_DOC])
def test_paid_column_exists_and_marks_paid_rows(doc):
    text = doc.read_text()
    # Every ID-led table header carries the PAID column.
    header_lines = [l for l in text.splitlines() if l.startswith("| ID |")]
    assert header_lines, doc
    for header in header_lines:
        assert "PAID" in header, f"header missing PAID column: {header}"
    # Every paid-tagged row is marked Paid; non-paid rows are not.
    paid = paid_ids()
    for line in doc_table_rows(doc):
        parts = [c.strip() for c in line.strip("|").split("|")]
        row_id, paid_cell = parts[0], parts[-1]
        if row_id in paid:
            assert paid_cell == "PAID", f"{row_id} must be marked PAID"
        else:
            assert paid_cell != "PAID", f"{row_id} must NOT be marked PAID"


def test_db_paid_ids_are_tagged_in_the_registry():
    paid = paid_ids()
    for db_id in _DB_PAID_IDS:
        assert db_id in paid, f"{db_id} missing from paid_ids"


# ---------------------------------------------------------------------------
# 4. core-scope gates stop absorbing the paid Databricks IDs
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "gate",
    ["scripts/check_doc_journey_marker_sync.py", "scripts/check_doc_uc_marker_sync.py"],
)
def test_core_scope_gates_are_green(gate):
    result = subprocess.run(
        [sys.executable, str(REPO / gate), "--ci-mode", "--scope", "core"],
        capture_output=True,
        text=True,
        check=False,
        cwd=REPO,
    )
    assert result.returncode == 0, f"{gate} core-scope failed:\n{result.stdout}\n{result.stderr}"


# ---------------------------------------------------------------------------
# 5. persona-mapping regenerator reproduces the committed file
# ---------------------------------------------------------------------------


def test_regenerator_reproduces_committed_mapping(tmp_path):
    """The committed persona-journey mapping equals the extractor's output
    (in-process: the REAL extraction over the REAL persona aggregators,
    serialized through the extractor's own writer into a temp file)."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "extract_persona_journey_mapping",
        REPO / "scripts" / "extract_persona_journey_mapping.py",
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    mapping = module.extract_persona_journeys(
        REPO / "frontend" / "e2e" / "personas"
    )
    assert mapping, "no persona journeys extracted"
    generated_path = tmp_path / "mapping.yaml"
    module.write_mapping(mapping, generated_path)
    assert generated_path.read_text() == MAPPING_YAML.read_text(), (
        "the committed persona-journey mapping is stale — regenerate it with "
        "scripts/extract_persona_journey_mapping.py"
    )
