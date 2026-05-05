"""
DQ Service

Service layer for DQ run operations.
All create/update/delete paths call DQBusinessRules before mutation.
"""
import logging
from typing import Dict, Any, Optional, List
from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

from hub.apps.core.services.base import BaseService, NotFoundError, ValidationError
from hub.apps.dq.models import DQRun, DQRunStatus, DQEngine
from hub.apps.dq.business_rules import DQBusinessRules


def resolve_engine_for_profile(profile_key: str) -> str:
    """Phase 240.3.A.8 — single source of truth for engine routing.

    Lifted out of ``DQService.create_dq_run`` so unit tests can pin
    the contract without standing up the full create-run flow
    (which involves business-rule validation + dq-service HTTP).
    The behaviour matches the previous inline block verbatim:

    * ``*_gx`` / contains ``"gx"`` → ``DQEngine.GREAT_EXPECTATIONS``
    * ``*_soda`` / contains ``"soda"`` → ``DQEngine.SODA``
    * anything else → ``DQEngine.GREAT_EXPECTATIONS`` (safe default)

    Order matters: ``_gx`` is checked first so a profile that
    accidentally contains both substrings (legacy keys) routes to
    GX rather than Soda.
    """
    if profile_key.endswith("_gx") or "gx" in profile_key.lower():
        return DQEngine.GREAT_EXPECTATIONS
    if profile_key.endswith("_soda") or "soda" in profile_key.lower():
        return DQEngine.SODA
    return DQEngine.GREAT_EXPECTATIONS


