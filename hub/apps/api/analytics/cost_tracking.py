"""
Cost Tracking Service (UC-TA-007)

Converts tenant usage metrics to cost estimates for tenant admins.
Uses TenantUsageSummary, IngestionCost, and configurable rates.
"""

from decimal import Decimal
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from hub.apps.tenants.models import Tenant, TenantUsageSummary
from hub.apps.tenants.services import TenantUsageService


# Default cost rates (configurable via COST_RATES in settings)
DEFAULT_STORAGE_COST_PER_GB_MONTH = Decimal("0.023")
DEFAULT_API_COST_PER_1000 = Decimal("0.001")
DEFAULT_ASSET_COST_PER_MONTH = Decimal("0.00")  # Included in plan
DEFAULT_DATASET_COST_PER_MONTH = Decimal("0.00")  # Included in plan


def _get_cost_rates() -> Dict[str, Decimal]:
    """Get cost rates from settings with defaults."""
    rates = getattr(settings, "COST_RATES", {})
    return {
        "storage_per_gb_month": Decimal(
            str(rates.get("storage_per_gb_month", DEFAULT_STORAGE_COST_PER_GB_MONTH))
        ),
        "api_per_1000": Decimal(str(rates.get("api_per_1000", DEFAULT_API_COST_PER_1000))),
        "asset_per_month": Decimal(str(rates.get("asset_per_month", DEFAULT_ASSET_COST_PER_MONTH))),
        "dataset_per_month": Decimal(
            str(rates.get("dataset_per_month", DEFAULT_DATASET_COST_PER_MONTH))
        ),
    }


