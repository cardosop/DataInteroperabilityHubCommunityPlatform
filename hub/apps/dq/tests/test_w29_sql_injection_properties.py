"""W2.9 (optional improvement) — Hypothesis injection invariants (DQ SQL).

The W1.11 remediation made client-influenced identifiers strictly
validated and literals ANSI-escaped. These properties pin the INVARIANT
for EVERY string a client could send, not just the 23 hand-picked
payloads:

* **grammar gate** — an identifier/FQN that fails the strict grammar
  can never appear verbatim in compiled SQL (it is rejected before
  interpolation).
* **literal escaping is a round trip** — ``escape_sql_literal`` output
  re-parses to exactly the input (ANSI doubling), so a value can never
  terminate its literal early.
* **BigQuery regex escaping backslashes every quote** — every ``'`` in
  the escaped pattern is preceded by an ODD run of backslashes (a
  backslash-escaped quote); Snowflake/Databricks use ANSI doubling.
* **robustness** — the compiler never crashes on arbitrary check
  payloads: it compiles, skips, or raises SQLSafetyError — never
  TypeError/AttributeError/KeyError (unhashable ``type`` values and
  non-string warehouse types were REAL crashes found by this suite and
  root-fixed).

Pure property tests — no database.
"""

import contextlib

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

from hub.apps.dq.sql_safety import (
    SQLSafetyError,
    escape_regex_literal,
    escape_sql_literal,
    sql_number,
    validate_sql_identifier,
    validate_table_fqn,
)
from hub.apps.dq.warehouse_sql_compiler import DQWarehouseSQLCompiler

pytestmark = pytest.mark.django_db  # the app conftest's MVP marker scope

_WAREHOUSES = st.sampled_from(["snowflake", "bigquery", "databricks"])
_NASTY_TEXT = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=60)


def _compiled_sqls(compiler, definitions, warehouse_type, table_fqn):
    """Compile and return every emitted SQL string (raises propagate)."""
    results = compiler.compile(definitions, warehouse_type, table_fqn)
    return [r.sql for r in results]


@settings(max_examples=200, deadline=None)
@given(value=_NASTY_TEXT)
def test_literal_escaping_round_trips(value):
    # ANSI doubling: unescaping the escaped form recovers the input, so
    # a value can never break out of its single-quoted literal.
    escaped = escape_sql_literal(value)
    assert escaped.count("'") % 2 == 0
    assert escaped.replace("''", "'") == value


@settings(max_examples=200, deadline=None)
@given(value=_NASTY_TEXT)
def test_ansi_regex_escaping_round_trips(value):
    for warehouse_type in ("SNOWFLAKE", "DATABRICKS"):
        escaped = escape_regex_literal(value, warehouse_type)
        assert escaped == value.replace("'", "''")
        assert escaped.replace("''", "'") == value


@settings(max_examples=200, deadline=None)
@given(value=_NASTY_TEXT)
def test_bigquery_regex_escaping_backslashes_every_quote(value):
    escaped = escape_regex_literal(value, "BIGQUERY")
    # Scan for single quotes: each must be preceded by an ODD run of
    # backslashes (a quote after an even run would be unescaped and could
    # terminate the raw-string literal).
    i = 0
    while i < len(escaped):
        if escaped[i] == "'":
            run = 0
            j = i - 1
            while j >= 0 and escaped[j] == "\\":
                run += 1
                j -= 1
            assert run % 2 == 1, f"unescaped quote at index {i} in {escaped!r}"
        i += 1


@settings(max_examples=200, deadline=None)
@given(column=_NASTY_TEXT, warehouse_type=_WAREHOUSES)
def test_grammar_invalid_columns_never_reach_sql(column, warehouse_type):
    try:
        validate_sql_identifier(column, "column")
    except SQLSafetyError:
        valid = False
    else:
        valid = True
    assume(not valid)
    # The compiler rejects the column — or, if it somehow emits SQL, the
    # payload must not appear verbatim in any statement.
    try:
        sqls = _compiled_sqls(
            DQWarehouseSQLCompiler,
            [{"type": "not_null", "column": column}],
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
            DQWarehouseSQLCompiler,
            [{"type": "not_null", "column": "col"}],
            warehouse_type,
            fqn,
        )
    except SQLSafetyError:
        return
    for sql in sqls:
        assert fqn not in sql, f"invalid FQN leaked verbatim: {fqn!r}"


@settings(max_examples=200, deadline=None)
@given(
    values=st.lists(_NASTY_TEXT, min_size=1, max_size=5),
    warehouse_type=_WAREHOUSES,
)
def test_accepted_values_are_quote_balanced_and_escaped(values, warehouse_type):
    # Two invariants: (1) the statement's single-quote count is EVEN — a
    # literal breakout would leave it odd; (2) the ESCAPED form of every
    # value is what gets interpolated (ANSI doubling), never the raw one.
    sqls = _compiled_sqls(
        DQWarehouseSQLCompiler,
        [{"type": "accepted_values", "column": "col", "values": values}],
        warehouse_type,
        "db.schema.table",
    )
    for sql in sqls:
        assert sql.count("'") % 2 == 0, f"unbalanced quotes in {sql!r}"
        for value in values:
            assert escape_sql_literal(value) in sql, (
                f"value not interpolated in escaped form: {value!r}"
            )


@settings(max_examples=200, deadline=None)
@given(x=st.one_of(st.booleans(), _NASTY_TEXT, st.none()))
def test_sql_number_rejects_non_numbers(x):
    with pytest.raises(SQLSafetyError):
        sql_number(x, "limit")


@settings(max_examples=200, deadline=None)
@given(x=st.one_of(st.integers(), st.floats(allow_nan=False)))
def test_sql_number_accepts_real_numbers(x):
    assert sql_number(x, "limit") == x


@settings(max_examples=100, deadline=None)
@given(
    checks=st.lists(
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
)
def test_compiler_never_crashes_on_arbitrary_input(checks, warehouse_type, fqn):
    # Any client payload must end in a result, a skip, or a typed
    # SQLSafetyError — never an incidental TypeError/AttributeError/
    # KeyError (the unhashable-``type`` and non-string-warehouse crashes
    # were found here and root-fixed).
    with contextlib.suppress(SQLSafetyError, ValueError):
        DQWarehouseSQLCompiler.compile(checks, warehouse_type, fqn)


def test_w114_corpus_replay():
    """W11.4 — replay the fuzz corpus through the real compiler (the
    regression inputs the property suites found, pinned by outcome)."""
    import json
    from pathlib import Path

    corpus = json.loads(
        (Path(__file__).resolve().parent.parent.parent.parent.parent / "docs" / "security" / "fuzz" / "w114-property-corpus.json").read_text(encoding="utf-8")
    )
    entries = corpus.get("sql_dq", [])
    assert entries, "the sql_dq corpus section must carry entries"
    for entry in entries:
        if entry.get("expect") == "SQLSafetyError":
            with pytest.raises(SQLSafetyError):
                DQWarehouseSQLCompiler.compile(
                    entry["check_definitions"], entry["warehouse_type"], entry["table_fqn"]
                )
        else:
            results = DQWarehouseSQLCompiler.compile(
                entry["check_definitions"], entry["warehouse_type"], entry["table_fqn"]
            )
            assert isinstance(results, list), entry
