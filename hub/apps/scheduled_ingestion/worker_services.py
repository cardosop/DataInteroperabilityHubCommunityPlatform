"""
Worker API Service Layer

process_file_for_run: validate file (ScheduledIngestionBusinessRules), optional DQ,
create File + Dataset, index, update incremental state; on failure mark_file_failed and DLQ sync at run completion.
Same order and semantics as hub ScheduledIngestionWorkflow per-file processing.
"""

import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from hub.apps.core.services.base import ValidationError as ServiceValidationError

from .business_rules import ScheduledIngestionBusinessRules
from .incremental_state import IncrementalStateManager
from .models import ScheduledIngestion, ScheduledIngestionRun

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = ["CSV", "JSON", "PARQUET", "XLSX", "XLS"]
CONTENT_TYPE_MAP = {
    "CSV": "text/csv",
    "JSON": "application/json",
    "PARQUET": "application/octet-stream",
    "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "XLS": "application/vnd.ms-excel",
}


def _infer_format_from_path(file_path: str) -> str:
    ext = (Path(file_path).suffix or "").lower().lstrip(".")
    mapping = {"csv": "CSV", "json": "JSON", "parquet": "PARQUET", "xlsx": "XLSX", "xls": "XLS"}
    return mapping.get(ext, "CSV")


