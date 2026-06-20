"""
285.11.3.1 + 285.11.3.2 — PipelineTriggerEngine.

Unified post_save signal handler that listens for terminal pipeline
execution completions (SUCCEEDED/COMPLETED/FAILED/CANCELLED) across
all five pipeline types and auto-triggers downstream pipelines when
dependency_type=TRIGGER and all upstream deps are met.

Replaces the hardcoded transformation/signals.py trigger with a
general, priority-ordered, dependency-aware execution cascade.

For >10 downstream pipelines, batches into background
``Job(JobType.DEPENDENCY_TRIGGER_BATCH)``.
"""

from __future__ import annotations

import logging

from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from hub.apps.tenants.request_tenant import tenant_context

from .dependency_executor import DependencyAwareExecutor
from .dependency_resolver import PipelineDependencyResolver
from .models import DependencyType, PipelineType

logger = logging.getLogger(__name__)

# ── Helpers ────────────────────────────────────────────────────────────


def _is_trigger_engine_enabled(tenant_id: str) -> bool:
    """Check whether the pipeline_dependency_enabled flag is on.
    Fail-safe: returns False on any error (don't block saves).
    """
    try:
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.only("pipeline_dependency_enabled").get(id=tenant_id)
        return bool(tenant.pipeline_dependency_enabled)
    except Exception:
        return False


# ── Constants ──────────────────────────────────────────────────────────

_BATCH_THRESHOLD = 10  # trigger >10 downstream → async batch job

_TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        "SUCCEEDED",
        "COMPLETED",
        "SUCCESS",
        "FAILED",
        "CANCELLED",
    }
)

# 285.11.3.1 — mapping from model → pipeline_type for signal dispatch.
_PIPELINE_DISPATCH = {
    "transformation.PipelineExecution": PipelineType.TRANSFORMATION,
    "scheduled_ingestion.ScheduledIngestionRun": PipelineType.SCHEDULED_INGESTION,
    "scheduled_export.ScheduledExportRun": PipelineType.SCHEDULED_EXPORT,
    "dq.DQRun": PipelineType.DQ,
    "compliance.ComplianceRun": PipelineType.COMPLIANCE,
}


# ── Signal registration ────────────────────────────────────────────────


def register_signals():
    """Register post_save handlers for all 5 pipeline execution models.

    Called from ``orchestration/apps.py`` ``ready()`` so that signal
    registration happens exactly once at Django startup.
    """
    for model_label in _PIPELINE_DISPATCH:
        _connect_signal(model_label)


def _connect_signal(model_label: str):
    """Connect a single model's post_save signal."""
    try:
        # Use lazy string reference to avoid import-time model loading.
        receiver(post_save, sender=model_label)(
            _handle_pipeline_execution_completed,
        )
    except Exception:
        logger.debug(
            "trigger_engine_signal_connect_skipped",
            model_label=model_label,
        )


# ── Core handler ────────────────────────────────────────────────────────


def _handle_pipeline_execution_completed(
    sender,
    instance,
    created: bool,
    raw: bool,
    **kwargs,
):
    """Post-save handler for all pipeline execution models.

    Fires ONLY on updates (not creates) to avoid loops: a pipeline
    being set to PENDING_DEPENDENCY by the trigger engine itself
    should not trigger another cascade.

    The ``raw`` guard skips fixtures / data migrations — those loads
    should not fire business-logic triggers.
    """
    # Guard: skip creates, raw data loads, and non-terminal statuses.
    if created or raw:
        return

    status = getattr(instance, "status", None)
    if status is None or str(status).upper() not in _TERMINAL_STATUSES:
        return

    tenant_id = str(instance.tenant_id) if getattr(instance, "tenant_id", None) else None
    if not tenant_id:
        return

    instance_id = str(getattr(instance, "id", ""))
    if not instance_id:
        return

    # Find the pipeline type for this model.
    model_label = f"{instance._meta.app_label}.{instance._meta.model_name}"
    pipeline_type = _PIPELINE_DISPATCH.get(model_label)
    if pipeline_type is None:
        return

    # Gate on the feature flag — skip work when disabled.
    if not _is_trigger_engine_enabled(tenant_id):
        return

    # Defer to transaction.on_commit so we never fire for a
    # rolled-back save.
    transaction.on_commit(
        lambda: _on_pipeline_terminal(
            tenant_id,
            pipeline_type,
            instance_id,
            str(status),
        )
    )


