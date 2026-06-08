"""
Phase 260.4.G — file-storage quota helper.

Pure read-side computation:

  * ``used_bytes``  — sum of ``size`` over the tenant's File rows that
    are currently consuming storage (``status = ACTIVE``; Phase
    260.6.A retired the legacy ``COMPLETED`` value via migration
    ``0009_drop_completed_file_status``).
    Mirrors the aggregation used by ``billing.limit_registry`` for
    ``max_storage_gb`` so the meter and the plan-limit gate report
    identical numbers.
  * ``limit_bytes`` — the tenant plan's ``max_storage_gb`` converted
    to bytes.  ``None`` when the plan declares unlimited storage
    (typically ENTERPRISE) so the FE can render an "unlimited" pill
    rather than a 0% bar.
  * ``percentage`` — float in [0, 100] when ``limit_bytes`` is set;
    ``None`` when unlimited.  Capped at 100 even when the row sum
    exceeds the cap (over-quota is reported as 100% with the raw
    bytes preserved in ``used_bytes`` so the FE banner can still
    surface the overage).

Pure function, no audit emission, no side effects — composable into
the FE meter endpoint AND any future quota dashboards / cron-style
enforcement scripts without re-implementing the aggregation.
"""
from __future__ import annotations
from typing import Optional, TypedDict

from django.db.models import Sum

from hub.apps.files.models import File, FileStatus
from hub.apps.tenants.models import Tenant, TenantPlan


class QuotaPlanResolutionError(RuntimeError):
    """Raised when a tenant has no plan AND no FREE plan exists.

    This is a platform-misconfiguration signal — under normal
    operation the FREE plan is seeded via
    ``manage.py seed_default_plans`` at deploy time. The endpoint
    surfaces this as 503 with a clear ``QUOTA_PLAN_NOT_RESOLVED``
    code so operators can see the platform-level fix needed
    (re-run the seed) rather than the meter falsely showing
    "unlimited" and the limit-gate then 5xx-ing on the next
    upload.
    """


class FileStorageQuota(TypedDict):
    used_bytes: int
    limit_bytes: Optional[int]
    percentage: Optional[float]
    plan_slug: Optional[str]
    plan_tier: Optional[str]
    unlimited: bool


def _tenant_file_storage_used_bytes(tenant_id: str) -> int:
    """Sum of ``File.size`` for the tenant's storage-consuming rows.

    Filter set matches ``billing.limit_registry["max_storage_gb"]`` so
    the meter and the limit-gate cannot disagree on what counts.
    """
    aggregate = (
        File.objects.filter(
            tenant_id=tenant_id,
            status=FileStatus.ACTIVE,
        )
        .aggregate(total=Sum("size"))
    )
    return int(aggregate.get("total") or 0)


def _resolve_tenant_plan(tenant: Tenant) -> Optional[TenantPlan]:
    """Tenant plan resolution with FREE-plan fallback (matches
    ``PlanLimitService._check`` semantics so the meter shows the
    same plan name the limit gate would enforce against).
    """
    if tenant.plan:
        return tenant.plan
    return TenantPlan.objects.filter(slug="free", is_active=True).first()


def get_tenant_file_storage_quota(tenant_id: str) -> FileStorageQuota:
    """Return the tenant's file-storage quota snapshot.

    Raises ``Tenant.DoesNotExist`` for unknown tenants — callers
    surface the 404 themselves; this helper does not encode HTTP
    semantics so it stays composable with non-HTTP callers.

    Raises :class:`QuotaPlanResolutionError` when the tenant has no
    plan AND no FREE plan exists in the database (platform
    misconfiguration). R1 audit GAP-A: returning a falsey
    ``unlimited=True`` here would lie to the user — the limit gate
    would then 5xx on their next upload because
    ``PlanLimitService._check`` ALSO requires the FREE plan to
    exist. Failing loud at the meter layer makes the
    misconfiguration visible to operators rather than silently
    misleading the user.
    """
    tenant = Tenant.objects.get(id=tenant_id)
    plan = _resolve_tenant_plan(tenant)

    if plan is None:
        # Misconfigured platform — no tenant plan AND no FREE
        # fallback. Match the limit-gate's loud-failure semantics
        # (``PlanLimitService._check`` raises ``NotFoundError``
        # here) instead of silently lying about unlimited storage.
        raise QuotaPlanResolutionError(
            "No tenant plan resolved and no FREE plan exists. "
            "Run: manage.py seed_default_plans"
        )

    used_bytes = _tenant_file_storage_used_bytes(tenant_id)

    limit_gb: Optional[float] = plan.get_limit("max_storage_gb")

    if limit_gb is None:
        return FileStorageQuota(
            used_bytes=used_bytes,
            limit_bytes=None,
            percentage=None,
            plan_slug=plan.slug,
            plan_tier=plan.tier,
            unlimited=True,
        )

    # Convert plan limit (GB) → bytes for an apples-to-apples wire
    # shape with ``used_bytes``.  The bytes form is what the FE
    # meter renders against; converting once on the server side
    # avoids the client having to know the GB-to-bytes constant.
    limit_bytes = int(float(limit_gb) * (1024 ** 3))

    if limit_bytes <= 0:
        # Defensive — a plan with ``max_storage_gb=0`` would divide-
        # by-zero. Treat as 100% used IF there's any usage, else 0%.
        percentage: float = 100.0 if used_bytes > 0 else 0.0
    else:
        # Cap at 100 so over-quota reports as a saturated bar; the
        # raw ``used_bytes`` preserves the absolute overage for the
        # FE banner copy.
        raw = (used_bytes / limit_bytes) * 100.0
        percentage = min(round(raw, 2), 100.0)

    return FileStorageQuota(
        used_bytes=used_bytes,
        limit_bytes=limit_bytes,
        percentage=percentage,
        plan_slug=plan.slug,
        plan_tier=plan.tier,
        unlimited=False,
    )
