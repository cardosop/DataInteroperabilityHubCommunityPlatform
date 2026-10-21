"""W11.4 (oss-release-remediation) — Hypothesis property suite for the
DLT spec/payload surfaces (ASVS V5, register rows 2/14).

Two pure surfaces carry client-influenced data into the movement spine:

* ``_require_mappable_keys`` — the config-injection gate: a pipeline
  config bit OUTSIDE the DLT spec mapping's mappable set is REFUSED
  with a named ``DltSpecCompileError`` (never silently dropped — the
  W3.10 config-injection contract).
* ``materialize_databricks_rows`` — renders DATABRICKS_SOURCE read rows
  to a JSONL payload whose source key embeds the cursor identity (the
  retry-idempotency contract).

Properties (EVERY input, not hand-picked samples):

* **mappable-keys gate** — any dict: unknown keys are always refused
  with the bit named; known keys never crash;
* **payload round-trip** — ANY row shapes (nested dicts/lists, and the
  non-JSON-native types ``default=str`` exists to absorb: Decimal,
  datetime, bytes, sets) serialize to exactly one JSON line per row
  that parses back — a payload can never crash or drop rows;
* **source-key identity** — the source key embeds asset_key, table_ref
  and the cursor value (or ``initial``).

Plus the W11.4 corpus replay (docs/security/fuzz/w114-property-corpus.json).

Pure property tests — no database, no mocks.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from hub.data_movement.dlt_spec_compiler import (
    _INGESTION_MAPPABLE_KEYS,
    DltSpecCompileError,
    _require_mappable_keys,
)
from hub.data_movement.ingestion_catalog import materialize_databricks_rows

pytestmark = pytest.mark.django_db  # the app conftest's MVP marker scope

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CORPUS = REPO_ROOT / "docs" / "security" / "fuzz" / "w114-property-corpus.json"

_NASTY_KEYS = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=30
)
_MAPPABLE_KEYS = st.sampled_from(sorted(_INGESTION_MAPPABLE_KEYS))

# JSON-native + the non-native types ``default=str`` must absorb.
_JSON_LEAF = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(min_value=-(2**63), max_value=2**63),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=40),
    st.decimals(allow_nan=False, allow_infinity=False).map(Decimal),
    st.datetimes(),
    st.binary(max_size=16),
    st.sets(st.integers(min_value=0, max_value=9), max_size=4),
)
_JSON_VALUE = st.recursive(
    _JSON_LEAF,
    lambda children: st.one_of(
        st.lists(children, max_size=4),
        st.dictionaries(
            st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=10),
            children,
            max_size=4,
        ),
    ),
    max_leaves=30,
)


@settings(max_examples=200, deadline=None)
@given(keys=st.lists(st.one_of(_MAPPABLE_KEYS, _NASTY_KEYS), max_size=8, unique=True))
def test_mappable_keys_gate_refuses_unknown_and_accepts_known(keys):
    """Every key outside the mappable set is refused WITH the bit named;
    a fully-mappable config passes without raising."""
    config = dict.fromkeys(keys, "x")
    unknown = [key for key in keys if key not in _INGESTION_MAPPABLE_KEYS]
    if unknown:
        with pytest.raises(DltSpecCompileError) as exc_info:
            _require_mappable_keys(config, _INGESTION_MAPPABLE_KEYS, label="source_config")
        # The refusal NAMES the offending bit — never a bare drop.
        assert str(exc_info.value.bit).startswith("source_config.")
        assert str(exc_info.value.bit).split(".", 1)[1] in unknown
    else:
        assert _require_mappable_keys(config, _INGESTION_MAPPABLE_KEYS, label="source_config") is None


@settings(max_examples=200, deadline=None)
@given(rows=st.lists(_JSON_VALUE, max_size=10))
def test_payload_round_trips_one_json_line_per_row(rows):
    """ANY row shapes → a payload whose every line parses back as JSON
    and whose line count equals the row count (no dropped rows, no
    crash, no partial payload)."""
    file_name, _source_key, payload = materialize_databricks_rows(
        rows, asset_key="asset-1", table_ref="t", cursor_value=None
    )
    assert isinstance(file_name, str)
    assert bool(file_name)
    assert isinstance(payload, bytes)
    lines = payload.decode("utf-8").splitlines()
    assert len(lines) == len(rows)
    for line in lines:
        json.loads(line)  # every line is valid JSON


@settings(max_examples=200, deadline=None)
@given(
    rows=st.lists(_JSON_VALUE, max_size=5),
    asset_key=st.text(alphabet=st.characters(blacklist_categories=("Cs",)), min_size=1, max_size=30),
    table_ref=st.one_of(st.none(), st.text(min_size=1, max_size=30)),
    cursor_value=st.one_of(st.none(), st.integers(), st.text(max_size=20)),
)
def test_source_key_embeds_identity_components(rows, asset_key, table_ref, cursor_value):
    """The source key carries the asset, the table and the cursor (or
    ``initial``) — the retry-idempotency identity is never lost."""
    _file_name, source_key, _payload = materialize_databricks_rows(
        rows, asset_key=asset_key, table_ref=table_ref, cursor_value=cursor_value
    )
    assert asset_key in source_key
    assert (table_ref or "source") in source_key
    expected_cursor = str(cursor_value) if cursor_value is not None else "initial"
    assert expected_cursor in source_key


def test_w114_corpus_replay():
    """Replay the W11.4 fuzz corpus through the real payload builder."""
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    entries = corpus.get("dlt_rows", [])
    assert entries, "the dlt_rows corpus section must carry entries"
    for entry in entries:
        file_name, source_key, payload = materialize_databricks_rows(
            entry["rows"],
            asset_key=entry.get("asset_key", "corpus-asset"),
            table_ref=entry.get("table_ref"),
            cursor_value=entry.get("cursor_value"),
        )
        assert isinstance(file_name, str)
        assert bool(file_name)
        assert len(payload.decode("utf-8").splitlines()) == len(entry["rows"])
        if entry.get("expected_asset_key"):
            assert entry["expected_asset_key"] in source_key
