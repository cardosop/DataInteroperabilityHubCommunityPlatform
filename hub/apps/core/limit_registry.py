"""Resource counter registry for plan limit enforcement.

Phase 313.2 — moved from hub.apps.billing.limit_registry (pure module;
plan-limit resource counting is the commercial control plane, core-owned).
The paid billing app re-exports this module for compatibility.

Maps limit keys to model queries that count the current usage for a tenant.
Uses django.apps.get_model() for lazy imports to avoid circular dependencies.

Each entry defines:
- app_label.ModelName: Used with apps.get_model() at call time
- tenant_field: Django ORM lookup path to filter by tenant (supports FK traversal)
- timestamp_field: Field name for monthly date filtering (default: created_at)
- exclude_statuses: List of statuses to exclude (soft-deleted resources)
- monthly: Whether this is a monthly limit (filters by current month)
- sum_field: Field name for aggregate limits (e.g., storage bytes)
- extra_filter: Callable returning additional filter kwargs
"""

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from django.apps import apps
from django.conf import settings
from django.core.exceptions import FieldError
from django.db import OperationalError, ProgrammingError
from django.db.models import Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


class LimitCounterError(RuntimeError):
    """A resource counter failed to compute usage.

    R2-B6 (W2.7) — the counter registry previously swallowed every
    counting error into a silent 0 (fail-open quota: a broken counter
    reads as free usage).  ``get_resource_count`` raises this when
    ``LIMIT_CHECK_STRICT`` is armed so ``PlanLimitService.check_limit``
    fails CLOSED instead of approving against an untrusted 0.
    """


def _month_start() -> datetime:
    """Return the first instant of the current month (UTC)."""
    now = timezone.now()
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _day_start() -> datetime:
    """Return the first instant of the current day (UTC).

    Phase 240.3.B.2 — used by the ``daily=True`` window for
    ``max_quality_queries_per_day`` so the per-day cap resets at
    midnight UTC.
    """
    now = timezone.now()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


class ResourceCounter:
    """Describes how to count a resource for plan limit enforcement."""

    __slots__ = (
        "daily",
        "exclude_statuses",
        "extra_filter",
        "model_label",
        "monthly",
        "status_field",
        "sum_field",
        "tenant_field",
        "timestamp_field",
    )

    def __init__(
        self,
        model_label: str,
        *,
        tenant_field: str = "tenant_id",
        exclude_statuses: list | None = None,
        status_field: str = "status",
        monthly: bool = False,
        daily: bool = False,
        timestamp_field: str = "created_at",
        sum_field: str | None = None,
        extra_filter: Callable[[], dict[str, Any]] | None = None,
    ):
        self.model_label = model_label
        self.tenant_field = tenant_field
        self.exclude_statuses = exclude_statuses
        self.status_field = status_field
        self.monthly = monthly
        self.daily = daily
        self.timestamp_field = timestamp_field
        self.sum_field = sum_field
        self.extra_filter = extra_filter

    def get_count(self, tenant_id: str) -> int:
        """
        Query the current count/sum for a tenant.

        Returns an integer count or aggregate value.
        """
        Model = apps.get_model(self.model_label)
        qs = Model.objects.filter(**{self.tenant_field: tenant_id})

        # Exclude soft-deleted resources
        if self.exclude_statuses:
            qs = qs.exclude(**{f"{self.status_field}__in": self.exclude_statuses})

        # Monthly limits: filter to current month using timestamp_field
        if self.monthly:
            qs = qs.filter(**{f"{self.timestamp_field}__gte": _month_start()})

        # Phase 240.3.B.2 — daily limits: filter to current day (UTC).
        # Mutually exclusive with ``monthly`` in practice; if both are
        # set the QuerySet composes with AND so the narrower window
        # (daily) wins, but a counter SHOULD pick one window.
        if self.daily:
            qs = qs.filter(**{f"{self.timestamp_field}__gte": _day_start()})

        # Extra filter (e.g., only active files)
        if self.extra_filter:
            qs = qs.filter(**self.extra_filter())

        # Sum-based limits (e.g., storage)
        if self.sum_field:
            result = qs.aggregate(total=Sum(self.sum_field))
            return int(result["total"] or 0)

        return qs.count()


# ──────────────────────────────────────────────────────────────
# Registry: limit_key → ResourceCounter
#
# Only resources that already have models are registered here.
# Keys match TenantPlan.KNOWN_LIMIT_KEYS.
# ──────────────────────────────────────────────────────────────

