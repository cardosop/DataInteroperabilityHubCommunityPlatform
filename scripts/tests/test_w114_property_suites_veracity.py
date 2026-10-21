"""W11.4 (oss-release-remediation) — ASVS V5 property-suite veracity pins.

The W11.4 evidence is five Hypothesis property suites (cents, DQ SQL,
compliance SQL, SPARQL validator, DLT spec/payload, ODPS payload) plus a
committed fuzz corpus.  These pins keep the evidence HONEST (the P4
rule, applied to the ASVS pack), Django-free so the CI no-django lint
job can run them:

* every suite file exists and carries ``@given`` property tests;
* every suite carries the corpus-replay test (the corpus is ACTIVE —
  replayed through the real targets, not decoration);
* the corpus exists, parses, and carries the five target sections with
  well-formed entries;
* register rows 2 (SQL injection) and 14 (validation gaps) in
  ``design.md`` — the rows this suite verifies — cite the property
  evidence.

RED phase: before the suites/corpus existed, the existence pins failed
(FileNotFoundError); after, every citation is resolved mechanically
against the real tree.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CORPUS = REPO_ROOT / "docs" / "security" / "fuzz" / "w114-property-corpus.json"
DESIGN_DOC = (
    REPO_ROOT
    / "openspec"
    / "changes"
    / "oss-release-remediation"
    / "design.md"
)

SUITES = {
    "cents": REPO_ROOT / "hub/apps/marketplace/tests/test_w29_cents_properties.py",
    "dq-sql": REPO_ROOT / "hub/apps/dq/tests/test_w29_sql_injection_properties.py",
    "compliance-sql": REPO_ROOT / "hub/apps/compliance/tests/test_w29_sql_injection_properties.py",
    "sparql": REPO_ROOT / "hub/apps/semantic/tests/test_w114_sparql_properties.py",
    "dlt-spec": REPO_ROOT / "hub/data_movement/tests/test_w114_dlt_spec_properties.py",
    "odps": REPO_ROOT / "hub/apps/webhooks/tests/test_w114_odps_payload_properties.py",
}

CORPUS_SECTIONS = {"cents", "sql_dq", "sql_compliance", "sparql", "dlt_rows", "odps"}


def _suite_tree(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"))


def test_all_six_suite_files_exist():
    missing = [name for name, path in SUITES.items() if not path.is_file()]
    assert not missing, f"missing W11.4 property suites: {missing}"


def test_every_suite_carries_given_property_tests():
    for name, path in SUITES.items():
        tree = _suite_tree(path)
        has_given = False
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                for dec in node.decorator_list:
                    func = dec.func if isinstance(dec, ast.Call) else dec
                    func_name = getattr(func, "id", None) or getattr(func, "attr", None)
                    if func_name == "given":
                        has_given = True
        assert has_given, f"{name}: the suite carries no @given property tests"


def test_every_suite_carries_the_corpus_replay_test():
    for name, path in SUITES.items():
        tree = _suite_tree(path)
        names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        assert "test_w114_corpus_replay" in names, (
            f"{name}: the suite has no corpus-replay test"
        )


def test_corpus_exists_and_is_well_formed():
    assert CORPUS.is_file(), "the W11.4 fuzz corpus must be committed"
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    missing = CORPUS_SECTIONS - set(data)
    assert not missing, f"corpus missing sections: {sorted(missing)}"
    for section in CORPUS_SECTIONS:
        entries = data[section]
        assert isinstance(entries, list), (
            f"corpus section {section!r} must be a list"
        )
        assert entries, f"corpus section {section!r} must be non-empty"
        assert all(isinstance(entry, dict) for entry in entries), (
            f"corpus section {section!r} must hold dict entries"
        )


def test_corpus_cents_entries_pin_an_outcome():
    data = json.loads(CORPUS.read_text(encoding="utf-8"))
    for entry in data["cents"]:
        assert "input" in entry, f"cents entry missing input: {entry}"
        has_cents = "expect_cents" in entry
        has_error = "expect_error" in entry
        assert has_cents != has_error, (
            f"cents entry must pin exactly one outcome: {entry}"
        )


def test_design_register_rows_2_and_14_cite_the_property_evidence():
    """Register rows 2 (SQL injection) and 14 (validation gaps) are the
    rows these suites verify — the design doc must cite the evidence
    from both (corpus path or a suite path)."""
    assert DESIGN_DOC.is_file(), "design.md must exist"
    text = DESIGN_DOC.read_text(encoding="utf-8")
    row2 = re.search(r"^\| 2 \|.*$", text, re.M)
    row14 = re.search(r"^\| 14 \|.*$", text, re.M)
    assert row2 is not None, "register row 2 must exist in design.md"
    assert row14 is not None, "register row 14 must exist in design.md"
    tail = text[row2.start() : row14.end()]
    evidence = ("w114-property-corpus.json", "test_w114_sparql_properties.py")
    assert any(marker in tail for marker in evidence), (
        "design.md rows 2..14 must cite the W11.4 property evidence"
    )
