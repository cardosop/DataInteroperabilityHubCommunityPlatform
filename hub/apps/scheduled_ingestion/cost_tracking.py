"""
Ingestion Cost Tracking

Tracks storage, compute, and network costs for scheduled ingestion runs.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import structlog
from django.db.models import Avg, Count, Sum
from django.utils import timezone

from hub.apps.datasets.models import Dataset

from .models import IngestionCost, ScheduledIngestionRun

logger = structlog.get_logger(__name__)


class CostTrackingManager:
    """
    Manager for tracking ingestion costs.
    """

    # Default cost rates (per GB/month for storage, per hour for compute, per GB for network)
    DEFAULT_STORAGE_COST_PER_GB_MONTH = Decimal("0.023")  # S3 standard storage
    DEFAULT_COMPUTE_COST_PER_HOUR = Decimal("0.10")  # Approximate worker cost
    DEFAULT_NETWORK_COST_PER_GB = Decimal("0.09")  # Data transfer cost

    @staticmethod
    def calculate_run_costs(
        run_id: str,
        storage_cost_per_gb_month: Decimal | None = None,
        compute_cost_per_hour: Decimal | None = None,
        network_cost_per_gb: Decimal | None = None,
    ) -> IngestionCost:
        """
        Calculate costs for a specific ingestion run.

        Args:
            run_id: ScheduledIngestionRun UUID
            storage_cost_per_gb_month: Optional custom storage cost rate
            compute_cost_per_hour: Optional custom compute cost rate
            network_cost_per_gb: Optional custom network cost rate

        Returns:
            Created IngestionCost instance
        """
        run = ScheduledIngestionRun.objects.get(id=run_id)

        # Use defaults if not provided
        storage_rate = (
            storage_cost_per_gb_month or CostTrackingManager.DEFAULT_STORAGE_COST_PER_GB_MONTH
        )
        compute_rate = compute_cost_per_hour or CostTrackingManager.DEFAULT_COMPUTE_COST_PER_HOUR
        network_rate = network_cost_per_gb or CostTrackingManager.DEFAULT_NETWORK_COST_PER_GB

        # Calculate storage cost
        # Get total size of files created in this run
        storage_size_bytes = 0
        if run.result_json:
            # Try to get size from result_json
            files_processed = run.result_json.get("files_processed", [])
            for file_info in files_processed:
                if isinstance(file_info, dict):
                    storage_size_bytes += file_info.get("size_bytes", 0)

        # If not in result_json, calculate from datasets created
        if storage_size_bytes == 0 and run.datasets_created > 0:
            # Get datasets created around run time
            datasets = Dataset.objects.filter(
                tenant=run.scheduled_ingestion.tenant,
                created_at__gte=run.started_at if run.started_at else run.created_at,
                created_at__lte=run.completed_at if run.completed_at else timezone.now(),
            ).select_related("file")

            for dataset in datasets[: run.datasets_created]:
                if dataset.file:
                    storage_size_bytes += dataset.file.size or 0

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
        # Estimate based on files processed
        network_size_gb = Decimal(storage_size_bytes) / Decimal(1024**3)
        network_cost = network_size_gb * network_rate

        # Create cost record
        cost = IngestionCost.objects.create(
            scheduled_ingestion=run.scheduled_ingestion,
            run=run,
            storage_cost_usd=storage_cost,
            compute_cost_usd=compute_cost,
            network_cost_usd=network_cost,
            cost_breakdown_json={
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
            period_start=run.started_at or run.created_at,
            period_end=run.completed_at or timezone.now(),
        )

        logger.info(
            "Calculated ingestion run costs",
            run_id=run_id,
            total_cost_usd=float(cost.total_cost_usd),
            storage_cost_usd=float(storage_cost),
            compute_cost_usd=float(compute_cost),
            network_cost_usd=float(network_cost),
        )

        return cost

    @staticmethod
    def get_cost_report(
        tenant_id: str,
        scheduled_ingestion_id: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
        """
        Get cost report for ingestion.

        Args:
            tenant_id: Tenant UUID
            scheduled_ingestion_id: Optional specific ingestion ID
            start_date: Optional start date
            end_date: Optional end date

        Returns:
            Cost report dictionary
        """
        from hub.apps.tenants.models import Tenant

        tenant = Tenant.objects.get(id=tenant_id)

        query = IngestionCost.objects.filter(scheduled_ingestion__tenant=tenant)

        if scheduled_ingestion_id:
            query = query.filter(scheduled_ingestion_id=scheduled_ingestion_id)

        if start_date:
            query = query.filter(period_start__gte=start_date)

        if end_date:
            query = query.filter(period_end__lte=end_date)

        # Aggregate costs
        total_storage_cost = query.aggregate(total=Sum("storage_cost_usd"))["total"] or Decimal(
            "0.0"
        )

        total_compute_cost = query.aggregate(total=Sum("compute_cost_usd"))["total"] or Decimal(
            "0.0"
        )

        total_network_cost = query.aggregate(total=Sum("network_cost_usd"))["total"] or Decimal(
            "0.0"
        )

        total_cost = total_storage_cost + total_compute_cost + total_network_cost

        # Average costs
        avg_storage_cost = query.aggregate(avg=Avg("storage_cost_usd"))["avg"] or Decimal("0.0")

        avg_compute_cost = query.aggregate(avg=Avg("compute_cost_usd"))["avg"] or Decimal("0.0")

        avg_total_cost = query.aggregate(avg=Avg("total_cost_usd"))["avg"] or Decimal("0.0")

        # Cost by ingestion
        cost_by_ingestion = (
            query.values("scheduled_ingestion__id", "scheduled_ingestion__name")
            .annotate(
                total_cost=Sum("total_cost_usd"),
                storage_cost=Sum("storage_cost_usd"),
                compute_cost=Sum("compute_cost_usd"),
                network_cost=Sum("network_cost_usd"),
                run_count=Count("id"),
            )
            .order_by("-total_cost")
        )

        # Daily cost trend
        daily_costs = []
        if start_date and end_date:
            current_date = start_date.date()
            end_date_only = end_date.date()

            while current_date <= end_date_only:
                day_start = timezone.make_aware(datetime.combine(current_date, datetime.min.time()))
                day_end = day_start + timedelta(days=1)

                day_query = query.filter(period_start__gte=day_start, period_start__lt=day_end)

                day_total = day_query.aggregate(total=Sum("total_cost_usd"))["total"] or Decimal(
                    "0.0"
                )

                daily_costs.append(
                    {
                        "date": current_date.isoformat(),
                        "total_cost_usd": float(day_total),
                        "storage_cost_usd": float(
                            day_query.aggregate(total=Sum("storage_cost_usd"))["total"]
                            or Decimal("0.0")
                        ),
                        "compute_cost_usd": float(
                            day_query.aggregate(total=Sum("compute_cost_usd"))["total"]
                            or Decimal("0.0")
                        ),
                        "network_cost_usd": float(
                            day_query.aggregate(total=Sum("network_cost_usd"))["total"]
                            or Decimal("0.0")
                        ),
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
                "total_runs": query.count(),
            },
            "cost_by_ingestion": [
                {
                    "scheduled_ingestion_id": str(item["scheduled_ingestion__id"]),
                    "scheduled_ingestion_name": item["scheduled_ingestion__name"],
                    "total_cost_usd": float(item["total_cost"]),
                    "storage_cost_usd": float(item["storage_cost"]),
                    "compute_cost_usd": float(item["compute_cost"]),
                    "network_cost_usd": float(item["network_cost"]),
                    "run_count": item["run_count"],
                }
                for item in cost_by_ingestion
            ],
            "daily_trends": daily_costs,
        }