def _on_pipeline_terminal(
    tenant_id: str,
    pipeline_type: str,
    pipeline_id: str,
    status: str,
):
    """Inside transaction.on_commit: resolve downstream TRIGGER
    dependencies and enqueue the ones whose deps are all met.
    """
    try:
        with tenant_context(tenant_id):
            _trigger_downstream_cascade(tenant_id, pipeline_type, pipeline_id, status)
    except Exception as exc:
        logger.warning(
            "trigger_engine_cascade_failed",
            extra={
                "tenant_id": tenant_id,
                "pipeline_type": pipeline_type,
                "pipeline_id": pipeline_id,
                "status": status,
                "error": str(exc),
            },
        )


def _trigger_downstream_cascade(
    tenant_id: str,
    pipeline_type: str,
    pipeline_id: str,
    status: str,
):
    """Resolve downstream TRIGGER dependencies and enqueue them.

    Steps:
    1. If status is FAILED/CANCELLED → propagate failure.
    2. If status is SUCCEEDED/COMPLETED → find TRIGGER-type deps
       where all upstream deps are met → enqueue each downstream.
    3. For >10 downstream, batch into DEPENDENCY_TRIGGER_BATCH job.
    """
    resolver = PipelineDependencyResolver(tenant_id)

    if status.upper() in ("FAILED", "CANCELLED"):
        executor = DependencyAwareExecutor(tenant_id)
        executor.propagate_upstream_failure(
            pipeline_type,
            pipeline_id,
            pipeline_id,
        )
        return

    # Find TRIGGER-type downstream dependencies.
    downstream = [
        d
        for d in resolver.resolve_downstream(pipeline_type, pipeline_id)
        if d.dependency_type == DependencyType.TRIGGER
    ]
    if not downstream:
        return

    # Sort by priority DESC (highest priority runs first).
    downstream.sort(key=lambda d: d.priority, reverse=True)

    # Resolve upstream statuses for the downstream pipelines.
    # For each downstream, check if ALL its upstream deps are met.
    ready_to_trigger: list = []
    for dep in downstream:
        upstream_deps = resolver.resolve_upstream(
            dep.downstream_pipeline_type,
            str(dep.downstream_pipeline_id),
        )
        # Check if all upstream deps are satisfied.
        all_met = all(_is_upstream_terminal_success(resolver, u) for u in upstream_deps)
        if all_met:
            ready_to_trigger.append(dep)

    if not ready_to_trigger:
        return

    logger.info(
        "trigger_engine_cascade",
        tenant_id=tenant_id,
        pipeline_type=pipeline_type,
        pipeline_id=pipeline_id,
        status=status,
        downstream_count=len(ready_to_trigger),
    )

    count = len(ready_to_trigger)
    if count > _BATCH_THRESHOLD:
        _enqueue_batch_trigger(
            tenant_id,
            pipeline_type,
            pipeline_id,
            ready_to_trigger,
        )
    else:
        for dep in ready_to_trigger:
            _trigger_single(dep, tenant_id)


def _is_upstream_terminal_success(
    resolver: PipelineDependencyResolver,
    dep,
) -> bool:
    """Check if a single upstream dependency's pipeline execution
    has reached a terminal success status.

    Queries the actual pipeline execution model (not the
    PipelineRunDependency table, which is only populated AFTER a
    trigger fires — creating a chicken-and-egg problem).
    """
    tenant_id = resolver.tenant_id
    ptype = dep.pipeline_type
    pid = str(dep.pipeline_id)

    status = _get_pipeline_execution_status(tenant_id, ptype, pid)
    if status is None:
        return False
    return status.upper() in ("SUCCEEDED", "COMPLETED", "SUCCESS")