RESOURCE_COUNTERS: dict[str, ResourceCounter] = {
    # ── Existing enforced limits (Phase 25) ──
    "max_assets": ResourceCounter(
        "assets.Asset",
        exclude_statuses=["RETIRED"],
    ),
    "max_datasets": ResourceCounter(
        "datasets.Dataset",
    ),
    "max_scheduled_ingestions": ResourceCounter(
        "scheduled_ingestion.ScheduledIngestion",
    ),
    "max_scheduled_exports": ResourceCounter(
        "scheduled_export.ScheduledExport",
    ),
    # ── Newly enforced limits (Phase 113) ──
    "max_contracts": ResourceCounter(
        "contracts.Contract",
        # Soft-deleted contracts (status RETIRED — delete_contract is a
        # soft delete) must not count against the quota, or the free-plan
        # max_contracts ratchets up forever across test/E2E runs.
        exclude_statuses=["RETIRED"],
    ),
    "max_webhooks": ResourceCounter(
        "webhooks.Webhook",
    ),
    "max_mesh_domains": ResourceCounter(
        "mesh.DataMeshDomain",
    ),
    "max_users": ResourceCounter(
        "users.UserTenantMembership",
    ),
    "max_marketplace_listings": ResourceCounter(
        "marketplace.Listing",
    ),
    "max_marketplace_connections": ResourceCounter(
        "integrations.MarketplaceConnection",
    ),
    "max_marketplace_orders_per_month": ResourceCounter(
        "marketplace.Order",
        monthly=True,
        exclude_statuses=["CANCELLED", "REJECTED"],
    ),
    "max_virtual_datasets": ResourceCounter(
        "virtualization.VirtualDataset",
    ),
    # ── Monthly limits ──
    # ScheduledIngestionRun has NO direct tenant FK;
    # reach tenant via scheduled_ingestion__tenant_id.
    "max_scheduled_runs_per_month": ResourceCounter(
        "scheduled_ingestion.ScheduledIngestionRun",
        monthly=True,
        tenant_field="scheduled_ingestion__tenant_id",
    ),
    "max_export_runs_per_month": ResourceCounter(
        "scheduled_export.ScheduledExportRun",
        monthly=True,
    ),
    # APIUsage has NO direct tenant FK; tenant_id is a @property.
    # Reach tenant via auth_api_key__tenant_id. Uses 'timestamp'
    # instead of 'created_at' for monthly filtering.
    "max_api_calls_per_month": ResourceCounter(
        "baas.APIUsage",
        monthly=True,
        tenant_field="auth_api_key__tenant_id",
        timestamp_field="timestamp",
    ),
    "max_compliance_runs_per_month": ResourceCounter(
        "compliance.ComplianceRun",
        monthly=True,
    ),
    "max_dq_runs_per_month": ResourceCounter(
        "dq.DQRun",
        monthly=True,
    ),
    "max_access_requests_per_month": ResourceCounter(
        "governance.AccessRequest",
        monthly=True,
    ),
    # ── Storage (aggregate, not count) ──
    # R2-B3 (W2.7) — PENDING-aware: an initialized-but-unfinished upload
    # (PENDING / UPLOADING) RESERVES its declared bytes, so two
    # concurrent 1GB uploads cannot both pass a 1GB plan (the pre-fix
    # ACTIVE-only filter let every in-flight upload stack quota for
    # free).  FAILED releases the reservation.  ``COMPLETED`` was
    # retired by files/0009 (migration rewrote it to ACTIVE) — dropped
    # from the filter so the meter and the gate cannot drift.
    "max_storage_gb": ResourceCounter(
        "files.File",
        sum_field="size",
        extra_filter=lambda: {
            "status__in": ["PENDING", "UPLOADING", "ACTIVE"],
        },
    ),
    # ── ML limits ──
    "max_ml_models": ResourceCounter(
        "ml.MLModel",
        exclude_statuses=["ARCHIVED"],
    ),
    "max_ml_training_jobs_per_month": ResourceCounter(
        "jobs.Job",
        monthly=True,
        extra_filter=lambda: {"type": "ML_TRAINING"},
    ),
    "max_ml_inference_requests_per_month": ResourceCounter(
        "ml.ModelInference",
        monthly=True,
        tenant_field="model__tenant_id",
        timestamp_field="timestamp",
    ),
    "max_ml_deployed_models": ResourceCounter(
        "ml.MLModel",
        exclude_statuses=["ARCHIVED"],
        extra_filter=lambda: {"status": "DEPLOYED"},
    ),
    # "max_ml_storage_gb" — removed: MLModel has no ``model_size_bytes``
    # field.  Storage counting for ML models requires a dedicated size
    # column (e.g. odh_model_size_bytes) to be added to ml.MLModel first.
    # See Phase 114A.5 for the original intent.
    # ── Transformation limits (Phase 115A) ──
    "max_transformation_pipelines": ResourceCounter(
        "transformation.TransformationPipeline",
        exclude_statuses=["ARCHIVED"],
    ),
    "max_transformation_runs_per_month": ResourceCounter(
        "transformation.PipelineExecution",
        tenant_field="pipeline__tenant_id",
        monthly=True,
    ),
    # ── ODPS limits (Phase 117A) ──
    "max_odps_documents": ResourceCounter(
        "contracts.Contract",
        extra_filter=lambda: {"original_spec_type": "ODPS"},
    ),
    # ── Phase 3.4 (add-databricks-sql-warehouses) — the warehouse
    # creation chain's quota counter. The mirror is tenant-scoped through
    # the workspace (FK traversal); DELETING rows are on their way out
    # and never block a create.
    "max_databricks_warehouses": ResourceCounter(
        "databricks_admin.DatabricksSqlWarehouse",
        tenant_field="workspace__tenant_id",
        exclude_statuses=["DELETING"],
        status_field="state",
    ),
    # ── Phase 240.3.B.2 — Advanced quality endpoints day-rate cap ──
    # Counts AuditEvent rows scoped to the DQ_QUALITY_QUERY action
    # emitted by ``DQQualityViewSet`` on each successful endpoint hit.
    # Daily window resets at midnight UTC (``_day_start()``).  Filter
    # by ``action="DQ_QUALITY_QUERY"`` via ``extra_filter`` so we don't
    # need a dedicated table — the audit trail IS the source of truth.
    "max_quality_queries_per_day": ResourceCounter(
        "audit.AuditEvent",
        daily=True,
        timestamp_field="timestamp",
        extra_filter=lambda: {"action": "DQ_QUALITY_QUERY"},
    ),
}


