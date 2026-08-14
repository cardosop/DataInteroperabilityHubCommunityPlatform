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
from django.core.exceptions import FieldError
from django.db import OperationalError, ProgrammingError
from django.db.models import Sum
from django.utils import timezone

logger = logging.getLogger(__name__)


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
    "max_storage_gb": ResourceCounter(
        "files.File",
        sum_field="size",
        extra_filter=lambda: {"status__in": ["ACTIVE", "COMPLETED"]},
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


def get_resource_count(tenant_id: str, limit_key: str) -> int:
    """
    Get the current usage count for a limit key.

    Returns the count from the registry, or 0 if the limit_key
    is not registered (e.g., for limits not yet backed by a model).
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
    except (FieldError, OperationalError, ProgrammingError):
        # Schema drift (FieldError — renamed/deleted column), DB outage
        # (OperationalError), or bad SQL (ProgrammingError).  All are
        # non-fatal for the usage endpoint — the counter returns 0 so
        # the rest of the response still renders.
        logger.warning(
            "Failed to count resource for limit_key=%s, tenant_id=%s",
            limit_key,
            tenant_id,
            exc_info=True,
        )
        return 0
