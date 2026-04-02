"""
Compliance Service

Service layer for compliance run operations.
All create/update/delete paths call ComplianceBusinessRules before mutation.
"""
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
            logger = logging.getLogger(__name__)
            logger.warning(
                "Failed to enqueue compliance run job %s (run %s): %s. "
                "Ensure Redis and the RQ worker are running.",
                job.id,
                compliance_run.id,
                e,
                exc_info=True,
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