class CostTrackingService:
    """
    Service for computing tenant cost from usage (UC-TA-007).
    """

    @staticmethod
    def get_cost_summary(
        tenant_id: str,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get cost summary for tenant: total_cost and breakdown by category.

        Args:
            tenant_id: Tenant UUID
            period_start: Start of period (default: start of current month)
            period_end: End of period (default: end of current month)

        Returns:
            Dict with total_cost, breakdown (storage, api, ingestion, export), period
        """
        usage_service = TenantUsageService(tenant_id=tenant_id)
        usage_summary = usage_service.calculate_usage_summary(
            tenant_id, period_start=period_start, period_end=period_end
        )
        rates = _get_cost_rates()

        storage_gb = usage_summary.storage_bytes / (1024**3)
        storage_cost = Decimal(str(storage_gb)) * rates["storage_per_gb_month"]

        api_calls = usage_summary.api_calls_count
        api_cost = (Decimal(api_calls) / Decimal(1000)) * rates["api_per_1000"]

        ingestion_cost = usage_summary.ingestion_cost or Decimal("0")

        # Export cost: not yet tracked in TenantUsageSummary; placeholder
        export_cost = Decimal("0")

        total_cost = storage_cost + api_cost + ingestion_cost + export_cost

        breakdown = [
            {"category": "storage", "amount_usd": float(storage_cost), "quantity": storage_gb},
            {"category": "api_calls", "amount_usd": float(api_cost), "quantity": api_calls},
            {"category": "ingestion", "amount_usd": float(ingestion_cost), "quantity": None},
            {"category": "export", "amount_usd": float(export_cost), "quantity": None},
        ]

        return {
            "tenant_id": tenant_id,
            "total_cost": float(total_cost),
            "breakdown": breakdown,
            "period_start": usage_summary.period_start.isoformat(),
            "period_end": usage_summary.period_end.isoformat(),
            "period": "month",
        }

    @staticmethod
    def get_cost_breakdown(
        tenant_id: str,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        period: str = "month",
    ) -> Dict[str, Any]:
        """
        Get cost breakdown by category (alias for get_cost_summary with period param).
        """
        result = CostTrackingService.get_cost_summary(
            tenant_id, period_start=period_start, period_end=period_end
        )
        result["period"] = period
        return result

    @staticmethod
    def get_cost_by_asset(
        tenant_id: str,
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get cost breakdown by asset (storage allocated per asset).
        Includes "Unassigned" row for storage from datasets without an asset.
        """
        from hub.apps.assets.models import Asset
        from hub.apps.datasets.models import Dataset
        from hub.apps.files.models import FileStatus

        now = timezone.now()
        if not period_start:
            period_start = datetime(now.year, now.month, 1, tzinfo=now.tzinfo)
        if not period_end:
            if period_start.month == 12:
                period_end = datetime(
                    period_start.year + 1, 1, 1, tzinfo=period_start.tzinfo
                ) - timedelta(seconds=1)
            else:
                period_end = datetime(
                    period_start.year,
                    period_start.month + 1,
                    1,
                    tzinfo=period_start.tzinfo,
                ) - timedelta(seconds=1)

        rates = _get_cost_rates()
        by_asset: List[Dict[str, Any]] = []

        assets = Asset.objects.filter(tenant_id=tenant_id).prefetch_related("datasets__file")
        for asset in assets:
            storage_bytes = 0
            for dataset in asset.datasets.all():
                if dataset.file and dataset.file.status in [
                    FileStatus.ACTIVE,
                    FileStatus.COMPLETED,
                ]:
                    storage_bytes += dataset.file.size or 0

            storage_gb = storage_bytes / (1024**3)
            cost_usd = float(Decimal(str(storage_gb)) * rates["storage_per_gb_month"])

            by_asset.append(
                {
                    "asset_id": str(asset.id),
                    "asset_name": asset.name,
                    "asset_key": asset.key,
                    "storage_bytes": storage_bytes,
                    "storage_gb": round(storage_gb, 4),
                    "cost_usd": round(cost_usd, 4),
                }
            )

        # Include unassigned storage (datasets with asset=None)
        unassigned_datasets = Dataset.objects.filter(
            tenant_id=tenant_id, asset__isnull=True
        ).select_related("file")
        unassigned_bytes = 0
        for dataset in unassigned_datasets:
            if dataset.file and dataset.file.status in [
                FileStatus.ACTIVE,
                FileStatus.COMPLETED,
            ]:
                unassigned_bytes += dataset.file.size or 0
        if unassigned_bytes > 0:
            unassigned_gb = unassigned_bytes / (1024**3)
            unassigned_cost = float(
                Decimal(str(unassigned_gb)) * rates["storage_per_gb_month"]
            )
            by_asset.append(
                {
                    "asset_id": "__unassigned__",
                    "asset_name": "Unassigned",
                    "asset_key": "(datasets without asset)",
                    "storage_bytes": unassigned_bytes,
                    "storage_gb": round(unassigned_gb, 4),
                    "cost_usd": round(unassigned_cost, 4),
                }
            )

        total_cost = sum(a["cost_usd"] for a in by_asset)
        return {
            "tenant_id": tenant_id,
            "by_asset": sorted(by_asset, key=lambda x: -x["cost_usd"]),
            "total_cost": round(total_cost, 2),
        }

    @staticmethod
    def get_cost_recommendations(tenant_id: str) -> Dict[str, Any]:
        """
        Get cost optimization recommendations for tenant.
        """
        usage_service = TenantUsageService(tenant_id=tenant_id)
        current_usage = usage_service.get_current_usage(tenant_id)
        tenant = Tenant.objects.get(id=tenant_id)
        plan = tenant.plan
        recommendations: List[Dict[str, Any]] = []

        if plan and plan.limits_json:
            limits = plan.limits_json
            storage_gb = current_usage.get("storage_gb", 0)
            max_storage = limits.get("max_storage_gb")
            if max_storage is not None and storage_gb >= max_storage * 0.9:
                recommendations.append(
                    {
                        "type": "storage",
                        "message": "Storage usage is approaching plan limit. Consider archiving old data or upgrading.",
                        "severity": "warning",
                    }
                )

            api_calls = current_usage.get("api_calls_this_month", 0)
            max_api = limits.get("max_api_calls_per_month")
            if max_api is not None and api_calls >= max_api * 0.9:
                recommendations.append(
                    {
                        "type": "api_calls",
                        "message": "API usage is approaching plan limit. Consider caching or upgrading.",
                        "severity": "warning",
                    }
                )

        if not recommendations:
            recommendations.append(
                {
                    "type": "ok",
                    "message": "Usage is within plan limits.",
                    "severity": "info",
                }
            )

        return {"tenant_id": tenant_id, "recommendations": recommendations}

    @staticmethod
    def get_cost_trends(
        tenant_id: str,
        period: str = "month",
        months: int = 6,
    ) -> Dict[str, Any]:
        """
        Get cost trends over time (historical usage summaries).
        """
        now = timezone.now()
        trends: List[Dict[str, Any]] = []

        for i in range(months - 1, -1, -1):
            month = now.month - i
            year = now.year
            while month <= 0:
                month += 12
                year -= 1
            period_start = datetime(year, month, 1, tzinfo=now.tzinfo)
            if month == 12:
                period_end = datetime(year + 1, 1, 1, tzinfo=now.tzinfo) - timedelta(seconds=1)
            else:
                period_end = datetime(year, month + 1, 1, tzinfo=now.tzinfo) - timedelta(
                    seconds=1
                )

            summary = CostTrackingService.get_cost_summary(
                tenant_id, period_start=period_start, period_end=period_end
            )
            trends.append(
                {
                    "period_start": summary["period_start"],
                    "period_end": summary["period_end"],
                    "total_cost": summary["total_cost"],
                    "breakdown": summary["breakdown"],
                }
            )

        return {"tenant_id": tenant_id, "trends": trends, "period": period}