def _get_pipeline_execution_status(
    tenant_id: str,
    pipeline_type: str,
    pipeline_id: str,
) -> str | None:
    """Query the actual pipeline execution model for its current status.

    Dispatches to the correct model based on pipeline_type.
    Returns None if the pipeline execution row doesn't exist.
    """
    try:
        if pipeline_type == PipelineType.TRANSFORMATION:
            from hub.apps.transformation.models import PipelineExecution

            obj = (
                PipelineExecution.objects.filter(
                    id=pipeline_id,
                    tenant_id=tenant_id,
                )
                .only("status")
                .first()
            )
        elif pipeline_type == PipelineType.SCHEDULED_INGESTION:
            from hub.apps.scheduled_ingestion.models import ScheduledIngestionRun

            obj = (
                ScheduledIngestionRun.objects.filter(
                    id=pipeline_id,
                    tenant_id=tenant_id,
                )
                .only("status")
                .first()
            )
        elif pipeline_type == PipelineType.SCHEDULED_EXPORT:
            from hub.apps.scheduled_export.models import ScheduledExportRun

            obj = (
                ScheduledExportRun.objects.filter(
                    id=pipeline_id,
                    tenant_id=tenant_id,
                )
                .only("status")
                .first()
            )
        elif pipeline_type == PipelineType.DQ:
            from hub.apps.dq.models import DQRun

            obj = (
                DQRun.objects.filter(
                    id=pipeline_id,
                    tenant_id=tenant_id,
                )
                .only("status")
                .first()
            )
        elif pipeline_type == PipelineType.COMPLIANCE:
            from hub.apps.compliance.models import ComplianceRun

            obj = (
                ComplianceRun.objects.filter(
                    id=pipeline_id,
                    tenant_id=tenant_id,
                )
                .only("status")
                .first()
            )
        else:
            return None
        return str(obj.status) if obj else None
    except Exception:
        return None


def _trigger_single(dep, tenant_id: str):
    """Enqueue a single downstream pipeline trigger."""
    try:
        from hub.apps.core.events.publisher import EventPublisher

        publisher = EventPublisher(
            service_name="orchestration_trigger",
            tenant_id=tenant_id,
        )
        publisher.publish(
            event_type="orchestration.pipeline.triggered",
            data={
                "pipeline_type": dep.downstream_pipeline_type,
                "pipeline_id": str(dep.downstream_pipeline_id),
                "upstream_type": dep.pipeline_type,
                "upstream_id": str(dep.pipeline_id),
                "dependency_type": dep.dependency_type,
                "priority": dep.priority,
            },
            tags=["orchestration", "trigger", "pipeline"],
            tenant_id=tenant_id,
        )
        logger.info(
            "trigger_engine_single_triggered",
            downstream_type=dep.downstream_pipeline_type,
            downstream_id=str(dep.downstream_pipeline_id),
            upstream_type=dep.pipeline_type,
            upstream_id=str(dep.pipeline_id),
            priority=dep.priority,
        )
    except Exception as exc:
        logger.warning(
            "trigger_engine_single_failed",
            dep_id=str(dep.id),
            error=str(exc),
        )


def _enqueue_batch_trigger(
    tenant_id: str,
    upstream_type: str,
    upstream_id: str,
    downstream_list: list,
):
    """285.11.3.2 — Batch enqueue >10 downstream triggers."""
    try:
        from hub.apps.jobs.models import JobType
        from hub.apps.jobs.utils import create_job
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.filter(id=tenant_id).first()
        if tenant is None:
            return

        batch = [
            {
                "pipeline_type": d.downstream_pipeline_type,
                "pipeline_id": str(d.downstream_pipeline_id),
                "priority": d.priority,
            }
            for d in downstream_list
        ]

        # Split into sub-batches of _MAX_BATCH_SIZE.
        _MAX_BATCH_SIZE = 100
        for i in range(0, len(batch), _MAX_BATCH_SIZE):
            sub_batch = batch[i : i + _MAX_BATCH_SIZE]
            create_job(
                tenant=tenant,
                job_type=JobType.DEPENDENCY_TRIGGER_BATCH,
                resource_type="PIPELINE_DEPENDENCY",
                resource_id=upstream_id,
                details_json={
                    "upstream_type": upstream_type,
                    "upstream_id": upstream_id,
                    "downstream_pipelines": sub_batch,
                },
            )

        logger.info(
            "trigger_engine_batch_enqueued",
            tenant_id=tenant_id,
            batch_count=len(batch),
            sub_batches=(len(batch) + _MAX_BATCH_SIZE - 1) // _MAX_BATCH_SIZE,
        )
    except Exception as exc:
        logger.error(
            "trigger_engine_batch_failed",
            tenant_id=tenant_id,
            upstream_type=upstream_type,
            upstream_id=upstream_id,
            error=str(exc),
        )
