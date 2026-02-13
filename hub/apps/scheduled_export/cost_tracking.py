"""
Export Cost Tracking

Tracks storage, compute, and network costs for scheduled export runs.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Dict, Optional

from django.db.models import Avg, Count, Sum
from django.utils import timezone

from .models import ExportRunCost, ScheduledExport, ScheduledExportRun

logger = logging.getLogger(__name__)


class CostTrackingManager:
    """
    Manager for tracking export costs.
    """

    # Default cost rates (per GB/month for storage, per hour for compute, per GB for network)
    DEFAULT_STORAGE_COST_PER_GB_MONTH = Decimal("0.023")  # S3 standard storage
    DEFAULT_COMPUTE_COST_PER_HOUR = Decimal("0.10")  # Approximate worker cost
    DEFAULT_NETWORK_COST_PER_GB = Decimal("0.09")  # Data transfer cost

    @staticmethod
    def calculate_run_costs(
        run_id: str,
        storage_cost_per_gb_month: Optional[Decimal] = None,
        compute_cost_per_hour: Optional[Decimal] = None,
        network_cost_per_gb: Optional[Decimal] = None,
    ) -> ExportRunCost:
        """
        Calculate costs for a specific export run.

        Args:
            run_id: ScheduledExportRun UUID
            storage_cost_per_gb_month: Optional custom storage cost rate
            compute_cost_per_hour: Optional custom compute cost rate
            network_cost_per_gb: Optional custom network cost rate

        Returns:
            Created ExportRunCost instance
        """
        run = ScheduledExportRun.objects.select_related("scheduled_export", "tenant").get(id=run_id)

        # Use defaults if not provided
        storage_rate = (
            storage_cost_per_gb_month or CostTrackingManager.DEFAULT_STORAGE_COST_PER_GB_MONTH
        )
        compute_rate = compute_cost_per_hour or CostTrackingManager.DEFAULT_COMPUTE_COST_PER_HOUR
        network_rate = network_cost_per_gb or CostTrackingManager.DEFAULT_NETWORK_COST_PER_GB

        # Calculate storage cost
        # Estimate based on items exported (assume average size per item)
        # In production, this would track actual exported file sizes
        storage_size_bytes = 0
        if run.result_json:
            # Try to get size from result_json
            items_exported = run.result_json.get("items_exported", [])
            if isinstance(items_exported, list):
                for item_info in items_exported:
                    if isinstance(item_info, dict):
                        storage_size_bytes += item_info.get("size_bytes", 0)

        # If not in result_json, estimate based on items_exported count
        # Assume average 10MB per item (conservative estimate)
        if storage_size_bytes == 0 and run.items_exported > 0:
            storage_size_bytes = run.items_exported * 10 * 1024 * 1024  # 10MB per item

        # Convert bytes to GB
        storage_size_gb = Decimal(storage_size_bytes) / Decimal(1024**3)

        # Calculate storage cost (pro-rated for the month)
        # For simplicity, we'll use a daily rate
        days_in_month = 30
        daily_storage_rate = storage_rate / Decimal(days_in_month)
        storage_cost = storage_size_gb * daily_storage_rate

        # Calculate compute cost
        compute_hours = Decimal("0.0")
        if run.started_at and run.completed_at:
            duration_seconds = (run.completed_at - run.started_at).total_seconds()
            compute_hours = Decimal(duration_seconds) / Decimal(3600)
        elif run.started_at:
            # If still running, use current time
            duration_seconds = (timezone.now() - run.started_at).total_seconds()
            compute_hours = Decimal(duration_seconds) / Decimal(3600)

        compute_cost = compute_hours * compute_rate

        # Calculate network cost (data transfer)
        # Estimate based on items exported
        network_size_gb = Decimal(storage_size_bytes) / Decimal(1024**3)
        network_cost = network_size_gb * network_rate

        # Create cost record
        cost = ExportRunCost.objects.create(
            run=run,
            tenant=run.tenant,
            cost_components={
                "storage": {
                    "size_bytes": storage_size_bytes,
                    "size_gb": float(storage_size_gb),
                    "rate_per_gb_month": float(storage_rate),
                    "cost_usd": float(storage_cost),
                },
                "compute": {
                    "hours": float(compute_hours),
                    "rate_per_hour": float(compute_rate),
                    "cost_usd": float(compute_cost),
                },
                "network": {
                    "size_gb": float(network_size_gb),
                    "rate_per_gb": float(network_rate),
                    "cost_usd": float(network_cost),
                },
            },
        )

        logger.info(
            "Calculated export run costs",
            extra={
                "run_id": run_id,
                "storage_cost_usd": float(storage_cost),
                "compute_cost_usd": float(compute_cost),
                "network_cost_usd": float(network_cost),
            },
        )

        return cost

    @staticmethod
    def get_cost_report(
        tenant_id: str,
        scheduled_export_id: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Get cost report for exports.

        Args:
            tenant_id: Tenant UUID
            scheduled_export_id: Optional specific export ID
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            Cost report dictionary
        """
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.get(id=tenant_id)

        query = ExportRunCost.objects.filter(tenant=tenant)

        if scheduled_export_id:
            query = query.filter(run__scheduled_export_id=scheduled_export_id)

        if start_date:
            query = query.filter(calculated_at__gte=start_date)

        if end_date:
            query = query.filter(calculated_at__lte=end_date)

        # Aggregate costs from cost_components
        total_storage_cost = Decimal("0.0")
        total_compute_cost = Decimal("0.0")
        total_network_cost = Decimal("0.0")

        for cost in query:
            components = cost.cost_components or {}
            if "storage" in components:
                total_storage_cost += Decimal(str(components["storage"].get("cost_usd", 0)))
            if "compute" in components:
                total_compute_cost += Decimal(str(components["compute"].get("cost_usd", 0)))
            if "network" in components:
                total_network_cost += Decimal(str(components["network"].get("cost_usd", 0)))

        total_cost = total_storage_cost + total_compute_cost + total_network_cost

        # Average costs
        cost_count = query.count()
        avg_storage_cost = (
            total_storage_cost / Decimal(cost_count) if cost_count > 0 else Decimal("0.0")
        )
        avg_compute_cost = (
            total_compute_cost / Decimal(cost_count) if cost_count > 0 else Decimal("0.0")
        )
        avg_total_cost = total_cost / Decimal(cost_count) if cost_count > 0 else Decimal("0.0")

        # Cost by export
        cost_by_export = []
        scheduled_exports = ScheduledExport.objects.filter(tenant=tenant)
        if scheduled_export_id:
            scheduled_exports = scheduled_exports.filter(id=scheduled_export_id)

        for export in scheduled_exports:
            export_costs = query.filter(run__scheduled_export=export)
            export_storage_cost = Decimal("0.0")
            export_compute_cost = Decimal("0.0")
            export_network_cost = Decimal("0.0")

            for cost in export_costs:
                components = cost.cost_components or {}
                if "storage" in components:
                    export_storage_cost += Decimal(str(components["storage"].get("cost_usd", 0)))
                if "compute" in components:
                    export_compute_cost += Decimal(str(components["compute"].get("cost_usd", 0)))
                if "network" in components:
                    export_network_cost += Decimal(str(components["network"].get("cost_usd", 0)))

            export_total_cost = export_storage_cost + export_compute_cost + export_network_cost
            if export_total_cost > 0:
                cost_by_export.append(
                    {
                        "scheduled_export_id": str(export.id),
                        "scheduled_export_name": export.name,
                        "total_cost_usd": float(export_total_cost),
                        "storage_cost_usd": float(export_storage_cost),
                        "compute_cost_usd": float(export_compute_cost),
                        "network_cost_usd": float(export_network_cost),
                        "run_count": export_costs.count(),
                    }
                )

        # Daily cost trend
        daily_costs = []
        if start_date and end_date:
            current_date = start_date.date()
            end_date_only = end_date.date()

            while current_date <= end_date_only:
                day_start = timezone.make_aware(datetime.combine(current_date, datetime.min.time()))
                day_end = day_start + timedelta(days=1)

                day_query = query.filter(calculated_at__gte=day_start, calculated_at__lt=day_end)

                day_storage_cost = Decimal("0.0")
                day_compute_cost = Decimal("0.0")
                day_network_cost = Decimal("0.0")

                for cost in day_query:
                    components = cost.cost_components or {}
                    if "storage" in components:
                        day_storage_cost += Decimal(str(components["storage"].get("cost_usd", 0)))
                    if "compute" in components:
                        day_compute_cost += Decimal(str(components["compute"].get("cost_usd", 0)))
                    if "network" in components:
                        day_network_cost += Decimal(str(components["network"].get("cost_usd", 0)))

                day_total_cost = day_storage_cost + day_compute_cost + day_network_cost

                daily_costs.append(
                    {
                        "date": current_date.isoformat(),
                        "total_cost_usd": float(day_total_cost),
                        "storage_cost_usd": float(day_storage_cost),
                        "compute_cost_usd": float(day_compute_cost),
                        "network_cost_usd": float(day_network_cost),
                    }
                )

                current_date += timedelta(days=1)

        return {
            "summary": {
                "total_cost_usd": float(total_cost),
                "total_storage_cost_usd": float(total_storage_cost),
                "total_compute_cost_usd": float(total_compute_cost),
                "total_network_cost_usd": float(total_network_cost),
                "avg_storage_cost_usd": float(avg_storage_cost),
                "avg_compute_cost_usd": float(avg_compute_cost),
                "avg_total_cost_usd": float(avg_total_cost),
                "total_runs": cost_count,
            },
            "cost_by_export": cost_by_export,
            "daily_trends": daily_costs,
        }