def _emit_counter_error_audit(tenant_id: str, limit_key: str, error: Exception) -> None:
    """R2-B6 — every counter failure is audited (never a silent 0).

    Best-effort: an audit-DB outage must not compound the counter
    failure (the LIMIT_CHECK_STRICT raise below is the fail-closed
    signal; this event is the forensic trail).
    """
    try:
        from hub.apps.audit.utils import create_audit_event
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.filter(pk=tenant_id).first()
        create_audit_event(
            resource_type="PLAN_LIMIT",
            action="LIMIT_COUNTER_ERROR",
            actor_user=None,
            tenant=tenant,
            resource_id=tenant_id,
            result="FAILURE",
            details={
                "limit_key": limit_key,
                "error_type": type(error).__name__,
                "error": str(error)[:256],
                "strict": bool(getattr(settings, "LIMIT_CHECK_STRICT", False)),
            },
        )
    except Exception as audit_error:  # noqa: BLE001 — audit must never compound the counter failure
        logger.warning(
            "limit_counter_error_audit_failed",
            extra={"error": str(audit_error)},
            exc_info=True,
        )


def get_resource_count(tenant_id: str, limit_key: str) -> int:
    """
    Get the current usage count for a limit key.

    Returns the count from the registry, or 0 if the limit_key
    is not registered (e.g., for limits not yet backed by a model).

    R2-B6 — counter ERRORS are audited (``LIMIT_COUNTER_ERROR``) and,
    when ``LIMIT_CHECK_STRICT`` is armed, RAISE ``LimitCounterError``
    so a limit check fails closed instead of approving against an
    untrusted 0.
    """
    counter = RESOURCE_COUNTERS.get(limit_key)
    if counter is None:
        logger.debug(
            "No resource counter registered for limit_key=%s",
            limit_key,
        )
        return 0

    try:
        return counter.get_count(tenant_id)
    except (FieldError, OperationalError, ProgrammingError) as error:
        # Schema drift (FieldError — renamed/deleted column), DB outage
        # (OperationalError), or bad SQL (ProgrammingError).
        logger.warning(
            "Failed to count resource for limit_key=%s, tenant_id=%s",
            limit_key,
            tenant_id,
            exc_info=True,
        )
        _emit_counter_error_audit(tenant_id, limit_key, error)
        if getattr(settings, "LIMIT_CHECK_STRICT", False):
            raise LimitCounterError(
                f"Resource counter failed for {limit_key}: {error}"
            ) from error
        # Non-strict: the pre-existing fail-open fallback (0) so the
        # usage endpoint still renders — but the failure is now audited.
        return 0
