"""
Phase 260.4.E — manual dataset refresh helpers.

The refresh action re-runs schema inference on a dataset's existing
backing file (no version bump unless the inferred schema changes).
Helpers in this module are intentionally pure / side-effect-free so
the action layer can compose them without each one re-implementing
input-validation guards.

* :func:`canonical_schema_hash` — JSON-stable SHA-256 over a schema
  dict, used to detect "did inference produce something different"
  without persisting two full schema payloads in the audit row.
* :func:`reinfer_dataset_schema` — fetches the file bytes via the
  shared S3 helper and runs the format-appropriate inference
  function.  Returns ``(schema_json, sample_data, row_count)`` so the
  caller writes a single ORM update.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from hub.apps.datasets.models import Dataset
from hub.apps.files.models import File


def canonical_schema_hash(schema: dict | None) -> str:
    """SHA-256 hex digest over a JSON-stable serialisation of *schema*.

    ``None`` and ``{}`` produce DIFFERENT hashes so the audit row can
    encode "schema was previously unset" distinctly from "schema was
    previously the empty dict".  Stability under dict-key reordering
    is the load-bearing property — without it ``schema_changed``
    flips on noise from Python's dict iteration order.
    """
    if schema is None:
        # A sentinel that JSON cannot produce on its own — guarantees
        # ``hash(None) != hash({})``.
        canonical = "__NULL_SCHEMA__"
    else:
        canonical = json.dumps(schema, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def reinfer_dataset_schema(
    file_obj: File,
) -> tuple[dict, Any, int | None]:
    """Re-run schema inference for *file_obj* and return the
    ``(schema_json, sample_data, row_count)`` triple.

    Mirrors the inference branch of
    :meth:`DatasetService._create_dataset_impl` so the manual-refresh
    action produces the same schema shape as the initial dataset
    creation. Format detection is content-type + filename based,
    matching the existing logic.

    Raises :class:`hub.apps.core.services.base.ValidationError` on
    inference failure so the calling action can surface a 400.
    """
    from hub.apps.core.services.base import ValidationError as ServiceValidationError
    from hub.apps.datasets.inference_limits import (
        InferenceMode,
        plan_inference_for_file,
        truncate_to_clean_boundary,
    )
    from hub.apps.datasets.schema_inference import (
        extract_sample_data,
        infer_schema_with_encoding_gate,
    )
    from hub.apps.datasets.storage_fetch import (
        fetch_file_content_for_dataset_schema_safe,
    )
    from hub.apps.files.storage import S3StorageClient

    format_map = {
        "text/csv": "CSV",
        "application/csv": "CSV",
        "application/json": "JSON",
        "text/json": "JSON",
        "application/parquet": "PARQUET",
        "application/x-parquet": "PARQUET",
    }
    file_format = format_map.get(file_obj.content_type, "CSV")
    if file_format == "CSV":
        filename_lower = (file_obj.name or "").lower()
        if filename_lower.endswith(".json") or filename_lower.endswith(".ndjson"):
            file_format = "JSON"
        elif filename_lower.endswith(".parquet"):
            file_format = "PARQUET"

    # Phase 260.5.F — same pre-flight gate the create path runs.
    # Refresh-from-new-file (260.4.D) and manual refresh (260.4.E)
    # both land here; both must honour the size cap + sampling
    # policy so a tenant cannot refresh a 10 GB CSV into the same
    # dataset that creation rejected for the same reason.
    inference_plan = plan_inference_for_file(
        file_size=file_obj.size or 0,
        file_format=file_format,
    )

    storage = S3StorageClient()
    sample_max = (
        inference_plan.bytes_to_read if inference_plan.mode == InferenceMode.SAMPLE else None
    )
    file_content = fetch_file_content_for_dataset_schema_safe(
        storage=storage,
        storage_path=file_obj.storage_path,
        max_bytes=sample_max,
    )
    if inference_plan.mode == InferenceMode.SAMPLE:
        file_content = truncate_to_clean_boundary(file_content, file_format)

    # Phase 260.5.D.R1 GAP-A — refresh paths (manual + refresh-from-
    # new-file) MUST run the same encoding gate the create path
    # runs. Originally these dispatched directly to
    # ``infer_schema_from_*`` and skipped the gate entirely, so a
    # tenant could refresh into mojibake content while creation
    # rejected the same bytes. Routing through the canonical
    # gated helper closes the bypass at the structural level.
    try:
        schema_json = infer_schema_with_encoding_gate(
            file_content=file_content,
            file_format=file_format,
        )
    except ServiceValidationError:
        # Preserve FILE_ENCODING_UNSUPPORTED / UNSUPPORTED_FILE_FORMAT
        # so the refresh action surfaces the documented 400 + code.
        raise
    except Exception as exc:
        raise ServiceValidationError(
            f"Schema inference failed: {exc}",
            details={"file_format": file_format, "error": str(exc)},
        )

    # Phase 260.5.F — surface sampled flags on refreshed schema so
    # contract drift / FE consumers see the partial-read signal.
    if isinstance(schema_json, dict):
        meta = schema_json.setdefault("inference_metadata", {})
        meta.update(inference_plan.metadata_for_schema)

    try:
        sample_data = extract_sample_data(file_content, file_format)
    except Exception:
        sample_data = []

    row_count = schema_json.get("row_count_estimated") if isinstance(schema_json, dict) else None
    return schema_json, sample_data, row_count


def apply_refreshed_schema(
    dataset: Dataset,
    *,
    schema_json: dict,
    sample_data: Any,
    row_count: int | None,
) -> bool:
    """Persist the re-inferred schema onto *dataset* and return
    ``schema_changed`` (True iff the canonical hash flipped).

    The function only writes to the row when something actually
    changed — a no-op refresh leaves ``updated_at`` unchanged so the
    UI doesn't flicker its "last updated" surface on every Refresh
    button click.
    """
    previous_hash = canonical_schema_hash(dataset.schema_json)
    new_hash = canonical_schema_hash(schema_json)
    if previous_hash == new_hash:
        return False

    dataset.schema_json = schema_json
    dataset.sample_data_json = sample_data
    if row_count is not None:
        dataset.row_count = row_count
    dataset.save(
        update_fields=[
            "schema_json",
            "sample_data_json",
            "row_count",
            "updated_at",
        ]
    )
    return True
