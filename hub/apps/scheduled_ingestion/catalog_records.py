"""
W3.8 (oss-release-remediation R2-P7/D6) — the shared catalog-record
creation core.

ONE implementation of the File+Dataset creation used by BOTH the legacy
per-file worker path (``worker_services.process_file_for_run``) and the
dlt spine (``hub.data_movement.ingestion_execution``) — the D6
parity-first fix.  The worker's creation block (format guard, schema
inference, version resolution + schema-compatibility check, File row +
hub-storage upload + ClamAV gate, asset resolution + auto-create,
Dataset row + version history, empty-data audit, search index, and the
source_config-gated compliance/semantic enrichments) lives here so the
two entrypoints can never diverge again (the sibling-copy failure
class).

Idempotency: a re-delivery of the same source key (the crash window
between a committed creation and the caller's state marking) finds the
existing rows via the provenance markers in ``File.metadata_json`` and
returns them with ``created=False`` — the caller counts the rows as
recovered instead of re-creating (which would trip the per-tenant
unique-active-name constraint).
"""

from __future__ import annotations

import contextlib
import hashlib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from django.core.files.base import ContentFile
from django.db import IntegrityError, transaction
from django.utils import timezone

from hub.apps.core.services.base import NotFoundError
from hub.apps.core.services.base import ValidationError as ServiceValidationError

if TYPE_CHECKING:
    from .models import ScheduledIngestion

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = ["CSV", "JSON", "PARQUET", "XLSX", "XLS"]
CONTENT_TYPE_MAP = {
    "CSV": "text/csv",
    "JSON": "application/json",
    "PARQUET": "application/octet-stream",
    "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "XLS": "application/vnd.ms-excel",
}

# The ``File.metadata_json`` keys that link a catalog row to its
# ingestion + source key (the idempotency discriminator).
_METADATA_INGESTION_KEY = "scheduled_ingestion_id"
_METADATA_SOURCE_KEY = "source_key"


@dataclass
class CatalogRecordResult:
    """The outcome of one catalog-record creation.

    ``created`` is False when an idempotent re-delivery found the rows
    created by an earlier (crashed) attempt — the rows exist either way.
    """

    file: Any  # hub.apps.files.models.File
    dataset: Any  # hub.apps.datasets.models.Dataset
    asset: Any | None  # hub.apps.assets.models.Asset
    created: bool


def _infer_format_from_path(file_path: str) -> str | None:
    # W1.14 — unknown/absent extensions return None so the caller
    # REJECTS the file (the pre-fix CSV default treated any payload
    # — e.g. a ``.exe`` — as a CSV and processed it).
    ext = (Path(file_path).suffix or "").lower().lstrip(".")
    mapping = {"csv": "CSV", "json": "JSON", "parquet": "PARQUET", "xlsx": "XLSX", "xls": "XLS"}
    return mapping.get(ext)


def _enqueue_file_scan(file_id: str) -> None:
    """Enqueue the ClamAV scan job for an internal-path file."""
    from hub.apps.files.tasks import enqueue_file_malware_scan

    enqueue_file_malware_scan(file_id)


def check_ingestion_plan_limits(tenant_id: str, delta_bytes: int) -> None:
    """R2-B2 (W2.7) — plan limits on the background ingestion paths.

    The single implementation of the per-file quota gate: the storage
    reservation (max_storage_gb) and the dataset count (max_datasets).
    Both checks run BEFORE any File row exists so a blocked file leaves
    zero side effects. Raises the ``PlanLimitService`` error
    (``code="plan_limit_exceeded"``) unchanged.
    """
    from hub.apps.tenants.services import PlanLimitService

    plan_limit_service = PlanLimitService(tenant_id=tenant_id)
    plan_limit_service.check_limit(
        tenant_id=tenant_id,
        limit_key="max_storage_gb",
        delta=delta_bytes,
    )
    plan_limit_service.check_limit(
        tenant_id=tenant_id,
        limit_key="max_datasets",
        delta=1,
    )


def _provenance_markers(scheduled_ingestion_id: str, source_key: str) -> dict[str, str]:
    return {
        _METADATA_INGESTION_KEY: scheduled_ingestion_id,
        _METADATA_SOURCE_KEY: source_key,
    }