class DQService(BaseService):
    """
    Service for DQ run operations.

    Provides business logic for:
    - DQ run creation (with business rules validation)
    - DQ run update and delete (with validation)
    """

    service_name = "dq_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        self.tenant_id = tenant_id
        self.user_id = user_id

    @staticmethod
    def run_external_dq_check(
        file_content: bytes,
        file_format: str,
        profile_key: str = "intake_basic_gx",
        use_cache: bool = True,
        contract: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Run DQ against the external dq-service.

        Phase 205: same parameters as ``@circuit_breaker(service_name="dq-service",
        failure_threshold=5, timeout_seconds=60)`` are applied inside
        ``DQServiceClient`` via the shared breaker — not repeated here, to avoid
        nested ``call()`` double-counting failures.
        """
        from hub.apps.dq.service_client import DQServiceClient

        return DQServiceClient().run_dq(
            file_content,
            file_format,
            profile_key=profile_key,
            use_cache=use_cache,
            contract=contract,
        )

    # ------------------------------------------------------------------
    # Phase 250.1.A.2 — fail-closed-at-intake in-memory DQ scan
    # ------------------------------------------------------------------

    _FORMAT_BY_CONTENT_TYPE = {
        "text/csv": "csv",
        "application/csv": "csv",
        "application/json": "json",
        "text/json": "json",
        "application/x-ndjson": "json",
        "application/parquet": "parquet",
        "application/x-parquet": "parquet",
    }
    _FORMAT_BY_EXTENSION = {
        "csv": "csv",
        "json": "json",
        "ndjson": "json",
        "parquet": "parquet",
    }

    @classmethod
    def _resolve_file_format(cls, file_obj) -> str:
        """Pick the file format string the dq-service expects.

        Mirrors :meth:`ComplianceService._resolve_file_format` so the
        two pre-persistence gates can't disagree on what they're
        scanning.
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
        profile_key: Optional[str] = None,
        contract: Optional[Any] = None,
        user=None,
        correlation_id: Optional[str] = None,
    ) -> DQRun:
        """Run a DQ check against ``file_id`` synchronously.

        Phase 250.1.A.2 — companion to
        :meth:`ComplianceService.scan_inmemory`. The asset-creation
        workflow re-sequence calls both synchronously BEFORE
        persisting the ``Asset`` row so a FAIL on either gate refuses
        intake without leaving an orphan draft.

        ``scan_inmemory``:

        * Persists a ``DQRun`` keyed on ``file`` only — no ``asset`` /
          ``dataset`` FK — so the row is durable for audit / replay
          even if the workflow later refuses to persist an Asset.
        * Downloads the file payload from S3 and calls dq-service via
          :meth:`run_dq` (the synchronous interface — there is no
          async ``202`` path on dq-service today).
        * Returns the populated ``DQRun`` so the caller can inspect
          ``overall_status`` / ``quality_score``.

        Args:
            file_id: UUID of the :class:`File` to scan.
            tenant: Resolved :class:`Tenant`.
            profile_key: DQ profile key (e.g. ``"intake_basic_gx"``);
                defaults to the tenant's configured profile.
            contract: Optional :class:`Contract` instance — when set,
                custom quality rules + the contract's profile_key
                override the default per :class:`ContractQualityRulesExtractor`.
            user: Optional :class:`User` for audit; falls back to
                ``file.created_by``.
            correlation_id: Trace-ID forwarded to dq-service; defaults
                to ``str(file_id)`` so logs stitch together.

        Returns:
            The persisted :class:`DQRun` in a terminal status.

        Raises:
            ValidationError: ``file_id`` does not exist or belongs
                to a different tenant.
        """
        from hub.apps.files.models import File
        from hub.apps.files.storage import S3StorageClient
        from hub.apps.jobs.models import JobType
        from hub.apps.jobs.utils import create_job, get_job_timeout
        from hub.apps.tenants.services import get_tenant_dq_profile

        if not tenant:
            raise ValidationError(
                "tenant is required for in-memory DQ scan",
                code="BUSINESS_RULES_VALIDATION",
            )

        try:
            file_obj = File.objects.get(id=file_id, tenant=tenant)
        except File.DoesNotExist:
            raise ValidationError(
                "File not found for in-memory DQ scan",
                code="BUSINESS_RULES_VALIDATION",
                details={
                    "file_id": str(file_id),
                    "tenant_id": str(tenant.id),
                },
            )

        actor = user or file_obj.created_by
        effective_correlation_id = correlation_id or str(file_obj.id)
        resolved_profile_key = profile_key or get_tenant_dq_profile(str(tenant.id))
        engine = resolve_engine_for_profile(resolved_profile_key)

        job = create_job(
            tenant=tenant,
            user=actor,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=str(file_obj.id),
            details_json={
                "profile_key": resolved_profile_key,
                "engine": engine,
                "inmemory": True,
                "correlation_id": effective_correlation_id,
            },
            timeout_seconds=get_job_timeout(JobType.DQ_RUN),
            executed_by_prefect=True,
        )

        run: DQRun = DQRun.objects.create(
            tenant=tenant,
            asset=None,        # Phase 250.1.A.2 — pre-persistence.
            dataset=None,
            file=file_obj,
            job=job,
            profile_key=resolved_profile_key,
            engine=engine,
            status=DQRunStatus.RUNNING,
            started_at=timezone.now(),
        )
        job.resource_id = str(run.id)
        job.details_json["dq_run_id"] = str(run.id)
        job.save(update_fields=["resource_id", "details_json"])

        from hub.apps.dq.service_client import DQServiceClient

        try:
            storage_client = S3StorageClient()
            file_content = storage_client.get_file_content(file_obj.storage_path)
            file_format = DQService._resolve_file_format(file_obj)

            client = DQServiceClient()
            result = client.run_dq(
                file_content=file_content,
                file_format=file_format,
                profile_key=resolved_profile_key,
                use_cache=True,
                contract=contract,
                tenant_id=str(tenant.id),
            )

            # Successful execution path — persist the result onto the
            # row. Mirrors the schema written by ``execute_dq_run`` in
            # ``hub/apps/dq/views.py`` so downstream consumers
            # (workflow gate, alerting) see the same shape regardless
            # of which path persisted the row.
            row_count = (result.get("metadata") or {}).get("total_rows", 0)
            column_count = (result.get("metadata") or {}).get("total_columns", 0)
            execution_time = (
                timezone.now() - run.started_at
            ).total_seconds() if run.started_at else 0.0

            run.status = DQRunStatus.SUCCEEDED
            run.overall_status = result.get("overall_status")
            raw_score = result.get("quality_score")
            run.quality_score = (
                max(0.0, min(100.0, float(raw_score)))
                if raw_score is not None
                else None
            )
            run.checks_json = result.get("checks", [])
            run.details_json = {
                "engine_type": result.get("engine_type"),
                "engine_version": result.get("engine_version"),
                "profile_key": result.get("profile_key") or resolved_profile_key,
                "metadata": result.get("metadata") or {},
                "metering": {
                    "operation_type": "DQ_RUN",
                    "rows_inspected": row_count,
                    "columns_inspected": column_count,
                    "execution_time_seconds": round(execution_time, 2),
                    "engine_type": result.get("engine_type"),
                    "profile_key": result.get("profile_key") or resolved_profile_key,
                    "quality_score": result.get("quality_score"),
                    "checks_count": len(result.get("checks") or []),
                    "inmemory": True,
                },
            }
            run.completed_at = timezone.now()
            run.save(
                update_fields=[
                    "status",
                    "overall_status",
                    "quality_score",
                    "checks_json",
                    "details_json",
                    "completed_at",
                    "updated_at",
                ]
            )
        except Exception as exc:  # noqa: BLE001 — fail-closed on ANY exception
            logger.warning(
                "dq_scan_inmemory_failed",
                extra={
                    "file_id": str(file_obj.id),
                    "tenant_id": str(tenant.id),
                    "correlation_id": effective_correlation_id,
                    "error": str(exc),
                },
                exc_info=True,
            )
            run.status = DQRunStatus.FAILED
            # ``UNKNOWN`` so workflow gate code only needs a single
            # fail-closed predicate (``status not in PASS|WARN``).
            run.overall_status = "UNKNOWN"
            run.quality_score = 0.0
            run.checks_json = []
            run.details_json = {
                "error": str(exc),
                "error_code": "EXECUTION_ERROR",
                "inmemory": True,
            }
            run.completed_at = timezone.now()
            run.save(
                update_fields=[
                    "status",
                    "overall_status",
                    "quality_score",
                    "checks_json",
                    "details_json",
                    "completed_at",
                    "updated_at",
                ]
            )

        run.refresh_from_db()
        return run

    @staticmethod
    def apply_degraded_dq_status_if_circuit_open(
        asset, request=None, actor_user=None
    ) -> None:
        """
        If dq-service circuit is OPEN and the asset has a dataset, set
        ``dq_status`` to WARN and log ``DQ_SERVICE_UNAVAILABLE``.
        """
        from hub.apps.assets.models import Asset, DQStatus
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

        br = get_shared_circuit_breaker("dq-service")
        if br.get_state() != CircuitBreakerState.OPEN:
            return

        st = br.get_status()
        Asset.objects.filter(pk=asset.pk).update(dq_status=DQStatus.WARN)

        user = actor_user
        if user is None and request is not None:
            u = getattr(request, "user", None)
            if u is not None and getattr(u, "is_authenticated", False):
                user = u

        create_audit_event(
            resource_type="ASSET",
            action="DQ_SERVICE_UNAVAILABLE",
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

    @transaction.atomic
    def create_dq_run(
        self,
        tenant_id: str,
        user_id: str,
        asset_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        file_id: Optional[str] = None,
        profile_key: Optional[str] = None,
        tenant=None,
        user=None,
        asset=None,
        dataset=None,
        file_obj=None,
    ) -> DQRun:
        """
        Create a DQ run. Validates via DQBusinessRules before mutation.

        Args:
            tenant_id: Tenant UUID
            user_id: User UUID
            asset_id: Optional asset UUID
            dataset_id: Optional dataset UUID
            file_id: Optional file UUID
            profile_key: Optional profile key (default from tenant config)
            tenant: Optional tenant instance (if already resolved)
            user: Optional user instance (if already resolved)
            asset, dataset, file_obj: Optional resolved resource instances

        Returns:
            Created DQRun instance

        Raises:
            ValidationError: If DQBusinessRules reject
        """
        from hub.apps.tenants.models import Tenant
        from hub.apps.users.models import User
        from hub.apps.assets.models import Asset
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import File
        from hub.apps.jobs.models import JobType
        from hub.apps.jobs.utils import create_job, get_job_timeout
        from hub.apps.tenants.services import get_tenant_dq_profile

        # Plan limit enforcement (monthly)
        from hub.apps.tenants.services import PlanLimitService
        plan_limit_service = PlanLimitService(tenant_id=tenant_id)
        plan_limit_service.check_limit(
            tenant_id=tenant_id,
            limit_key="max_dq_runs_per_month",
            delta=1,
        )

        tenant = tenant or Tenant.objects.get(id=tenant_id)
        user = user or User.objects.get(id=user_id)

        if asset is None and asset_id:
            try:
                asset = Asset.objects.get(id=asset_id, tenant_id=tenant_id)
            except Asset.DoesNotExist:
                raise ValidationError(
                    "Asset not found",
                    code="BUSINESS_RULES_VALIDATION",
                    details={"asset_id": asset_id},
                )
        if dataset is None and dataset_id:
            try:
                dataset = Dataset.objects.get(id=dataset_id, tenant_id=tenant_id)
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
        if file_obj is None and file_id:
            try:
                file_obj = File.objects.get(id=file_id, tenant_id=tenant_id)
            except File.DoesNotExist:
                raise ValidationError(
                    "File not found",
                    code="BUSINESS_RULES_VALIDATION",
                    details={"file_id": file_id},
                )

        profile_key = profile_key or get_tenant_dq_profile(tenant_id)
        # Phase 240.3.A.8 — engine resolution lives in the
        # module-level helper so tests can pin the contract
        # without exercising the rest of create_dq_run.
        engine = resolve_engine_for_profile(profile_key)

        # Validate via DQBusinessRules before any mutation (unsaved payload)
        payload_run = DQRun(
            tenant_id=tenant_id,
            asset=asset,
            dataset=dataset,
            file=file_obj,
            profile_key=profile_key,
            engine=engine,
            status=DQRunStatus.PENDING,
        )
        rules = DQBusinessRules(tenant_id=tenant_id, user_id=user_id)
        result = rules.validate(
            dq_run=payload_run,
            tenant=tenant,
            user=user,
            validation_type="dq_run",
        )
        if not result.is_valid:
            raise ValidationError(
                "; ".join(result.errors),
                code="BUSINESS_RULES_VALIDATION",
                details=result.details,
            )

        # Create job and run (same as previous view logic)
        import uuid
        temp_resource_id = str(uuid.uuid4())
        job = create_job(
            tenant=tenant,
            user=user,
            job_type=JobType.DQ_RUN,
            resource_type="DQ_RUN",
            resource_id=temp_resource_id,
            details_json={},
            timeout_seconds=get_job_timeout(JobType.DQ_RUN),
        )
        dq_run = DQRun.objects.create(
            tenant=tenant,
            asset=asset,
            dataset=dataset,
            file=file_obj,
            job=job,
            profile_key=profile_key,
            engine=engine,
            status=DQRunStatus.PENDING,
        )
        job.resource_id = str(dq_run.id)
        job.details_json["dq_run_id"] = str(dq_run.id)
        job.save(update_fields=["resource_id", "details_json"])

        try:
            from hub.apps.jobs.tasks import process_job
            from hub.apps.jobs.utils import (
                get_queue,
                get_queue_for_job_type,
            )

            queue_name = get_queue_for_job_type(JobType.DQ_RUN)
            queue = get_queue(queue_name)
            _job_id = str(job.id)
            _queue = queue
            _timeout = get_job_timeout(JobType.DQ_RUN)
            transaction.on_commit(
                lambda: _queue.enqueue(
                    process_job,
                    _job_id,
                    job_type=JobType.DQ_RUN,
                    timeout=_timeout,
                )
            )
        except Exception as e:
            logger.warning(
                "Failed to enqueue DQ run job %s (run %s): %s. "
                "Ensure Redis and the RQ worker are running.",
                job.id,
                dq_run.id,
                e,
                exc_info=True,
            )

        return dq_run