def process_file_for_run(
    run_id: str,
    file_path: str,
    file_content: bytes,
    tenant_id: str,
    user_id: Optional[str] = None,
    asset_id: Optional[str] = None,
    contract_id: Optional[str] = None,
    dq_options: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Process one file for a run: validate (business rules), optional DQ, create File + Dataset,
    index, update incremental state. On permanent failure: mark_file_failed (DLQ sync at run completion).
    Uses real ScheduledIngestionBusinessRules, DQ, Files, Datasets, Search, IncrementalStateManager.
    """
    dq_options = dq_options or {}
    run = ScheduledIngestionRun.objects.select_related("scheduled_ingestion__tenant").get(id=run_id)
    scheduled_ingestion = run.scheduled_ingestion
    if str(scheduled_ingestion.tenant_id) != tenant_id:
        raise ServiceValidationError(
            "Run does not belong to tenant",
            code="FORBIDDEN",
            details={"run_id": run_id, "tenant_id": tenant_id},
        )
    tenant = scheduled_ingestion.tenant
    file_format = _infer_format_from_path(file_path)
    file_content_length = len(file_content)

    # 1. Basic validation (same as workflow _validate_file_task)
    if file_content_length == 0:
        _mark_permanent_failure(scheduled_ingestion, file_path, "File is empty", "EMPTY_FILE")
        raise ServiceValidationError(
            "File is empty", code="VALIDATION_ERROR", details={"file_path": file_path}
        )
    if file_format not in SUPPORTED_FORMATS:
        _mark_permanent_failure(
            scheduled_ingestion,
            file_path,
            f"Unsupported format: {file_format}",
            "UNSUPPORTED_FORMAT",
        )
        raise ServiceValidationError(
            f"Unsupported file format: {file_format}",
            code="VALIDATION_ERROR",
            details={"file_path": file_path, "file_format": file_format},
        )

    # 2. ScheduledIngestionBusinessRules (validation_type="source_structure" — no live connection test per file)
    rules = ScheduledIngestionBusinessRules(tenant_id=tenant_id, user_id=user_id)
    user = None
    if user_id:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            pass
    file_validation_result = rules.validate(
        schedule=scheduled_ingestion,
        tenant=tenant,
        user=user,
        validation_type="source_structure",
    )
    if not file_validation_result.is_valid:
        err_msg = "; ".join(file_validation_result.errors)
        _mark_permanent_failure(
            scheduled_ingestion, file_path, err_msg, "BUSINESS_RULES_VALIDATION"
        )
        raise ServiceValidationError(
            err_msg,
            code="BUSINESS_RULES_VALIDATION",
            details=file_validation_result.details or {},
        )

    # 3. Optional DQ (same as workflow _run_dq_check_task)
    dq_result = None
    dq_profile_key = dq_options.get("profile_key", "intake_basic_gx")
    dq_strict_mode = dq_options.get("strict_mode", True)
    min_quality_score = float(dq_options.get("min_quality_score", 0.8))
    contract = scheduled_ingestion.contract
    if contract_id:
        from hub.apps.contracts.models import Contract

        try:
            contract = Contract.objects.get(id=contract_id, tenant=tenant)
        except Contract.DoesNotExist:
            pass
    try:
        from hub.apps.dq.service_client import DQServiceClient

        dq_client = DQServiceClient()
        is_healthy, _ = dq_client.health_check()
        if is_healthy:
            dq_result = dq_client.run_dq(
                file_content=file_content,
                file_format=file_format.lower(),
                profile_key=dq_profile_key,
                contract=contract,
            )
            overall_status = (dq_result.get("overall_status") or "").upper()
            quality_score = float(dq_result.get("quality_score", 0))
            if quality_score < min_quality_score and dq_strict_mode:
                _mark_permanent_failure(
                    scheduled_ingestion,
                    file_path,
                    f"DQ quality score {quality_score:.2%} below threshold {min_quality_score:.2%}",
                    "DQ_QUALITY_BELOW_THRESHOLD",
                )
                raise ServiceValidationError(
                    f"DQ quality score below threshold",
                    code="DQ_VALIDATION_ERROR",
                    details={
                        "quality_score": quality_score,
                        "min_quality_score": min_quality_score,
                    },
                )
            if overall_status not in ("PASS", "SUCCESS") and dq_strict_mode:
                _mark_permanent_failure(
                    scheduled_ingestion,
                    file_path,
                    f"DQ check failed with status: {overall_status}",
                    "DQ_CHECK_FAILED",
                )
                raise ServiceValidationError(
                    f"DQ check failed: {overall_status}",
                    code="DQ_VALIDATION_ERROR",
                    details={"overall_status": overall_status},
                )
    except ServiceValidationError:
        raise
    except Exception as e:
        if dq_strict_mode:
            _mark_permanent_failure(scheduled_ingestion, file_path, str(e), "DQ_ERROR")
            raise ServiceValidationError(str(e), code="DQ_ERROR", details={})
        logger.warning("DQ check failed (non-strict), continuing: %s", e)

    # 4. Schema inference + compat check (outside transaction so audits
    #    survive even when a ServiceValidationError rolls back the
    #    File/Dataset atomic block below).
    created_by = scheduled_ingestion.created_by
    from hub.apps.assets.models import Asset, AssetStatus
    from hub.apps.datasets.models import Dataset
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
                logger.debug(
                    "Excel schema inference not available",
                    extra={"error_type": type(e).__name__},
                )
    except (ValueError, AttributeError, TypeError) as e:
        logger.warning(
            "Schema inference failed",
            extra={"file_format": file_format, "error_type": type(e).__name__},
        )
    except Exception as e:
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
    except Exception as e:
        logger.warning(
            "Unexpected error during sample data extraction",
            extra={"file_format": file_format, "error_type": type(e).__name__},
        )
        sample_data_json = []

    # Resolve parent_version outside the transaction so the schema-
    # compatibility check can emit an audit that survives rollback.
    version = 1
    parent_version = None
    asset = scheduled_ingestion.asset
    if asset_id:
        try:
            asset = Asset.objects.get(id=asset_id, tenant=tenant)
        except Asset.DoesNotExist:
            pass
    if asset:
        latest = Dataset.objects.filter(tenant=tenant, asset=asset).order_by("-version").first()
        if latest:
            version = latest.version + 1
            parent_version = latest

    # Schema-compatibility check: if a prior version exists, verify that
    # the new schema does not remove fields that were present before.
    if parent_version is not None and parent_version.schema_json:
        new_fields = set(
            (f.get("name") or f.get("field"))
            for f in (schema_json.get("fields") or [])
        )
        old_fields = set(
            (f.get("name") or f.get("field"))
            for f in (parent_version.schema_json.get("fields") or [])
        )
        missing_fields = old_fields - new_fields
        if missing_fields:
            from hub.apps.audit.utils import create_audit_event

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
            raise ServiceValidationError(
                "Schema incompatible: the following fields were removed "
                f"from the prior version: {', '.join(sorted(missing_fields))}",
                code="SCHEMA_INCOMPATIBLE",
                details={"missing_fields": sorted(missing_fields)},
            )

    # 4. Create File + Dataset (same as workflow _create_dataset_version_task)
    with transaction.atomic():
        content_type = CONTENT_TYPE_MAP.get(file_format, "application/octet-stream")
        file_hash = hashlib.sha256(file_content).hexdigest()
        from hub.apps.assets.models import Asset, AssetStatus
        from hub.apps.datasets.models import Dataset
        from hub.apps.datasets.schema_inference import (
            extract_sample_data,
            infer_schema_from_csv,
            infer_schema_from_json,
            infer_schema_from_parquet,
        )
        from hub.apps.files.models import File, FileStatus
        from hub.apps.files.storage import S3StorageClient

        created_by = scheduled_ingestion.created_by
        file_obj = File.objects.create(
            tenant=tenant,
            name=Path(file_path).name,
            content_type=content_type,
            size=len(file_content),
            status=FileStatus.ACTIVE,
            created_by=created_by,
            content_sha256=file_hash,
        )
        storage = S3StorageClient()
        storage_path = storage.save_file(
            tenant_id=str(tenant.id),
            file_id=str(file_obj.id),
            file_content=ContentFile(file_content, name=Path(file_path).name),
        )
        file_obj.storage_path = storage_path
        file_obj.save(update_fields=["storage_path"])

        asset = scheduled_ingestion.asset
        if asset_id:
            try:
                asset = Asset.objects.get(id=asset_id, tenant=tenant)
            except Asset.DoesNotExist:
                pass
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
                # Audit-pass GAP-A: mark every ConflictError as a
                # permanent file-failure first. The original
                # implementation only marked ``ASSET_KEY_RETIRED``,
                # leaving the rare ``ASSET_KEY_EXISTS`` race-recovery
                # edge case (when the racer's row vanished between
                # commit and re-fetch in
                # ``create_or_get_idempotent``) without a DLQ-sync
                # record. Now every ConflictError code lands a
                # permanent-failure entry so the run summary always
                # reflects the rejection.
                _mark_permanent_failure(
                    scheduled_ingestion,
                    file_path,
                    exc.message,
                    exc.code or "ASSET_CONFLICT",
                )
                if exc.code == "ASSET_KEY_RETIRED":
                    logger.warning(
                        "scheduled_ingestion_asset_key_retired",
                        extra={
                            "scheduled_ingestion_id": str(
                                scheduled_ingestion.id
                            ),
                            "tenant_id": str(tenant.id),
                            "asset_key": asset_key,
                            "asset_id": exc.details.get("asset_id"),
                        },
                    )
                    scheduled_ingestion_asset_key_retired_total.add(
                        1,
                        attributes={
                            "scheduled_ingestion_id": str(
                                scheduled_ingestion.id
                            ),
                            "tenant_id": str(tenant.id),
                        },
                    )
                # Re-raise as ServiceValidationError so the worker
                # run-lifecycle treats this the same as any other
                # business-rules / validation rejection.
                raise ServiceValidationError(
                    exc.message,
                    code=exc.code,
                    details=exc.details,
                )
            except _AssetValidationError as exc:
                # Phase 250.2.C.4 — worker error shape == HTTP API
                # error shape; the raise contract here MUST mirror
                # ``POST /assets/`` so a downstream consumer of
                # the run failure can handle both paths uniformly.
                _mark_permanent_failure(
                    scheduled_ingestion,
                    file_path,
                    exc.message,
                    exc.code or "VALIDATION_ERROR",
                )
                raise ServiceValidationError(
                    exc.message,
                    code=exc.code or "VALIDATION_ERROR",
                    details=exc.details,
                )
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

        if asset and scheduled_ingestion.auto_activate:
            asset.status = AssetStatus.ACTIVE
            asset.save(update_fields=["status"])

        # 5. Index (Search)
        try:
            from hub.apps.search.indexing import SearchIndexer

            SearchIndexer.index_dataset(dataset)
        except (ConnectionError, TimeoutError, ValueError, AttributeError) as e:
            logger.warning(
                "Search index failed",
                extra={"dataset_id": str(dataset.id), "error_type": type(e).__name__},
            )
        except Exception as e:
            logger.warning(
                "Unexpected error during search indexing",
                extra={"dataset_id": str(dataset.id), "error_type": type(e).__name__},
                exc_info=True,
            )

        # 6. Incremental state
        state_manager = IncrementalStateManager(scheduled_ingestion)
        state_manager.mark_file_processed(
            file_path=file_path, file_timestamp=timezone.now(), dataset_id=str(dataset.id)
        )

        # 7. Compliance (if configured in ingestion source_config; requires created_by for job ownership)
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
            except (ValidationError, NotFoundError, PermissionError) as e:
                logger.warning(
                    "Compliance run creation failed",
                    extra={
                        "dataset_id": str(dataset.id),
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                    exc_info=True,
                )
            except Exception as e:
                logger.warning(
                    "Unexpected error during compliance run creation",
                    extra={"dataset_id": str(dataset.id), "error_type": type(e).__name__},
                    exc_info=True,
                )

        # 8. Semantic mapping (if configured in ingestion source_config, applicable to datasets)
        if source_config.get("run_semantic_mapping") and dataset:
            try:
                from hub.apps.semantic.utils import map_dataset_to_semantic

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
            except Exception as e:
                logger.warning(
                    "Unexpected error during semantic mapping",
                    extra={"dataset_id": str(dataset.id), "error_type": type(e).__name__},
                    exc_info=True,
                )

    return {
        "file_id": str(file_obj.id),
        "dataset_id": str(dataset.id),
        "asset_id": str(asset.id) if asset else None,
    }


def _mark_permanent_failure(
    scheduled_ingestion: ScheduledIngestion,
    file_path: str,
    error_message: str,
    error_code: Optional[str] = None,
) -> None:
    """Record permanent failure in ingestion state (DLQ sync at run completion)."""
    state_manager = IncrementalStateManager(scheduled_ingestion)
    state_manager.mark_file_failed(
        file_path=file_path,
        error_message=error_message,
        error_code=error_code,
        retry_count=1,
        max_retries=1,
    )
