"""Phase 6 (openspec wire-databricks-dlt-movement task 6.11) — the
export-side dlt resources: the export's source scope becomes the
resources the pipeline loads (the acceptance round-trip's source leg —
design D1's "the hub performs the write").

The row reader is the canonical seam: the production default reads the
Hub file storage through the REAL ``S3StorageClient.get_file_content``;
the 6.11 fixture substitutes a real DuckDB-backed reader (the design's
"DuckDB source" contract). The parsing reuses the scaffold's
``raw_records`` resource (one parser, both directions).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from collections.abc import Iterator

logger = structlog.get_logger(__name__)


def _default_file_reader(_tenant_id: str, key: str) -> bytes:
    """The production reader — the Hub's real file storage."""
    from hub.apps.files.storage import S3StorageClient

    return S3StorageClient().get_file_content(key)


def export_rows(
    export,
    *,
    read_source=None,
) -> Iterator[tuple[str, str, bytes]]:
    """Yield ``(storage_path, format, content)`` for every source file in
    the export's scope (``file_ids`` directly, plus the files backing
    each ``dataset_ids`` entry and every dataset of each ``asset_ids``
    entry). Tenant-scoped reads only — a foreign file id is skipped,
    never read."""
    from hub.data_movement.dlt_resources import _infer_format

    reader = read_source or _default_file_reader
    scope = export.source_scope or {}
    file_ids = list(scope.get("file_ids") or [])

    dataset_ids = list(scope.get("dataset_ids") or [])

    # The asset-scoped export: the UI submits ``asset_ids`` and the
    # pre-flight validates each asset's contract — the execution must
    # actually EXPORT those assets' files. Without this expansion an
    # asset-scoped export ran with zero sources and "completed" having
    # touched nothing (JOURNEY-EXPORT-001 E2E — items_found=0 false
    # success, and before the pre-flight every such export failed on
    # the unvalidated contract instead).
    asset_ids = list(scope.get("asset_ids") or [])
    if asset_ids:
        from hub.apps.datasets.models import Dataset

        dataset_ids.extend(
            str(d.id)
            for d in Dataset.objects.filter(asset_id__in=asset_ids, tenant_id=export.tenant_id)
        )

    if dataset_ids:
        from hub.apps.datasets.models import Dataset

        for dataset in Dataset.objects.filter(
            id__in=dataset_ids, tenant_id=export.tenant_id
        ).select_related("file"):
            if dataset.file_id:
                file_ids.append(str(dataset.file_id))

    from hub.apps.files.models import File

    seen: set[str] = set()
    for file_id in file_ids:
        if file_id in seen:
            continue
        file_row = File.objects.filter(id=file_id, tenant_id=export.tenant_id).first()
        if file_row is None:
            logger.warning(
                "export_source_file_missing",
                export_id=str(export.id),
                file_id=file_id,
            )
            continue
        seen.add(file_id)
        yield (
            file_row.storage_path,
            _infer_format(file_row.name),
            reader(str(export.tenant_id), file_row.storage_path),
        )


def export_resources(export, *, read_source=None) -> list[Any]:
    """The dlt resources for the export's source scope — one
    ``raw_records`` resource per source file (the scaffold's parser)."""
    from hub.data_movement.dlt_resources import raw_records

    return [
        raw_records(content, file_format, storage_path)
        for storage_path, file_format, content in export_rows(export, read_source=read_source)
    ]
