"""W2.9 (optional improvement) — Hypothesis injection invariants (compliance SQL).

Companion to ``dq/tests/test_w29_sql_injection_properties.py`` for the
compliance scanner compiler (the second SQL-compiler surface from the
W1.11 remediation). Pins the same invariants for EVERY client-sendable
string:

* **grammar gate** — a column/FQN that fails the strict identifier
  grammar can never appear verbatim in compiled SQL.
* **robustness** — arbitrary scan payloads and non-string warehouse
  types end in a result, a skip, or a typed SQLSafetyError — never an
  incidental crash.

Pure property tests — no database.
"""

import contextlib

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from hub.apps.compliance.warehouse_sql_compiler import (
    ComplianceWarehouseSQLCompiler,
)
from hub.apps.dq.sql_safety import SQLSafetyError, validate_sql_identifier, validate_table_fqn

pytestmark = pytest.mark.django_db  # the app conftest's MVP marker scope

_WAREHOUSES = st.sampled_from(["snowflake", "bigquery", "databricks"])
_SCAN_TYPES = st.sampled_from(
    [
        "pii_email",
        "pii_phone",
        "pii_ssn",
        "pii_credit_card",
        "pii_ip_address",
        "retention_breach",
        "classification_mismatch",
    ]
)
_NASTY_TEXT = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=60)


def _compiled_sqls(compiler, definitions, warehouse_type, table_fqn):
    """Compile and return every emitted SQL string (raises propagate)."""
    results = compiler.compile(definitions, warehouse_type, table_fqn)
    return [r.sql for r in results]


@settings(max_examples=200, deadline=None)
@given(
    column=_NASTY_TEXT,
    warehouse_type=_WAREHOUSES,
    scan_type=_SCAN_TYPES,
)
def test_grammar_invalid_columns_never_reach_sql(column, warehouse_type, scan_type):
    try:
        validate_sql_identifier(column, "column")
    except SQLSafetyError:
        valid = False
    else:
        valid = True
    assume(not valid)
    try:
        sqls = _compiled_sqls(
            ComplianceWarehouseSQLCompiler,
            [{"type": scan_type, "column": column}],
            warehouse_type,
            "db.schema.table",
        )
    except SQLSafetyError:
        return
    for sql in sqls:
        assert column not in sql, f"invalid column leaked verbatim: {column!r}"


@settings(max_examples=200, deadline=None)
@given(fqn=_NASTY_TEXT, warehouse_type=_WAREHOUSES)
def test_grammar_invalid_table_fqns_never_reach_sql(fqn, warehouse_type):
    try:
        validate_table_fqn(fqn)
    except SQLSafetyError:
        valid = False
    else:
        valid = True
    assume(not valid)
    try:
        sqls = _compiled_sqls(
            ComplianceWarehouseSQLCompiler,
            [{"type": "pii_email", "column": "col"}],
            warehouse_type,
            fqn,
        )
    except SQLSafetyError:
        return
    for sql in sqls:
        assert fqn not in sql, f"invalid FQN leaked verbatim: {fqn!r}"


@settings(max_examples=100, deadline=None)
@given(
    scans=st.lists(
        st.dictionaries(
            keys=st.text(max_size=20),
            values=st.one_of(
                _NASTY_TEXT,
                st.integers(),
                st.floats(allow_nan=False),
                st.booleans(),
                st.none(),
                st.dictionaries(keys=st.text(max_size=10), values=_NASTY_TEXT, max_size=3),
            ),
            max_size=6,
        ),
        max_size=5,
    ),
    warehouse_type=st.one_of(st.text(max_size=10), st.integers(), st.none()),
    fqn=_NASTY_TEXT,
    regulations=st.one_of(st.none(), st.lists(st.text(max_size=10), max_size=3)),
)
def test_compiler_never_crashes_on_arbitrary_input(scans, warehouse_type, fqn, regulations):
    # Any client payload must end in a result, a skip, or a typed
    # SQLSafetyError — never an incidental TypeError/AttributeError/
    # KeyError.
    with contextlib.suppress(SQLSafetyError, ValueError):
        ComplianceWarehouseSQLCompiler.compile(
            scans, warehouse_type, fqn, applicable_regulations=regulations
        )


def test_w114_corpus_replay():
    """W11.4 — replay the fuzz corpus through the real compliance
    compiler (the regression inputs found by the property suites)."""
    import json
    from pathlib import Path

    corpus = json.loads(
        (Path(__file__).resolve().parent.parent.parent.parent.parent / "docs" / "security" / "fuzz" / "w114-property-corpus.json").read_text(encoding="utf-8")
    )
    entries = corpus.get("sql_compliance", [])
    assert entries, "the sql_compliance corpus section must carry entries"
    for entry in entries:
        if entry.get("expect") == "SQLSafetyError":
            with pytest.raises(SQLSafetyError):
                ComplianceWarehouseSQLCompiler.compile(
                    entry["check_definitions"], entry["warehouse_type"], entry["table_fqn"]
                )
        else:
            results = ComplianceWarehouseSQLCompiler.compile(
                entry["check_definitions"], entry["warehouse_type"], entry["table_fqn"]
            )
            assert isinstance(results, list), entry
