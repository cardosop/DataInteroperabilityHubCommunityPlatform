"""
285.11.2.2 + 285.11.2.3 + 285.11.2.5 — DependencyAwareExecutor.

Wraps each pipeline service's enqueue method with:
  1. Pre-flight dependency check via ``PipelineDependencyResolver``.
  2. Post-execution downstream trigger on upstream SUCCEEDED.
  3. Failure propagation: when an upstream run FAILED, all
     downstream runs are set to ``SKIPPED_UPSTREAM_FAILED``.

Feature-gated on ``pipeline_dependency_enabled`` — when the flag
is off, pipelines execute as they do today (pass-through).
"""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from django.utils import timezone

from hub.apps.jobs.models import JobType
from hub.apps.jobs.utils import create_job

from .dependency_resolver import PipelineDependencyResolver
from .models import (
    PipelineDependency,
    PipelineRunDependency,
    PipelineType,
)

logger = structlog.get_logger(__name__)

# 285.11.2.4 — max downstream batch size per trigger job
_MAX_BATCH_SIZE = 100


class DependencyAwareExecutor:
    """Pre/post execution guard for pipeline dependency enforcement.

    Usage::

        executor = DependencyAwareExecutor(tenant_id)
        result = executor.enqueue_with_dependency_check(
            pipeline_type="transformation",
            pipeline_id=str(execution_id),
            enqueue_fn=lambda: transformation_service.enqueue(...),
            resolve_upstream_statuses=upstream_statuses,
        )
    """

    def __init__(self, tenant_id: str):
        self.tenant_id = str(tenant_id)
        self._resolver = PipelineDependencyResolver(self.tenant_id)

    # ── 285.11.2.2 — Pre-flight dependency check ────────────────────

    def enqueue_with_dependency_check(
        self,
        pipeline_type: str,
        pipeline_id: str,
        enqueue_fn,
        resolve_upstream_statuses: dict = None,
    ) -> dict[str, Any]:
        """Gate pipeline execution on dependency satisfaction.

        Returns one of:
          - Normal enqueue result (dict) when all deps are met.
          - ``{status: "PENDING_DEPENDENCY", waiting_on: [...]}``
            when upstream deps are not yet satisfied.
        """
        # Feature-flag gate — pass-through when disabled.
        if not self._is_flag_enabled():
            return enqueue_fn()

        upstream_statuses = resolve_upstream_statuses or {}
        # Convert statuses dict to resolver format.
        typed_statuses = {
            (str(s.get("type", "")), str(s.get("id", ""))): str(s.get("status", ""))
            for s in (
                upstream_statuses.values()
                if isinstance(upstream_statuses, dict)
                else upstream_statuses
            )
        }

        if self._resolver.are_dependencies_met(
            pipeline_type,
            pipeline_id,
            typed_statuses,
        ):
            return enqueue_fn()

        # Not all deps are met → set PENDING_DEPENDENCY.
        waiting_on = self._resolver.resolve_upstream(pipeline_type, pipeline_id)
        self._set_run_status(
            pipeline_type,
            pipeline_id,
            "PENDING_DEPENDENCY",
        )

        waiting_list = [
            {
                "pipeline_type": d.pipeline_type,
                "pipeline_id": str(d.pipeline_id),
                "dependency_type": d.dependency_type,
            }
            for d in waiting_on
        ]
        logger.info(
            "pipeline_pending_dependency",
            pipeline_type=pipeline_type,
            pipeline_id=pipeline_id,
            waiting_on_count=len(waiting_list),
        )
        return {
            "status": "PENDING_DEPENDENCY",
            "waiting_on": waiting_list,
        }

    # ── 285.11.2.3 — Failure propagation ────────────────────────────

    def propagate_upstream_failure(
        self,
        upstream_type: str,
        upstream_id: str,
        upstream_run_id: str,
    ) -> int:
        """When an upstream pipeline FAILED, mark all downstream
        runs ``SKIPPED_UPSTREAM_FAILED``.

        For >10 downstream, batch into a ``DEPENDENCY_TRIGGER_BATCH``
        Job instead of processing synchronously.

        Returns the count of downstream pipelines affected.
        """
        if not self._is_flag_enabled():
            return 0

        downstream = self._resolver.resolve_downstream(upstream_type, upstream_id)
        if not downstream:
            return 0

        count = len(downstream)
        if count > 10:
            # Batch into async job.
            self._enqueue_batch_propagation(
                upstream_type,
                upstream_id,
                upstream_run_id,
                [
                    {
                        "pipeline_type": d.downstream_pipeline_type,
                        "pipeline_id": str(d.downstream_pipeline_id),
                    }
                    for d in downstream
                ],
            )
        else:
            # Synchronous — immediate status update.
            for dep in downstream:
                self._set_run_status(
                    dep.downstream_pipeline_type,
                    str(dep.downstream_pipeline_id),
                    "SKIPPED_UPSTREAM_FAILED",
                )

        logger.warning(
            "upstream_failure_propagated",
            upstream_type=upstream_type,
            upstream_id=upstream_id,
            upstream_run_id=upstream_run_id,
            downstream_count=count,
            batched=count > 10,
        )
        return count

    # ── 285.11.2.5 — Post-execution downstream trigger ──────────────

    def trigger_downstream(
        self,
        pipeline_type: str,
        pipeline_id: str,
        run_id: str,
        upstream_status: str,
    ) -> int:
        """After a successful upstream execution, trigger downstream
        pipelines that were waiting on this upstream.

        Only fires when *upstream_status* is a terminal success.
        Returns the number of downstream pipelines triggered.
        """
        if not self._is_flag_enabled():
            return 0

        if upstream_status.upper() not in ("SUCCEEDED", "COMPLETED", "SUCCESS"):
            return 0

        downstream = self._resolver.resolve_downstream(pipeline_type, pipeline_id)
        triggered = 0
        for dep in downstream:
            self._trigger_single_downstream(dep, run_id)
            triggered += 1
        return triggered

    # ── Internal helpers ────────────────────────────────────────────

    def _get_tenant(self):
        """Return the Tenant instance (cached per executor instance)."""
        if not hasattr(self, "_tenant"):
            try:
                from hub.apps.tenants.models import Tenant

                self._tenant = Tenant.objects.get(id=self.tenant_id)
            except Exception:
                self._tenant = None
        return self._tenant

    def _is_flag_enabled(self) -> bool:
        """Check the per-tenant pipeline_dependency_enabled flag."""
        tenant = self._get_tenant()
        if tenant is None:
            return False
        return bool(getattr(tenant, "pipeline_dependency_enabled", False))

    def _set_run_status(
        self,
        pipeline_type: str,
        pipeline_id: str,
        status: str,
    ) -> None:
        """Set the given pipeline run's status.  Dispatches to
        the correct model based on pipeline_type.
        """
        try:
            if pipeline_type == PipelineType.TRANSFORMATION:
                from hub.apps.transformation.models import (
                    PipelineExecution,
                )

                PipelineExecution.objects.filter(id=pipeline_id).update(
                    status=status,
                    updated_at=timezone.now(),
                )
            elif pipeline_type == PipelineType.SCHEDULED_INGESTION:
                from hub.apps.scheduled_ingestion.models import (
                    ScheduledIngestionRun,
                )

                ScheduledIngestionRun.objects.filter(id=pipeline_id).update(
                    status=status,
                )
            elif pipeline_type == PipelineType.SCHEDULED_EXPORT:
                from hub.apps.scheduled_export.models import (
                    ScheduledExportRun,
                )

                ScheduledExportRun.objects.filter(id=pipeline_id).update(
                    status=status,
                )
        except Exception as exc:
            logger.error(
                "dependency_set_run_status_failed",
                pipeline_type=pipeline_type,
                pipeline_id=pipeline_id,
                status=status,
                error=str(exc),
            )

    def _trigger_single_downstream(
        self,
        dep: PipelineDependency,
        upstream_run_id: str,
    ) -> None:
        """Record that a downstream pipeline's upstream dependency
        has resolved successfully.  Creates a PipelineRunDependency
        tracking row for audit and observability.

        Does NOT modify the downstream run's status — that is the
        responsibility of the downstream pipeline's own enqueue
        path, which will re-check dependencies and proceed.
        """
        try:
            PipelineRunDependency.objects.create(
                tenant_id=self.tenant_id,
                pipeline_dependency=dep,
                upstream_run_type=dep.pipeline_type,
                upstream_run_id=upstream_run_id,
                downstream_run_type=dep.downstream_pipeline_type,
                downstream_run_id=dep.downstream_pipeline_id,
                upstream_status="SUCCEEDED",
            )
        except Exception as exc:
            logger.error(
                "dependency_downstream_trigger_failed",
                dep_id=str(dep.id),
                error=str(exc),
            )

    def _enqueue_batch_propagation(
        self,
        upstream_type: str,
        upstream_id: str,
        upstream_run_id: str,
        downstream_pipelines: list[dict[str, str]],
    ) -> None:
        """Enqueue a DEPENDENCY_TRIGGER_BATCH job for async processing."""
        try:
            tenant = self._get_tenant()
            if tenant is None:
                return
            # Process in batches of _MAX_BATCH_SIZE.
            for i in range(0, len(downstream_pipelines), _MAX_BATCH_SIZE):
                batch = downstream_pipelines[i : i + _MAX_BATCH_SIZE]
                create_job(
                    tenant=tenant,
                    job_type=JobType.DEPENDENCY_TRIGGER_BATCH,
                    resource_type="PIPELINE_DEPENDENCY",
                    resource_id=upstream_id or str(uuid.uuid4()),
                    details_json={
                        "upstream_type": upstream_type,
                        "upstream_id": upstream_id,
                        "upstream_run_id": upstream_run_id,
                        "downstream_pipelines": batch,
                    },
                )
        except Exception as exc:
            logger.error(
                "dependency_batch_propagation_enqueue_failed",
                upstream_type=upstream_type,
                upstream_id=upstream_id,
                error=str(exc),
            )


def handle_upstream_completed(
    tenant_id: str,
    pipeline_type: str,
    pipeline_id: str,
    run_id: str,
    status: str,
) -> int:
    """Convenience function for post_save signal handlers.
    Call from pipeline execution model signals.

    Returns the number of downstream pipelines triggered.
    """
    executor = DependencyAwareExecutor(tenant_id)
    if status.upper() in ("FAILED", "CANCELLED"):
        return executor.propagate_upstream_failure(
            pipeline_type,
            pipeline_id,
            run_id,
        )
    return executor.trigger_downstream(
        pipeline_type,
        pipeline_id,
        run_id,
        status,
    )
