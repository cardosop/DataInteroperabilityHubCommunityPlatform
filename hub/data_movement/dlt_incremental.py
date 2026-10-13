"""
285.6.3.2 — dlt incremental loading replacing incremental_state.py (319L).

dlt tracks cursor state automatically via pipeline.state.
No custom state management needed — dlt handles watermarks,
processed files, and deduplication natively.

6.7 (openspec wire-databricks-dlt-movement) — the DATABRICKS_SOURCE
section: the SQL-cursor incremental state, keyed per pipeline + asset
inside the REAL dlt pipeline state (design D1 — a re-run resumes from
the last cursor, never a full re-read). The cursor bounds the READ SQL
(a parameterised ``:last_cursor`` bound — the value never rides in the
SQL text); the cursor advances ONLY after a successful load; a schema
change on the source (rows without the cursor field, or uncomparable
cursor values) resets the cursor by design (dlt's documented
semantics — the next run re-reads everything).

dlt 1.30 API note: ``pipeline.state`` is read-only (no setter) — state
mutations persist through the ``managed_state()`` context manager.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import dlt
import structlog

from hub.data_movement.dlt_pipeline import _configure_dlt_pipelines_dir

# W3.10 — this module imports dlt at MODULE level (independently of the
# lazy _get_dlt chokepoint), so arm the volume-backed pipelines-dir
# config here too: any dlt.pipeline() created through this module must
# resolve the same persistent state dir.
_configure_dlt_pipelines_dir(dlt)

logger = structlog.get_logger(__name__)

# ── 285.6.3.2 — file-based cursors ──────────────────────────────────────


def incremental_by_last_modified(
    source_files: list[dict[str, Any]],
    pipeline_name: str,
    cursor_field: str = "last_modified",
) -> list[dict[str, Any]]:
    """
    285.6.3.2 — Filter files to only new/modified since last run.

    Uses dlt pipeline state to track the last processed timestamp.
    Replaces IncrementalStateManager.get_processed_files() logic.

    dlt equivalent: @dlt.resource(primary_key="file_key") with
    write_disposition="merge" handles dedup automatically.
    """
    pipeline = dlt.pipeline(pipeline_name=pipeline_name)

    with pipeline.managed_state() as state:
        last_cursor = state.get("last_processed_cursor", "")
        new_files: list[dict[str, Any]] = []

        for f in source_files:
            file_cursor = f.get(cursor_field, "")
            if not last_cursor or file_cursor > last_cursor:
                new_files.append(f)

        if new_files:
            # Update the cursor to the latest file's timestamp
            latest = max(f.get(cursor_field, "") for f in new_files)
            state["last_processed_cursor"] = latest

    logger.info(
        "dlt_incremental_filter",
        pipeline=pipeline_name,
        total=len(source_files),
        new=len(new_files),
        cursor=last_cursor,
    )
    return new_files


def get_processed_keys(pipeline_name: str) -> list[str]:
    """
    285.6.3.2 — Return list of already-processed file keys from dlt state.

    Replaces IncrementalStateManager.get_processed_files().
    """
    pipeline = dlt.pipeline(pipeline_name=pipeline_name)
    state = pipeline.state
    return state.get("processed_keys", [])


def mark_processed(pipeline_name: str, file_keys: list[str]) -> None:
    """
    285.6.3.2 — Mark file keys as processed in dlt state.

    Replaces IncrementalStateManager.mark_processed().
    """
    pipeline = dlt.pipeline(pipeline_name=pipeline_name)
    with pipeline.managed_state() as state:
        existing = set(state.get("processed_keys", []))
        existing.update(file_keys)
        state["processed_keys"] = list(existing)


def clear_processed_keys(pipeline_name: str, file_keys: list[str]) -> None:
    """W3.9 (F17) — UN-mark file keys in the dlt state.

    The DLQ retry path uses this to re-queue a file for the LIVE
    movement path: removing the key makes the next run's incremental
    filter re-discover it (the counterpart of ``mark_processed`` —
    the legacy ``IncrementalStateManager.clear_failed_file`` equivalent
    for the dlt state).
    """
    pipeline = dlt.pipeline(pipeline_name=pipeline_name)
    with pipeline.managed_state() as state:
        existing = set(state.get("processed_keys", []))
        existing.difference_update(file_keys)
        state["processed_keys"] = list(existing)


@dlt.source
def incremental_file_source(
    files: list[dict[str, Any]],
    pipeline_name: str,
):
    """
    285.6.3.2 — dlt source with incremental loading.

    dlt cursor tracking replaces IncrementalStateManager entirely.
    The @dlt.resource(write_disposition="merge") deduplication
    means previously processed files are silently skipped.
    """
    new_files = incremental_by_last_modified(files, pipeline_name)

    @dlt.resource(write_disposition="merge", primary_key="file_key")
    def files_resource():
        for f in new_files:
            yield {
                "file_key": f.get("key", f.get("path", "")),
                "file_name": f.get("name", ""),
                "file_size_bytes": f.get("size", 0),
                "last_modified": f.get("last_modified", ""),
                "etag": f.get("etag", ""),
            }

    return files_resource


# ── 6.7 — DATABRICKS_SOURCE SQL cursors ─────────────────────────────────


# The per-pipeline state key holding the per-asset cursor map.
CURSOR_STATE_KEY = "databricks_source_cursors"

# Identifiers accepted inside generated SQL: a plain SQL identifier, or a
# dot-qualified table ref (catalog.schema.table). Anything else is refused
# fail-closed — these values are never interpolated unchecked.
_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")
_TABLE_REF_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_.]*$")


class DatabricksSourceIncrementalError(Exception):
    """A DATABRICKS_SOURCE incremental configuration failure: a table ref
    or cursor field that failed the identifier guard — refused fail-closed
    before any warehouse work."""

    code = "DATABRICKS_SOURCE_INCREMENTAL_ERROR"


def _guard_identifier(value: str, *, kind: str) -> str:
    if not _IDENTIFIER_RE.match(value):
        raise DatabricksSourceIncrementalError(
            f"invalid {kind} {value!r} — identifiers only, never interpolated unchecked into SQL"
        )
    return value


def get_databricks_source_cursor(pipeline_name: str, asset_id: str) -> dict[str, Any] | None:
    """6.7 — the recorded cursor for one pipeline+asset, or None before
    the first successful run.

    The state shape: ``{"cursor_field": ..., "last_value": ...,
    "updated_at": <iso>}`` — ``last_value`` carries the connector's own
    string representation (ISO-8601 timestamps sort chronologically).
    """
    pipeline = dlt.pipeline(pipeline_name=pipeline_name)
    state = pipeline.state or {}
    return (state.get(CURSOR_STATE_KEY) or {}).get(str(asset_id))


def incremental_sql_predicate(cursor_field: str, last_value: Any) -> tuple[str, dict[str, Any]]:
    """6.7 — the parameterised bound for a cursor run.

    Returns the ``WHERE`` fragment with a named ``:last_cursor``
    parameter (the connectors' binding convention — the value is NEVER
    inlined into the SQL text). The cursor field is identifier-guarded.
    """
    _guard_identifier(cursor_field, kind="cursor field")
    return f' WHERE "{cursor_field}" > :last_cursor', {"last_cursor": last_value}


def databricks_source_read_sql(
    table_ref: str,
    cursor_field: str,
    cursor: dict[str, Any] | None,
) -> tuple[str, dict[str, Any] | None]:
    """6.7 — the DATABRICKS_SOURCE read: an unbounded full read on the
    first run, a cursor-bounded read afterwards. The table ref and the
    cursor field are identifier-guarded; the cursor value rides as a
    parameter, never in the SQL text."""
    table_ref = (table_ref or "").strip()
    if not _TABLE_REF_RE.match(table_ref):
        raise DatabricksSourceIncrementalError(
            f"invalid table ref {table_ref!r} — never interpolated unchecked into SQL"
        )
    _guard_identifier(cursor_field, kind="cursor field")

    predicate, params = "", None
    if cursor:
        predicate, params = incremental_sql_predicate(
            str(cursor.get("cursor_field") or cursor_field), cursor.get("last_value")
        )
    return f'SELECT * FROM {table_ref}{predicate} ORDER BY "{cursor_field}"', params


def advance_databricks_source_cursor(
    pipeline_name: str,
    asset_id: str,
    *,
    cursor_field: str,
    rows: list[dict[str, Any]],
) -> str | None:
    """6.7 — advance the cursor to the max cursor value seen. Caller
    contract: invoke ONLY after a successful load.

    An empty read keeps the cursor where it was. Rows lacking the cursor
    field (or carrying uncomparable values) are a source schema change:
    the cursor is RESET (dropped) so the next run re-reads everything —
    dlt's documented semantics, never a silently wrong bound.
    """
    pipeline = dlt.pipeline(pipeline_name=pipeline_name)
    asset_key = str(asset_id)

    with pipeline.managed_state() as state:
        cursors = state.setdefault(CURSOR_STATE_KEY, {})
        current = cursors.get(asset_key)

        if not rows:
            return current.get("last_value") if current else None

        values: list[Any] = []
        for row in rows:
            if not isinstance(row, dict) or row.get(cursor_field) is None:
                values = []
                break
            values.append(row[cursor_field])
        if not values:
            # Schema change on the source: reset the cursor by design.
            if cursors.pop(asset_key, None) is not None:
                logger.warning(
                    "databricks_source_cursor_reset",
                    pipeline=pipeline_name,
                    asset=asset_key,
                    reason="the read rows carry no cursor field — schema change",
                )
            state[CURSOR_STATE_KEY] = cursors
            return None

        try:
            next_value = max(values)
        except TypeError:
            if cursors.pop(asset_key, None) is not None:
                logger.warning(
                    "databricks_source_cursor_reset",
                    pipeline=pipeline_name,
                    asset=asset_key,
                    reason="uncomparable cursor values — schema change",
                )
            state[CURSOR_STATE_KEY] = cursors
            return None

        cursors[asset_key] = {
            "cursor_field": cursor_field,
            "last_value": next_value,
            # `datetime` here is the class import, which shadows the module
            # attribute — timezone.utc is the unambiguous form (UP017 n/a).
            "updated_at": datetime.now(UTC).isoformat(),
        }
        state[CURSOR_STATE_KEY] = cursors
        return next_value


def databricks_source_rows(rows: list[dict[str, Any]], *, asset_id: str) -> Any:
    """6.7 — the DATABRICKS_SOURCE dlt resource: one append table per
    asset inside the pipeline's dataset (the per-asset keying). The
    no-duplicate guarantee is the READ bound (the strict ``>`` cursor),
    not the destination — the movement's filesystem staging destination
    is append-only (dlt 1.30 falls back from merge there by design)."""
    resource_name = f"databricks_source_{str(asset_id).replace('-', '')}"

    @dlt.resource(name=resource_name, write_disposition="append")
    def _rows_resource():
        for row in rows:
            yield dict(row)

    return _rows_resource
