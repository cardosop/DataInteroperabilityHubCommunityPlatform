"""
Worker API Service Layer

process_file_for_run: validate file (ScheduledIngestionBusinessRules), optional DQ,
create File + Dataset, index, update incremental state; on failure mark_file_failed and DLQ sync at run completion.
Same order and semantics as hub ScheduledIngestionWorkflow per-file processing.

W3.8 (oss-release-remediation R2-P7/D6) — the File+Dataset creation
block moved to ``catalog_records.create_file_and_dataset_records``: the
ONE implementation shared with the dlt spine
(``hub.data_movement.ingestion_execution``) so the two entrypoints can
never diverge again. This module keeps the worker-path contract:
validation, DQ, plan limits, and the incremental-state marking.
"""

import contextlib
import logging
from typing import Any

from django.utils import timezone

from hub.apps.core.services.base import ValidationError as ServiceValidationError

from .business_rules import ScheduledIngestionBusinessRules
from .catalog_records import (
    _infer_format_from_path,
    check_ingestion_plan_limits,
    create_file_and_dataset_records,
)
from .incremental_state import IncrementalStateManager
from .models import ScheduledIngestion, ScheduledIngestionRun, ScheduledIngestionRunStatus

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS = ["CSV", "JSON", "PARQUET", "XLSX", "XLS"]


def process_file_for_run(
    run_id: str,
    file_path: str,
    file_content: bytes,
    tenant_id: str,
    user_id: str | None = None,
    asset_id: str | None = None,
    contract_id: str | None = None,
    dq_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
    # W3.1 (R2-P1) — the worker honors CANCELLED: no file is processed
    # for a cancelled run (checked before validation/limits so a
    # cancelled run leaves zero side effects).
    if run.status == ScheduledIngestionRunStatus.CANCELLED:
        raise ServiceValidationError(
            "Run was cancelled; no further files are processed",
            code="RUN_CANCELLED",
            details={"run_id": run_id, "status": run.status},
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
            code="UNSUPPORTED_FORMAT",
            details={"file_path": file_path, "file_format": file_format},
        )

    # 2. ScheduledIngestionBusinessRules (validation_type="source_structure" — no live connection test per file)
    rules = ScheduledIngestionBusinessRules(tenant_id=tenant_id, user_id=user_id)
    user = None
    if user_id:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        with contextlib.suppress(User.DoesNotExist):
            user = User.objects.get(id=user_id)
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

    # 2.5 R2-B2 (W2.7) — plan limits on the BACKGROUND path (the
    # request path checked; this sibling didn't — the P1 pattern).
    # Both checks run BEFORE any File row exists so a blocked run
    # leaves zero side effects. The checks live in
    # ``catalog_records.check_ingestion_plan_limits`` — the shared
    # per-file quota gate also used by the dlt spine (W3.8).
    try:
        check_ingestion_plan_limits(tenant_id=tenant_id, delta_bytes=file_content_length)
    except ServiceValidationError as exc:
        if getattr(exc, "code", None) == "plan_limit_exceeded":
            _mark_permanent_failure(
                scheduled_ingestion,
                file_path,
                str(exc.message),
                "PLAN_LIMIT_EXCEEDED",
            )
        raise

    # 3. Optional DQ (same as workflow _run_dq_check_task)
    dq_result = None
    dq_profile_key = dq_options.get("profile_key", "intake_basic_gx")
    dq_strict_mode = dq_options.get("strict_mode", True)
    min_quality_score = float(dq_options.get("min_quality_score", 0.8))
    contract = scheduled_ingestion.contract
    if contract_id:
        from hub.apps.contracts.models import Contract

        with contextlib.suppress(Contract.DoesNotExist):
            contract = Contract.objects.get(id=contract_id, tenant=tenant)

    def _run_dq() -> None:
        nonlocal dq_result
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
                    "DQ quality score below threshold",
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

    try:
        _run_dq()
    except ServiceValidationError:
        raise
    except Exception as e:  # noqa: BLE001 - the DQ error classification contract
        if dq_strict_mode:
            _mark_permanent_failure(scheduled_ingestion, file_path, str(e), "DQ_ERROR")
            raise ServiceValidationError(str(e), code="DQ_ERROR", details={}) from None
        logger.warning("DQ check failed (non-strict), continuing: %s", e)

    # 4. Create File + Dataset — the shared catalog-record core (W3.8):
    # schema inference, version resolution + compatibility check, the
    # File row + hub-storage upload + ClamAV gate, asset resolution +
    # auto-create, the Dataset row + version history, search index, and
    # the source_config-gated compliance/semantic enrichments. The dlt
    # spine runs the SAME core — one implementation, no sibling copies.
    result = create_file_and_dataset_records(
        scheduled_ingestion,
        file_path,
        file_content,
        asset_id=asset_id,
        dq_result=dq_result,
    )

    # 5. Incremental state
    state_manager = IncrementalStateManager(scheduled_ingestion)
    state_manager.mark_file_processed(
        file_path=file_path, file_timestamp=timezone.now(), dataset_id=str(result.dataset.id)
    )

    return {
        "file_id": str(result.file.id),
        "dataset_id": str(result.dataset.id),
        "asset_id": str(result.asset.id) if result.asset else None,
    }


def _mark_permanent_failure(
    scheduled_ingestion: ScheduledIngestion,
    file_path: str,
    error_message: str,
    error_code: str | None = None,
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
