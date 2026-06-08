"""  # noqa: D400
Compliance Service

Service layer for compliance run operations.
All create/update/delete paths call ComplianceBusinessRules before mutation.
"""
import os
from typing import Any, Dict, List, Optional
from django.db import transaction
from django.utils import timezone

from hub.apps.core.services.base import (
    BaseService,
    NotFoundError,
    ValidationError,
)
from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
from hub.apps.compliance.business_rules import ComplianceBusinessRules


class ComplianceService(BaseService):
    """
    Service for compliance run operations.

    Provides business logic for:
    - Compliance run creation (with business rules validation)
    - Compliance run update and delete (with validation)
    - Compliance result persistence (sync and async paths)
    """

    service_name = "compliance_service"

    def __init__(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        self.tenant_id = tenant_id
        self.user_id = user_id

    @transaction.atomic
    def create_compliance_run(
        self,
        tenant_id: str,
        user_id: str,
        asset_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        file_id: Optional[str] = None,
        scan_mode: str = "internal",
        applicable_regulations: Optional[List[str]] = None,
        legal_basis: Optional[str] = None,
        destination_jurisdiction: Optional[str] = None,
        tenant=None,
        user=None,
        asset=None,
        dataset=None,
        file_obj=None,
    ) -> ComplianceRun:
        """
        Create a compliance run. Validates via ComplianceBusinessRules.

        Args:
            tenant_id: Tenant UUID
            user_id: User UUID
            asset_id: Optional asset UUID
            dataset_id: Optional dataset UUID
            file_id: Optional file UUID
            scan_mode: Scan mode (internal/external)
            applicable_regulations: Optional list of regulations
            legal_basis: Optional legal basis (e.g. 'CONSENT')
            destination_jurisdiction: Optional destination jurisdiction
            tenant: Optional resolved tenant instance
            user: Optional resolved user instance
            asset, dataset, file_obj: Optional resolved resource instances

        Returns:
            Created ComplianceRun instance

        Raises:
            ValidationError: If ComplianceBusinessRules reject
        """
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User
        from hub.apps.assets.models import Asset
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File
        from hub.apps.jobs.models import JobType
        from hub.apps.jobs.utils import create_job, get_job_timeout

        # Plan limit enforcement (monthly)
        from hub.apps.tenants.services import PlanLimitService
        plan_limit_service = PlanLimitService(tenant_id=tenant_id)
        plan_limit_service.check_limit(
            tenant_id=tenant_id,
            limit_key="max_compliance_runs_per_month",
            delta=1,
        )

        try:
            tenant = tenant or Tenant.objects.get(id=tenant_id)
        except Tenant.DoesNotExist:
            raise NotFoundError(
                "Tenant not found", details={"tenant_id": tenant_id}
            )
        try:
            user = user or User.objects.get(id=user_id)
        except User.DoesNotExist:
            raise NotFoundError(
                "User not found", details={"user_id": user_id}
            )

        if asset is None and asset_id:
            try:
                asset = Asset.objects.get(
                    id=asset_id, tenant_id=tenant_id
                )
            except Asset.DoesNotExist:
                raise ValidationError(
                    "Asset not found",
                    code="BUSINESS_RULES_VALIDATION",
                    details={"asset_id": asset_id},
                )
        if dataset is None and dataset_id:
            try:
                dataset = Dataset.objects.get(
                    id=dataset_id, tenant_id=tenant_id
                )
            except Dataset.DoesNotExist:
                raise ValidationError(
                    "Dataset not found",
                    code="BUSINESS_RULES_VALIDATION",
                    details={"dataset_id": dataset_id},
                )
            if asset and dataset.asset != asset:
                raise ValidationError(
                    "Dataset does not belong to the specified asset",
                    code="BUSINESS_RULES_VALIDATION",
                )
            # Inherit asset from dataset when only dataset_id provided
            if asset is None and dataset.asset_id:
                asset = dataset.asset
        if file_obj is None and file_id:
            try:
                file_obj = File.objects.get(
                    id=file_id, tenant_id=tenant_id
                )
            except File.DoesNotExist:
                raise ValidationError(
                    "File not found",
                    code="BUSINESS_RULES_VALIDATION",
                    details={"file_id": file_id},
                )

        # Validate via ComplianceBusinessRules before any mutation
        payload_run = ComplianceRun(
            tenant_id=tenant_id,
            asset=asset,
            dataset=dataset,
            file=file_obj,
            status=ComplianceRunStatus.PENDING,
        )
        rules = ComplianceBusinessRules(
            tenant_id=tenant_id, user_id=user_id
        )
        result = rules.validate(
            compliance_run=payload_run,
            tenant=tenant,
            user=user,
            validation_type="compliance_run",
        )
        if not result.is_valid:
            raise ValidationError(
                "; ".join(result.errors),
                code="BUSINESS_RULES_VALIDATION",
                details=result.details,
            )

        # Create job and run.  executed_by_prefect=True prevents immediate
        # enqueue; we enqueue after writing compliance_run_id into job.
        import uuid
        temp_resource_id = str(uuid.uuid4())
        job = create_job(
            tenant=tenant,
            user=user,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=temp_resource_id,
            details_json={
                "scan_mode": scan_mode,
                "applicable_regulations": applicable_regulations or [],
                "legal_basis": legal_basis,
                "destination_jurisdiction": destination_jurisdiction,
            },
            timeout_seconds=get_job_timeout(JobType.COMPLIANCE_RUN),
            executed_by_prefect=True,
        )
        compliance_run = ComplianceRun.objects.create(
            tenant=tenant,
            asset=asset,
            dataset=dataset,
            file=file_obj,
            job=job,
            status=ComplianceRunStatus.PENDING,
        )
        job.resource_id = str(compliance_run.id)
        job.details_json["compliance_run_id"] = str(compliance_run.id)
        job.save(update_fields=["resource_id", "details_json"])

        try:
            from hub.apps.jobs.tasks import process_job
            from hub.apps.jobs.utils import (
                check_tenant_job_limits,
                get_queue,
                get_queue_for_job_type,
                increment_tenant_job_counter,
            )

            can_create, error_message = check_tenant_job_limits(
                str(tenant.id)
            )
            if not can_create:
                raise ValidationError(
                    error_message or "Tenant job limit exceeded"
                )

            increment_tenant_job_counter(str(tenant.id), "queued")

            queue_name = get_queue_for_job_type(JobType.COMPLIANCE_RUN)
            queue = get_queue(queue_name)
            _job_id = str(job.id)
            _queue = queue
            _timeout = get_job_timeout(JobType.COMPLIANCE_RUN)
            transaction.on_commit(
                lambda: _queue.enqueue(
                    process_job,
                    _job_id,
                    job_type=JobType.COMPLIANCE_RUN,
                    timeout=_timeout,
                )
            )
        except Exception as e:
            import logging
            _logger = logging.getLogger(__name__)
            _logger.error(
                "Failed to enqueue compliance run job %s (run %s): %s. "
                "Marking run and job as FAILED to avoid PENDING-forever. "
                "Ensure Redis and the RQ worker are running.",
                job.id,
                compliance_run.id,
                e,
                exc_info=True,
            )
            # ── Recovery: mark run + job as FAILED so they don't stay ──
            # ── PENDING forever with no worker to process them.      ──
            from hub.apps.jobs.models import JobStatus

            _now = timezone.now()
            compliance_run.status = ComplianceRunStatus.FAILED
            compliance_run.completed_at = _now
            # error_message was removed in Phase 278 (Django 6 upgrade);
            # persist error context in metadata_json instead.
            meta = compliance_run.metadata_json or {}
            meta["error_message"] = (
                f"Job enqueue failed: {e}. "
                "Verify Redis/RQ connectivity."
            )[:500]
            compliance_run.metadata_json = meta
            compliance_run.save(
                update_fields=["status", "completed_at", "metadata_json", "updated_at"],
            )
            job.status = JobStatus.FAILED
            job.completed_at = _now
            job.error_message = (
                f"Failed to enqueue COMPLIANCE_RUN job: {e}"
            )[:2000]
            job.save(
                update_fields=["status", "completed_at", "error_message", "updated_at"],
            )

        return compliance_run

    # ------------------------------------------------------------------
    # Shared result-persistence helper (19.10.4)
    # ------------------------------------------------------------------

    @staticmethod
    def _persist_result(run: ComplianceRun, result_data: dict) -> None:
        """
        Persist a compliance service scan result onto a ComplianceRun.

        Used by both the synchronous execute path and the async poll task
        so that result-mapping logic lives in exactly one place.

        Args:
            run: ComplianceRun instance (in any pre-completion status).
            result_data: JSON dict returned by the compliance service.
        """
        # run.job is a ForeignKey descriptor; truthy check avoids the
        # django-stubs false-positive on the `job_id` attname.
        scan_mode = (
            run.job.details_json.get("scan_mode", "internal")
            if run.job
            else "internal"
        )

        # Phase 213.G.4 — defensive guard. If a caller hands us a FAILED
        # payload (legacy callers, retry shims, sync fallback after the
        # microservice already failed), do NOT mark the run SUCCEEDED.
        # Persist the error fields and bail out so the FAILED-row
        # invariant (regulation_mapping_json.error is not None) holds
        # for every code path, not just the poll-task path.
        _incoming_status = str(result_data.get("status") or "").upper()
        if _incoming_status in {"FAILED", "ERROR"}:
            error_detail = (
                result_data.get("error")
                or result_data.get("detail")
                or result_data.get("message")
                or "compliance scan failed"
            )
            existing_mapping = dict(run.regulation_mapping_json or {})
            existing_mapping["error"] = error_detail
            existing_mapping["error_type"] = "EXECUTION_ERROR"
            run.regulation_mapping_json = existing_mapping
            run.status = ComplianceRunStatus.FAILED
            # Fail-closed for any caller that reads these fields.
            run.allowed_to_store = False
            run.completed_at = timezone.now()
            run.save(
                update_fields=[
                    "status",
                    "regulation_mapping_json",
                    "allowed_to_store",
                    "completed_at",
                    "updated_at",
                ]
            )
            return

        run.status = ComplianceRunStatus.SUCCEEDED
        run.overall_status = result_data.get("overall_status")
        run.risk_level = result_data.get("risk_level")

        allowed_to_store = result_data.get("allowed_to_store")
        # Fail-closed: UNKNOWN overall_status or missing flag → block
        if (
            result_data.get("overall_status") == "UNKNOWN"
            or allowed_to_store is None
        ):
            allowed_to_store = False
        run.allowed_to_store = bool(allowed_to_store)

        run.detected_categories_json = result_data.get(
            "detected_categories", []
        )
        run.column_findings_json = result_data.get("column_findings", [])

        # v2 fields
        # NOTE: compliance service emits "localization_alert" (American spelling);
        # the Django model field is "localisation_alert" (British).
        run.cross_border_alert = result_data.get("cross_border_alert")
        run.localisation_alert = result_data.get("localization_alert")
        run.legal_basis_violations = result_data.get(
            "legal_basis_violations"
        )

        # Build regulation_mapping_json preserving v2 sub-keys
        reg_mapping = dict(result_data.get("regulation_mapping") or {})
        if result_data.get("schema_version"):
            reg_mapping["schema_version"] = result_data["schema_version"]
        if result_data.get("regulation_summary"):
            reg_mapping["regulation_summary"] = (
                result_data["regulation_summary"]
            )
        if result_data.get("metadata"):
            reg_mapping["metadata"] = result_data["metadata"]

        run.regulation_mapping_json = reg_mapping
        run.regulations = result_data.get("applicable_regulations", [])

        # Metering
        now = timezone.now()
        started = run.started_at or now
        execution_time = (now - started).total_seconds()
        metadata = result_data.get("metadata") or {}
        run.regulation_mapping_json["metering"] = {
            "operation_type": "COMPLIANCE_RUN",
            "rows_scanned": metadata.get("total_rows", 0),
            "columns_scanned": metadata.get("total_columns", 0),
            "execution_time_seconds": round(execution_time, 2),
            "scan_mode": scan_mode,
            "risk_score": result_data.get("risk_score", 0.0),
            "risk_level": result_data.get("risk_level"),
            "allowed_to_store": run.allowed_to_store,
            "regulations_checked": result_data.get(
                "applicable_regulations", []
            ),
        }

        run.completed_at = now
        run.save(
            update_fields=[
                "status",
                "overall_status",
                "risk_level",
                "allowed_to_store",
                "detected_categories_json",
                "column_findings_json",
                "regulation_mapping_json",
                "regulations",
                "cross_border_alert",
                "localisation_alert",
                "legal_basis_violations",
                "completed_at",
                "updated_at",
            ]
        )

        # Update asset compliance status when applicable.
        # Use `run.asset` (FK descriptor) rather than `run.asset_id`
        # (FK attname) to keep django-stubs happy.
        if run.asset is not None:
            from hub.apps.assets.models import (
                ComplianceStatus as AssetComplianceStatus,
            )
            status_map = {
                "PASS": AssetComplianceStatus.PASS,
                "WARN": AssetComplianceStatus.WARN,
                "FAIL": AssetComplianceStatus.FAIL,
            }
            # overall_status is Optional[str]; guard against None before
            # using as a dict key to satisfy mypy.
            comp_status = status_map.get(
                run.overall_status or "",
                AssetComplianceStatus.UNKNOWN,
            )
            run.asset.compliance_status = comp_status
            run.asset.save(update_fields=["compliance_status"])

            # Notify user that compliance scan completed
            try:
                from hub.apps.notifications.utils import create_user_notification

                notify_user = (
                    run.created_by
                    if hasattr(run, "created_by") and run.created_by
                    else run.asset.created_by
                )
                if notify_user and run.asset.tenant:
                    create_user_notification(
                        user=notify_user,
                        tenant=run.asset.tenant,
                        title="Compliance Scan Complete",
                        message=f"Compliance scan for '{run.asset.name}' completed: {run.overall_status or 'UNKNOWN'}. Storage {'allowed' if run.allowed_to_store else 'blocked'}.",
                        notification_type="SUCCESS" if run.allowed_to_store else "WARNING",
                        category="COMPLIANCE",
                        resource_type="COMPLIANCE_RUN",
                        resource_id=str(run.id),
                    )
            except Exception:
                pass  # Notifications must never block compliance pipeline

    # ------------------------------------------------------------------
    # Compliance service call dispatcher (19.10.4)
    # ------------------------------------------------------------------

    @staticmethod
    def _call_compliance_service(
        compliance_run: ComplianceRun,
        file_content: bytes,
        file_format: str,
        scan_mode: str,
        applicable_regulations: Optional[List[str]],
        legal_basis: Optional[str],
        destination_jurisdiction: Optional[str],
        tenant_id: str,
        correlation_id: str,
    ) -> None:
        """
        Call the compliance microservice, handling both async (202) and
        synchronous (200) response paths.

        Async path (202):
          - Sets ComplianceRun.status = QUEUED
          - Persists metadata_json = {"job_id": "...", "poll_url": "..."}
          - Enqueues poll_compliance_job on job_default queue

        Sync path (200 or async-endpoint unavailable):
          - Calls _persist_result directly
        """
        import logging
        from hub.apps.compliance.service_client import (
            ComplianceServiceClient,
        )

        logger = logging.getLogger(__name__)
        client = ComplianceServiceClient()

        try:
            # Use synchronous /scan-file by default.  The async path
            # (scan_file_async → 202 → RQ poll via transaction.on_commit)
            # has a fundamental timing gap when called from synchronous
            # workflows: the RQ job is only enqueued after the outer
            # transaction commits, but the workflow's activation step
            # reads compliance_status BEFORE the commit, so the result
            # is always UNKNOWN and activation is blocked.
            #
            # Sync scanning blocks until the compliance service returns
            # a result, eliminating the gap.  The RQ job worker also
            # calls this code path and benefits from the simpler sync
            # approach (no polling needed).
            #
            # Async is retained as an opt-in via COMPLIANCE_USE_ASYNC=1
            # for deployments where scan latency exceeds HTTP timeouts.
            _use_async = os.environ.get("COMPLIANCE_USE_ASYNC", "").lower() in ("1", "true", "yes")

            if not _use_async:
                sync_result = client.scan_file(
                    file_content=file_content,
                    file_format=file_format,
                    scan_mode=scan_mode,
                    applicable_regulations=applicable_regulations,
                    tenant_id=tenant_id,
                    correlation_id=correlation_id,
                )
                ComplianceService._persist_result(
                    compliance_run=compliance_run,
                    result=sync_result,
                )
                return

            async_result = client.scan_file_async(
                file_content=file_content,
                file_format=file_format,
                scan_mode=scan_mode,
                applicable_regulations=applicable_regulations,
                legal_basis=legal_basis,
                destination_jurisdiction=destination_jurisdiction,
                tenant_id=tenant_id,
                correlation_id=correlation_id,
            )
            http_status = async_result.pop("_http_status", 202)

            if http_status == 202:
                # Async path: compliance service accepted the job
                job_id = async_result.get("job_id", "")
                poll_url = async_result.get("poll_url", "")
                compliance_run.status = ComplianceRunStatus.QUEUED
                compliance_run.metadata_json = {
                    "job_id": job_id,
                    "poll_url": poll_url,
                }
                compliance_run.save(
                    update_fields=["status", "metadata_json", "updated_at"]
                )
                logger.info(
                    "compliance_run_queued_async",
                    extra={
                        "run_id": str(compliance_run.id),
                        "job_id": job_id,
                    },
                )
                # Import inside the branch to avoid module-level
                # circular dependency (tasks.py imports services.py
                # only inside function bodies, so this is safe).
                from hub.apps.compliance.tasks import (
                    poll_compliance_job,
                )
                from django_rq import get_queue
                _queue = get_queue("job_default")
                _run_id = compliance_run.id
                transaction.on_commit(
                    lambda: _queue.enqueue(
                        poll_compliance_job,
                        _run_id,
                        job_timeout=1800,
                    )
                )
            else:
                # Synchronous 200 response from async endpoint
                ComplianceService._persist_result(
                    compliance_run, async_result
                )

        except Exception as exc:
            # Async endpoint unavailable — fall back to synchronous scan
            logger.info(
                "compliance_async_fallback_to_sync",
                extra={
                    "run_id": str(compliance_run.id),
                    "reason": str(exc),
                },
            )
            result = client.scan_file(
                file_content=file_content,
                file_format=file_format,
                scan_mode=scan_mode,
                applicable_regulations=(
                    applicable_regulations or None
                ),
                tenant_id=tenant_id,
                correlation_id=correlation_id,
                legal_basis=legal_basis,
            )
            ComplianceService._persist_result(compliance_run, result)

    @staticmethod
    def run_external_compliance_scan(
        file_content: bytes,
        file_format: str,
        scan_mode: str = "internal",
        applicable_regulations: Optional[List[str]] = None,
        contract: Optional[Any] = None,
        tenant_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        legal_basis: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synchronous compliance scan via microservice.

        Phase 205: breaker lives in ``ComplianceServiceClient.scan_file`` (shared
        ``compliance-service``); no stacked decorator on this wrapper.
        """
        from hub.apps.compliance.service_client import ComplianceServiceClient

        return ComplianceServiceClient().scan_file(
            file_content,
            file_format,
            scan_mode=scan_mode,
            applicable_regulations=applicable_regulations,
            contract=contract,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
            legal_basis=legal_basis,
        )

    # ------------------------------------------------------------------
    # Phase 250.1.A.1 — fail-closed-at-intake in-memory scan
    # ------------------------------------------------------------------

    #: File-format MIME / extension hints recognised by ``scan_inmemory``.
    #: Anything unrecognised falls back to "csv" — the compliance
    #: microservice's default — so a misclassified upload still gets
    #: scanned rather than 5xx-ing the whole intake.
    _FORMAT_BY_CONTENT_TYPE: Dict[str, str] = {
        "text/csv": "csv",
        "application/csv": "csv",
        "application/json": "json",
        "text/json": "json",
        "application/x-ndjson": "json",
        "application/parquet": "parquet",
        "application/x-parquet": "parquet",
    }
    _FORMAT_BY_EXTENSION: Dict[str, str] = {
        "csv": "csv",
        "json": "json",
        "ndjson": "json",
        "parquet": "parquet",
    }

    @classmethod
    def _resolve_file_format(cls, file_obj) -> str:
        """Pick the file format string the compliance microservice expects.

        Order: explicit content_type → filename extension → CSV fallback.
        """
        ct = (file_obj.content_type or "").lower().strip()
        if ct in cls._FORMAT_BY_CONTENT_TYPE:
            return cls._FORMAT_BY_CONTENT_TYPE[ct]
        if file_obj.name:
            ext = (file_obj.name.rsplit(".", 1)[-1] or "").lower()
            if ext in cls._FORMAT_BY_EXTENSION:
                return cls._FORMAT_BY_EXTENSION[ext]
        return "csv"

    @staticmethod
    @transaction.atomic
    def scan_inmemory(
        file_id: str,
        tenant,
        legal_basis: Optional[str] = None,
        applicable_regulations: Optional[List[str]] = None,
        scan_mode: str = "internal",
        destination_jurisdiction: Optional[str] = None,
        user=None,
        correlation_id: Optional[str] = None,
    ) -> ComplianceRun:
        """Run a compliance scan against ``file_id`` synchronously.

        Phase 250.1.A.1 — the asset-creation workflow re-sequence
        needs to know whether the file's payload PASSes / WARNs / FAILs
        BEFORE deciding whether to persist the ``Asset`` row. That's
        impossible with :meth:`create_compliance_run` because it
        always wires the new run to a pre-existing ``Asset`` (the
        whole point of the re-sequence is to undo that ordering).

        ``scan_inmemory``:

        * Persists a ``ComplianceRun`` keyed on ``file`` only — no
          ``asset`` / ``dataset`` FK — so the row is durable for
          audit / replay even if the workflow later refuses to
          persist an Asset.
        * Downloads the file payload from S3 and calls the compliance
          microservice synchronously via :meth:`scan_file` (the async
          ``202`` path can't return the gate signal in-band).
        * Returns the populated ``ComplianceRun`` so the caller can
          inspect ``allowed_to_store`` / ``overall_status``.

        Args:
            file_id: UUID of the :class:`File` to scan.
            tenant: Resolved :class:`Tenant` (the workflow already has
                this from the request context — we don't re-fetch).
            legal_basis: GDPR-style legal basis the controller is
                relying on (forwarded to the microservice for the
                legal-basis-violation check).
            applicable_regulations: Optional list of regulations
                (e.g. ``["GDPR", "LGPD"]``); empty list = service
                picks the default for the tenant region.
            scan_mode: ``"internal"`` (Hub-managed) or ``"external"``
                (read-only scan) — forwarded to the microservice.
            destination_jurisdiction: ISO region the data is destined
                for (drives the cross-border check).
            user: Optional :class:`User` for audit; falls back to
                ``file.created_by``.
            correlation_id: Trace-ID to forward to the microservice;
                defaults to ``str(file_id)`` so logs stitch together.

        Returns:
            The persisted :class:`ComplianceRun`. Callers should
            ``refresh_from_db()`` if they need the latest state after
            an async race; this synchronous path always returns a
            terminal-status row.

        Raises:
            ValidationError: ``file_id`` does not exist or belongs
                to a different tenant.
        """
        from hub.apps.files.models import File
        from hub.apps.files.storage import S3StorageClient
        from hub.apps.jobs.models import JobType
        from hub.apps.jobs.utils import create_job, get_job_timeout

        if not tenant:
            raise ValidationError(
                "tenant is required for in-memory compliance scan",
                code="BUSINESS_RULES_VALIDATION",
            )

        try:
            file_obj = File.objects.get(id=file_id, tenant=tenant)
        except File.DoesNotExist:
            raise ValidationError(
                "File not found for in-memory compliance scan",
                code="BUSINESS_RULES_VALIDATION",
                details={
                    "file_id": str(file_id),
                    "tenant_id": str(tenant.id),
                },
            )

        actor = user or file_obj.created_by
        effective_correlation_id = correlation_id or str(file_obj.id)

        # Job tracks the scan for the operations / billing surface.
        # ``executed_by_prefect=True`` keeps RQ from picking up an
        # additional poll cycle — the synchronous scan runs inline.
        job = create_job(
            tenant=tenant,
            user=actor,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(file_obj.id),
            details_json={
                "scan_mode": scan_mode,
                "applicable_regulations": applicable_regulations or [],
                "legal_basis": legal_basis,
                "destination_jurisdiction": destination_jurisdiction,
                "inmemory": True,
                "correlation_id": effective_correlation_id,
            },
            timeout_seconds=get_job_timeout(JobType.COMPLIANCE_RUN),
            executed_by_prefect=True,
        )

        run: ComplianceRun = ComplianceRun.objects.create(
            tenant=tenant,
            asset=None,        # Phase 250.1.A.1 — NO asset attached.
            dataset=None,      # Same — pre-persistence in the workflow.
            file=file_obj,
            job=job,
            regulations=applicable_regulations or [],
            status=ComplianceRunStatus.RUNNING,
            started_at=timezone.now(),
        )
        # Re-link the job back to the run id so audit replays can
        # join on either side of the FK.
        job.resource_id = str(run.id)
        job.details_json["compliance_run_id"] = str(run.id)
        job.save(update_fields=["resource_id", "details_json"])

        # Download payload + dispatch the synchronous scan.
        # File-system / network errors here are converted into a
        # FAILED row + ``allowed_to_store=False`` so the workflow
        # caller never has to interpret a partial ``RUNNING`` row
        # as ambiguous.
        from hub.apps.compliance.service_client import ComplianceServiceClient

        try:
            storage_client = S3StorageClient()
            file_content = storage_client.get_file_content(file_obj.storage_path)
            file_format = ComplianceService._resolve_file_format(file_obj)

            client = ComplianceServiceClient()
            result = client.scan_file(
                file_content=file_content,
                file_format=file_format,
                scan_mode=scan_mode,
                applicable_regulations=applicable_regulations,
                tenant_id=str(tenant.id),
                correlation_id=effective_correlation_id,
                legal_basis=legal_basis,
            )
            ComplianceService._persist_result(run, result)
        except Exception as exc:  # noqa: BLE001 — see fail-closed contract below
            # Fail-closed: ANY exception leaves a FAILED row with
            # ``allowed_to_store=False`` so the workflow gate refuses
            # to persist the Asset. ``_persist_result`` already knows
            # how to write a FAILED-shaped payload, so we hand it the
            # right shape rather than re-implementing that branch.
            import logging

            logging.getLogger(__name__).warning(
                "compliance_scan_inmemory_failed",
                extra={
                    "file_id": str(file_obj.id),
                    "tenant_id": str(tenant.id),
                    "correlation_id": effective_correlation_id,
                    "error": str(exc),
                },
                exc_info=True,
            )
            ComplianceService._persist_result(
                run,
                {
                    "status": "FAILED",
                    "error": str(exc),
                    "overall_status": "UNKNOWN",
                    "allowed_to_store": False,
                    "metadata": {},
                },
            )

        run.refresh_from_db()
        return run

    @staticmethod
    def apply_degraded_compliance_status_if_circuit_open(
        asset, request=None, actor_user=None
    ) -> None:
        """
        If compliance-service circuit is OPEN and the asset has a dataset,
        set ``compliance_status`` to WARN and log
        ``COMPLIANCE_SERVICE_UNAVAILABLE``.
        """
        from hub.apps.assets.models import (
            Asset,
            ComplianceStatus as AssetComplianceStatus,
        )
        from hub.apps.audit.utils import create_audit_event
        from hub.apps.core.resilience.circuit_breaker import (
            CircuitBreakerState,
        )
        from hub.apps.core.resilience.service_breakers import (
            get_shared_circuit_breaker,
        )
        from hub.apps.datasets.models import Dataset

        if not Dataset.objects.filter(asset_id=asset.id).exists():
            return

        br = get_shared_circuit_breaker("compliance-service")
        if br.get_state() != CircuitBreakerState.OPEN:
            return

        st = br.get_status()
        Asset.objects.filter(pk=asset.pk).update(
            compliance_status=AssetComplianceStatus.WARN
        )

        user = actor_user
        if user is None and request is not None:
            u = getattr(request, "user", None)
            if u is not None and getattr(u, "is_authenticated", False):
                user = u

        create_audit_event(
            resource_type="ASSET",
            action="COMPLIANCE_SERVICE_UNAVAILABLE",
            actor_user=user,
            tenant=asset.tenant,
            resource_id=str(asset.id),
            result="WARNING",
            details={
                "circuit_state": "OPEN",
                "asset_id": str(asset.id),
                "last_failure": st.get("opened_at"),
                "failure_count": st.get("failure_count"),
            },
            request=request,
        )

    # ── Warehouse-native Compliance (Phase 285.10) ────────────────────

    @staticmethod
    def _resolve_engine(
        dataset=None,
        warehouse_config=None,
        requested_scan_mode=None,
    ) -> str:
        """Auto-detect compliance scan mode from dataset storage_type."""
        if requested_scan_mode:
            return requested_scan_mode
        if dataset is not None:
            meta = getattr(dataset, "snapshot_metadata", None) or {}
            if meta.get("storage_type") == "EXTERNAL_WAREHOUSE":
                return "WAREHOUSE_SQL"
            if getattr(dataset, "kind", None) == "EXTERNAL_REF":
                return "WAREHOUSE_SQL"
        if warehouse_config and warehouse_config.get("warehouse_type"):
            return "WAREHOUSE_SQL"
        return "FILE_SCAN"

    @staticmethod
    @transaction.atomic
    def scan_inmemory_warehouse(
        dataset,
        tenant,
        regulations=None,
        warehouse_config=None,
        user=None,
        correlation_id=None,
    ):
        """Run compliance PII/retention/classification checks directly in
        the customer's warehouse via SQL pushdown (Phase 285.10).

        Uses ``ComplianceWarehouseSQLCompiler`` to generate per-dialect
        SQL with ``SELECT COUNT(*)`` patterns — zero PII data transits
        back to Meshant.  Only aggregate match counts return.
        """
        from hub.apps.compliance.models import ComplianceRun, ComplianceRunStatus
        from hub.apps.compliance.warehouse_sql_compiler import (
            ComplianceWarehouseSQLCompiler,
        )
        from hub.apps.jobs.models import JobType
        from hub.apps.jobs.utils import create_job, get_job_timeout

        if not tenant:
            raise ValidationError(
                "tenant is required for warehouse compliance scan",
                code="BUSINESS_RULES_VALIDATION",
            )
        if not warehouse_config or not warehouse_config.get("table_fqn"):
            raise ValidationError(
                "warehouse_config.table_fqn is required",
                code="BUSINESS_RULES_VALIDATION",
            )

        warehouse_type = (warehouse_config.get("warehouse_type") or "").lower()
        if warehouse_type not in ("snowflake", "bigquery", "databricks"):
            raise ValidationError(
                f"Unsupported warehouse type: {warehouse_type}",
                code="WAREHOUSE_UNSUPPORTED_DIALECT",
            )

        effective_correlation_id = correlation_id or str(dataset.id)

        job = create_job(
            tenant=tenant,
            user=user,
            job_type=JobType.COMPLIANCE_RUN,
            resource_type="COMPLIANCE_RUN",
            resource_id=str(dataset.id),
            details_json={
                "warehouse_native": True,
                "correlation_id": effective_correlation_id,
                "warehouse_type": warehouse_type,
            },
            timeout_seconds=get_job_timeout(JobType.COMPLIANCE_RUN),
            executed_by_prefect=True,
        )

        run = ComplianceRun.objects.create(
            tenant=tenant,
            dataset=dataset,
            job=job,
            scan_mode="WAREHOUSE_SQL",
            warehouse_config=warehouse_config,
            status=ComplianceRunStatus.RUNNING,
            started_at=timezone.now(),
        )
        job.resource_id = str(run.id)
        job.details_json["compliance_run_id"] = str(run.id)
        job.save(update_fields=["resource_id", "details_json"])

        try:
            compiler = ComplianceWarehouseSQLCompiler()
            compiled = compiler.compile(
                scan_types=regulations or ["pii_email", "pii_phone", "pii_ssn",
                                            "pii_credit_card", "retention_breach",
                                            "classification_mismatch"],
                warehouse_type=warehouse_type,
                table_fqn=warehouse_config["table_fqn"],
            )

            from hub.apps.dq.services import _resolve_warehouse_connector
            connector = _resolve_warehouse_connector(
                warehouse_config, tenant_id=str(tenant.id),
            )

            results: list[dict] = []
            connector.connect()
            try:
                for c in compiled:
                    rows, _cols = connector.execute_query(c.sql)
                    match_count = rows[0][0] if rows else 0
                    results.append({
                        "check_name": c.check_name,
                        "check_type": c.check_type,
                        "column_name": c.column_name,
                        "match_count": match_count,
                        "sql_preview": c.sql[:200],
                    })
            finally:
                try:
                    connector.close()
                except Exception:
                    pass

            total_matches = sum(r["match_count"] for r in results)
            has_findings = total_matches > 0

            run.status = ComplianceRunStatus.SUCCEEDED
            run.overall_status = "PASS" if not has_findings else "WARN"
            run.risk_level = "HIGH" if has_findings else "LOW"
            run.allowed_to_store = not has_findings
            run.detected_categories_json = [
                r["check_type"] for r in results if r["match_count"] > 0
            ]
            run.completed_at = timezone.now()
            run.save(update_fields=[
                "status", "overall_status", "risk_level",
                "allowed_to_store", "detected_categories_json",
                "completed_at", "updated_at",
            ])

            try:
                from hub.apps.audit.utils import create_audit_event
                create_audit_event(
                    resource_type="COMPLIANCE_RUN",
                    action="COMPLIANCE_WAREHOUSE_SCANNED",
                    tenant=tenant,
                    resource_id=str(run.id),
                    details={
                        "compliance_run_id": str(run.id),
                        "warehouse_type": warehouse_type,
                        "table_fqn": warehouse_config.get("table_fqn"),
                        "total_matches": total_matches,
                        "correlation_id": effective_correlation_id,
                    },
                )
            except Exception:
                logger.warning("compliance_warehouse_audit_failed", exc_info=True)

        except Exception as exc:
            logger.warning(
                "compliance_scan_inmemory_warehouse_failed",
                extra={
                    "dataset_id": str(dataset.id),
                    "tenant_id": str(tenant.id),
                    "warehouse_type": warehouse_type,
                    "correlation_id": effective_correlation_id,
                    "error": str(exc),
                },
                exc_info=True,
            )
            run.status = ComplianceRunStatus.FAILED
            run.overall_status = "UNKNOWN"
            run.risk_level = "UNKNOWN"
            run.allowed_to_store = False
            # error_message was removed in Phase 278 (Django 6 upgrade);
            # persist error context in metadata_json instead.
            meta = run.metadata_json or {}
            meta["error_message"] = str(exc)[:2000]
            run.metadata_json = meta
            run.completed_at = timezone.now()
            run.save(update_fields=[
                "status", "overall_status", "risk_level",
                "allowed_to_store", "metadata_json",
                "completed_at", "updated_at",
            ])

        run.refresh_from_db()
        return run
