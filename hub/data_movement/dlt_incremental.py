"""
285.6.3.2 — dlt incremental loading replacing incremental_state.py (319L).

dlt tracks cursor state automatically via pipeline.state.
No custom state management needed — dlt handles watermarks,
processed files, and deduplication natively.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

import dlt
import structlog

logger = structlog.get_logger(__name__)


def incremental_by_last_modified(
    source_files: List[Dict[str, Any]],
    pipeline_name: str,
    cursor_field: str = "last_modified",
) -> List[Dict[str, Any]]:
    """
    285.6.3.2 — Filter files to only new/modified since last run.

    Uses dlt pipeline state to track the last processed timestamp.
    Replaces IncrementalStateManager.get_processed_files() logic.

    dlt equivalent: @dlt.resource(primary_key="file_key") with
    write_disposition="merge" handles dedup automatically.
    """
    pipeline = dlt.pipeline(pipeline_name=pipeline_name)
    state = pipeline.state

    last_cursor = state.get("last_processed_cursor", "")
    new_files: List[Dict[str, Any]] = []

    for f in source_files:
        file_cursor = f.get(cursor_field, "")
        if not last_cursor or file_cursor > last_cursor:
            new_files.append(f)

    if new_files:
        # Update the cursor to the latest file's timestamp
        latest = max(f.get(cursor_field, "") for f in new_files)
        state["last_processed_cursor"] = latest
        pipeline.state = state

    logger.info(
        "dlt_incremental_filter",
        pipeline=pipeline_name,
        total=len(source_files),
        new=len(new_files),
        cursor=state.get("last_processed_cursor", ""),
    )
    return new_files


def get_processed_keys(pipeline_name: str) -> List[str]:
    """
    285.6.3.2 — Return list of already-processed file keys from dlt state.

    Replaces IncrementalStateManager.get_processed_files().
    """
    pipeline = dlt.pipeline(pipeline_name=pipeline_name)
    state = pipeline.state
    return state.get("processed_keys", [])


def mark_processed(pipeline_name: str, file_keys: List[str]) -> None:
    """
    285.6.3.2 — Mark file keys as processed in dlt state.

    Replaces IncrementalStateManager.mark_processed().
    """
    pipeline = dlt.pipeline(pipeline_name=pipeline_name)
    state = pipeline.state
    existing = set(state.get("processed_keys", []))
    existing.update(file_keys)
    state["processed_keys"] = list(existing)
    pipeline.state = state


@dlt.source
def incremental_file_source(
    files: List[Dict[str, Any]],
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