def find_existing_catalog_records(
    scheduled_ingestion: ScheduledIngestion, source_key: str
) -> tuple[Any, Any] | None:
    """The idempotency lookup: the File+Dataset pair created by an
    earlier attempt of THIS ingestion for THIS source key, or None.

    The pair is created atomically, so a present File row without a
    Dataset is not a recoverable state — it is treated as absent and the
    re-creation raises the classified name-collision error.
    """
    from hub.apps.files.models import File, FileStatus

    existing_file = (
        File.objects.filter(
            tenant=scheduled_ingestion.tenant,
            status=FileStatus.ACTIVE,
            **{
                f"metadata_json__{_METADATA_INGESTION_KEY}": str(scheduled_ingestion.id),
                f"metadata_json__{_METADATA_SOURCE_KEY}": source_key,
            },
        )
        .order_by("-created_at")
        .first()
    )
    if existing_file is None:
        return None
    existing_dataset = existing_file.datasets.order_by("-created_at").first()
    if existing_dataset is None:
        return None
    return existing_file, existing_dataset


def create_file_and_dataset_records(
    scheduled_ingestion: ScheduledIngestion,
    file_path: str,
    file_content: bytes,
    *,
    source_key: str | None = None,
    asset_id: str | None = None,
    dq_result: dict[str, Any] | None = None,
) -> CatalogRecordResult:
    """Create the File + Dataset catalog records for one ingested file.

    The extracted worker core (worker_services.process_file_for_run's
    creation block, verbatim semantics). Raises
    ``ServiceValidationError`` with the classified codes:
    ``EMPTY_FILE``, ``UNSUPPORTED_FORMAT``, ``SCHEMA_INCOMPATIBLE``,
    ``CATALOG_FILE_NAME_COLLISION``, ``plan_limit_exceeded`` (via the
    caller's ``check_ingestion_plan_limits``), and the AssetService
    codes (``ASSET_KEY_RETIRED`` / ``ASSET_KEY_EXISTS``).
    """
    tenant = scheduled_ingestion.tenant
    source_key = source_key or file_path
    created_by = scheduled_ingestion.created_by

    existing = find_existing_catalog_records(scheduled_ingestion, source_key)
    if existing is not None:
        existing_file, existing_dataset = existing
        return CatalogRecordResult(
            file=existing_file,
            dataset=existing_dataset,
            asset=existing_dataset.asset if existing_dataset else None,
            created=False,
        )

    file_format = _infer_format_from_path(file_path)
    if not file_content:
        raise ServiceValidationError(
            "File is empty", code="EMPTY_FILE", details={"file_path": file_path}
        )
    if file_format not in SUPPORTED_FORMATS:
        raise ServiceValidationError(
            f"Unsupported file format: {file_format}",
            code="UNSUPPORTED_FORMAT",
            details={"file_path": file_path, "file_format": file_format},
        )

    # ── Schema inference + compatibility check (outside the atomic
    #    block so the audit row survives a rollback) ───────────────────
    from hub.apps.datasets.schema_inference import (
        extract_sample_data,
        infer_schema_from_csv,
        infer_schema_from_json,
        infer_schema_from_parquet,
    )

    schema_json = {}
    try:
        if file_format == "CSV":
            schema_json = infer_schema_from_csv(file_content)
        elif file_format == "JSON":
            schema_json = infer_schema_from_json(file_content)
        elif file_format == "PARQUET":
            schema_json = infer_schema_from_parquet(file_content)
        elif file_format in ("XLSX", "XLS"):
            try:
                from hub.apps.datasets.schema_inference import infer_schema_from_excel

                schema_json = infer_schema_from_excel(file_content)
            except (ImportError, ValueError, AttributeError) as e:
                logger.warning(
                    "Excel schema inference not available",
                    extra={"error_type": type(e).__name__},
                )
    except (ValueError, AttributeError, TypeError) as e:
        logger.warning(
            "Schema inference failed",
            extra={"file_format": file_format, "error_type": type(e).__name__},
        )
    except Exception as e:  # noqa: BLE001 - resilience: an inference quirk must never block a run
        logger.warning(
            "Unexpected error during schema inference",
            extra={"file_format": file_format, "error_type": type(e).__name__},
            exc_info=True,
        )
    try:
        sample_data_json = extract_sample_data(file_content, file_format)
    except (ValueError, AttributeError, TypeError) as e:
        logger.debug(
            "Sample data extraction failed",
            extra={"file_format": file_format, "error_type": type(e).__name__},
        )
        sample_data_json = []
    except Exception as e:  # noqa: BLE001 - resilience: an extraction quirk must never block a run
        logger.warning(
            "Unexpected error during sample data extraction",
            extra={"file_format": file_format, "error_type": type(e).__name__},
        )
        sample_data_json = []

    # Resolve the asset + version outside the transaction so the
    # schema-compatibility check can emit an audit that survives
    # rollback.
    from hub.apps.assets.models import Asset
    from hub.apps.datasets.models import Dataset

    version = 1
    parent_version = None
    asset = scheduled_ingestion.asset
    if asset_id:
        with contextlib.suppress(Asset.DoesNotExist):
            asset = Asset.objects.get(id=asset_id, tenant=tenant)
    if asset:
        latest = Dataset.objects.filter(tenant=tenant, asset=asset).order_by("-version").first()
        if latest:
            version = latest.version + 1
            parent_version = latest

    # Schema-compatibility check: if a prior version exists, verify that
    # the new schema does not remove fields that were present before.
    if parent_version is not None and parent_version.schema_json:
        new_fields = {(f.get("name") or f.get("field")) for f in (schema_json.get("fields") or [])}
        old_fields = {
            (f.get("name") or f.get("field"))
            for f in (parent_version.schema_json.get("fields") or [])
        }
        missing_fields = old_fields - new_fields
        if missing_fields:
            from hub.apps.audit.utils import create_audit_event

            # Best-effort (the Phase 273 contract): an audit-store outage
            # must never mask the classified rejection below.
            try:
                create_audit_event(
                    resource_type="scheduled_ingestion",
                    action="SCHEDULED_INGESTION_SCHEMA_INCOMPATIBLE_REJECTED",
                    actor_user=created_by,
                    tenant=tenant,
                    resource_id=str(scheduled_ingestion.id),
                    result="FAILURE",
                    details={
                        "missing_fields": sorted(missing_fields),
                        "prior_version": parent_version.version,
                        "prior_dataset_id": str(parent_version.id),
                        "audience": "TENANT_ADMIN",
                    },
                )
            except Exception as exc:
                logger.warning("catalog_schema_incompatible_audit_failed: %s", exc)
                logger.exception("catalog_schema_incompatible_audit_failed")
            raise ServiceValidationError(
                "Schema incompatible: the following fields were removed "
                f"from the prior version: {', '.join(sorted(missing_fields))}",
                code="SCHEMA_INCOMPATIBLE",
                details={"missing_fields": sorted(missing_fields)},
            )

    # ── Create File + Dataset ─────────────────────────────────────────
    with transaction.atomic():
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.files.models import File, FileStatus
        from hub.apps.files.storage import S3StorageClient

        content_type = CONTENT_TYPE_MAP.get(file_format, "application/octet-stream")
        # W10.3 (round-3 re-audit): the worker/dlt catalog path must run
        # the SAME magic-byte gate as the browser upload path — a PE
        # payload named .csv through the worker credential was
        # catalogued ACTIVE with no FILE_FORMAT_MISMATCH (the gate only
        # lived on the presigned-completion path). The content is in
        # memory here, so the gate can never be skipped by a storage
        # read failure (unlike the browser path's object-head read).
        from django.conf import settings

        if getattr(settings, "MAGIC_BYTE_VALIDATION_ENABLED", True):
            from hub.apps.files.magic_bytes import (
                MAGIC_BYTE_HEAD_BYTES,
                validate_magic_bytes_for_content_type,
            )

            validate_magic_bytes_for_content_type(
                content_type=content_type,
                head=file_content[:MAGIC_BYTE_HEAD_BYTES],
            )
        file_hash = hashlib.sha256(file_content).hexdigest()
        try:
            file_obj = File.objects.create(
                tenant=tenant,
                name=Path(file_path).name,
                content_type=content_type,
                size=len(file_content),
                status=FileStatus.ACTIVE,
                created_by=created_by,
                content_sha256=file_hash,
                metadata_json=_provenance_markers(str(scheduled_ingestion.id), source_key),
            )
        except IntegrityError as exc:
            # The (tenant, name) unique-when-ACTIVE constraint: a
            # DIFFERENT source key whose basename collides with an
            # existing active file. Classified loudly instead of leaking
            # a raw IntegrityError.
            raise ServiceValidationError(
                f"An active file named {Path(file_path).name!r} already exists "
                "for this tenant — rename the source file or the existing "
                "catalog entry",
                code="CATALOG_FILE_NAME_COLLISION",
                details={"file_path": file_path},
            ) from exc

        storage = S3StorageClient()
        storage_path = storage.save_file(
            tenant_id=str(tenant.id),
            file_id=str(file_obj.id),
            file_content=ContentFile(file_content, name=Path(file_path).name),
        )
        file_obj.storage_path = storage_path
        file_obj.save(update_fields=["storage_path"])

        # W1.14 — the internal path created File rows DIRECTLY (bypassing
        # FileService), so no ClamAV scan was ever enqueued and internal
        # files sat PENDING_SCAN forever.  Mirror the canonical
        # files/services.py gate: CLAMAV_ENABLED → on_commit enqueue;
        # disabled → SCAN_UNAVAILABLE + skipped audit.
        from django.conf import settings

        if not getattr(settings, "CLAMAV_ENABLED", True):
            from hub.apps.files.models import FileScanStatus

            file_obj.scan_status = FileScanStatus.SCAN_UNAVAILABLE
            file_obj.scanned_at = timezone.now()
            file_obj.save(update_fields=["scan_status", "scanned_at", "updated_at"])
            from hub.apps.audit.utils import create_audit_event

            # Best-effort (the Phase 273 contract): an audit-store
            # outage must never fail the catalog creation.
            try:
                create_audit_event(
                    resource_type="FILE",
                    action="FILE_MALWARE_SCAN_SKIPPED",
                    tenant=tenant,
                    resource_id=str(file_obj.id),
                    result="WARNING",
                    details={"reason": "CLAMAV_DISABLED"},
                )
            except Exception as exc:
                logger.warning("catalog_clamav_skip_audit_failed: %s", exc)
                logger.exception("catalog_clamav_skip_audit_failed")
        else:
            transaction.on_commit(lambda: _enqueue_file_scan(str(file_obj.id)))

        if not asset and scheduled_ingestion.auto_create_asset:
            asset_key = f"scheduled-ingestion-{scheduled_ingestion.id}"
            # Phase 250.2.C.2 (closes Gap 4 / B2-9) — replace the
            # raw ``Asset.objects.get_or_create`` (which bypassed
            # business rules + plan limit + audit emission +
            # webhook publication) with the canonical
            # ``AssetService.create_or_get_idempotent`` so the
            # worker path runs the same pipeline as the
            # ``POST /assets/`` API path. RETIRED-key collisions
            # raise ``ConflictError(code="ASSET_KEY_RETIRED")``;
            # we mark the file as a permanent failure so the run
            # surfaces the precise reason to ops + bumps the
            # alerting counter.
            from hub.apps.assets.services import AssetService
            from hub.apps.core.services.base import (
                ConflictError as _AssetConflictError,
            )
            from hub.apps.core.services.base import (
                ValidationError as _AssetValidationError,
            )
            from hub.apps.observability.otel_metrics import (
                scheduled_ingestion_asset_key_retired_total,
            )

            asset_service = AssetService(
                tenant_id=str(tenant.id),
                user_id=str(created_by.id) if created_by else None,
            )
            try:
                asset = asset_service.create_or_get_idempotent(
                    tenant_id=str(tenant.id),
                    user_id=str(created_by.id) if created_by else None,
                    key=asset_key,
                    name=scheduled_ingestion.name,
                    description=(
                        scheduled_ingestion.description
                        or f"Asset from scheduled ingestion {scheduled_ingestion.name}"
                    ),
                    created_by=created_by,
                )
            except _AssetConflictError as exc:
                if exc.code == "ASSET_KEY_RETIRED":
                    logger.warning(
                        "scheduled_ingestion_asset_key_retired",
                        extra={
                            "scheduled_ingestion_id": str(scheduled_ingestion.id),
                            "tenant_id": str(tenant.id),
                            "asset_key": asset_key,
                            "asset_id": exc.details.get("asset_id"),
                        },
                    )
                    scheduled_ingestion_asset_key_retired_total.add(
                        1,
                        attributes={
                            "scheduled_ingestion_id": str(scheduled_ingestion.id),
                            "tenant_id": str(tenant.id),
                        },
                    )
                # Re-raise as ServiceValidationError so the caller treats
                # this the same as any other business-rules /
                # validation rejection.
                raise ServiceValidationError(
                    exc.message,
                    code=exc.code,
                    details=exc.details,
                ) from exc
            except _AssetValidationError as exc:
                # Phase 250.2.C.4 — worker error shape == HTTP API
                # error shape; the raise contract here MUST mirror
                # ``POST /assets/`` so a downstream consumer of
                # the run failure can handle both paths uniformly.
                raise ServiceValidationError(
                    exc.message,
                    code=exc.code or "VALIDATION_ERROR",
                    details=exc.details,
                ) from exc
            scheduled_ingestion.asset = asset
            scheduled_ingestion.save(update_fields=["asset"])

        snapshot_metadata = {}
        if dq_result:
            snapshot_metadata["pre_ingestion_dq"] = {
                "overall_status": dq_result.get("overall_status"),
                "quality_score": dq_result.get("quality_score"),
                "checks_count": len(dq_result.get("checks", [])),
            }

        dataset = Dataset.objects.create(
            tenant=tenant,
            asset=asset,
            file=file_obj,
            schema_json=schema_json,
            sample_data_json=sample_data_json,
            row_count=schema_json.get("row_count_estimated"),
            format=file_format,
            version=version,
            created_by=created_by,
            snapshot_metadata=snapshot_metadata or {},
        )
        from hub.apps.datasets.versioning import VersionHistoryManager

        VersionHistoryManager.create_version(
            dataset=dataset, parent_version=parent_version, is_current=True
        )

        # 260.7.F — empty-data warning: emit audit when row_count is 0
        # (e.g., header-only CSV). The dataset IS created; the warning
        # is informational so ops can spot empty-snapshot feeds.
        if (schema_json.get("row_count_estimated") or 0) == 0:
            from hub.apps.audit.utils import create_audit_event as _ce

            # Best-effort (the Phase 273 contract): an audit-store
            # outage must never fail the catalog creation.
            try:
                _ce(
                    resource_type="scheduled_ingestion",
                    action="SCHEDULED_INGESTION_EMPTY_DATA_WARN",
                    actor_user=created_by,
                    tenant=tenant,
                    resource_id=str(dataset.id),
                    result="WARNING",
                    details={
                        "dataset_id": str(dataset.id),
                        "row_count": 0,
                        "audience": "TENANT_ADMIN",
                    },
                )
            except Exception as exc:
                logger.warning("catalog_empty_data_audit_failed: %s", exc)
                logger.exception("catalog_empty_data_audit_failed")

        if asset and scheduled_ingestion.auto_activate:
            asset.status = AssetStatus.ACTIVE
            asset.save(update_fields=["status"])

    # ── Post-create enrichments (best-effort, never block the run) ────
    # 1. Index (Search)
    try:
        from hub.apps.search.indexing import SearchIndexer

        SearchIndexer.index_dataset(dataset)
    except (ConnectionError, TimeoutError, ValueError, AttributeError) as e:
        logger.warning(
            "Search index failed",
            extra={"dataset_id": str(dataset.id), "error_type": type(e).__name__},
        )
    except Exception as e:  # noqa: BLE001 - best-effort enrichment, never blocks the run
        logger.warning(
            "Unexpected error during search indexing",
            extra={"dataset_id": str(dataset.id), "error_type": type(e).__name__},
            exc_info=True,
        )

    # 2. Compliance (if configured in ingestion source_config; requires created_by for job ownership)
    source_config = scheduled_ingestion.get_source_config()
    if source_config.get("run_compliance") and dataset and created_by:
        try:
            from hub.apps.compliance.services import ComplianceService

            compliance_svc = ComplianceService(
                tenant_id=str(tenant.id),
                user_id=str(created_by.id),
            )
            compliance_svc.create_compliance_run(
                tenant_id=str(tenant.id),
                user_id=str(created_by.id),
                dataset_id=str(dataset.id),
                scan_mode="internal",
                tenant=tenant,
                user=created_by,
                dataset=dataset,
            )
        except (ServiceValidationError, NotFoundError, PermissionError) as e:
            logger.warning(
                "Compliance run creation failed",
                extra={
                    "dataset_id": str(dataset.id),
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
        except Exception as e:  # noqa: BLE001 - best-effort enrichment, never blocks the run
            logger.warning(
                "Unexpected error during compliance run creation",
                extra={"dataset_id": str(dataset.id), "error_type": type(e).__name__},
                exc_info=True,
            )

    # 3. Semantic mapping (if configured in ingestion source_config, applicable to datasets)
    if source_config.get("run_semantic_mapping") and dataset:
        # P2-3 root fix: the import guard is SEPARATE from the call error
        # handling — the old broad except (ValueError/AttributeError/
        # TypeError) did not cover the core-mode absence forms
        # (ModuleNotFoundError public tree / RuntimeError private core),
        # so a core-mode enrichment request crashed instead of degrading.
        try:
            from hub.apps.semantic.utils import map_dataset_to_semantic
        except (RuntimeError, ModuleNotFoundError):
            map_dataset_to_semantic = None
        if map_dataset_to_semantic is not None:
            try:
                map_dataset_to_semantic(dataset, tenant=tenant, use_cache=False)
            except (ValueError, AttributeError, TypeError) as e:
                logger.warning(
                    "Semantic mapping failed",
                    extra={
                        "dataset_id": str(dataset.id),
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )
        except Exception as e:  # noqa: BLE001 - best-effort enrichment, never blocks the run
            logger.warning(
                "Unexpected error during semantic mapping",
                extra={"dataset_id": str(dataset.id), "error_type": type(e).__name__},
                exc_info=True,
            )

    return CatalogRecordResult(file=file_obj, dataset=dataset, asset=asset, created=True)
