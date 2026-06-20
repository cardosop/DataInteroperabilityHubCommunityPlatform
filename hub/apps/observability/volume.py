"""
Data Volume Monitoring

Tracks volume metrics (row_count, size_bytes), aggregates trends, and detects anomalies.
"""

import statistics
from datetime import timedelta
from typing import Any

import structlog
from django.db import transaction
from django.db.models import Avg, Count, Max, Min, Q
from django.db.models.functions import TruncDay, TruncHour
from django.utils import timezone

from .models import DataObservabilityMetric, VolumeTrend

logger = structlog.get_logger(__name__)


class VolumeMonitor:
    """
    Monitors data volume for datasets and assets.
    """

    @classmethod
    @transaction.atomic
    def aggregate_hourly_trends(
        cls,
        tenant_id: str,
        dataset_id: str | None = None,
        asset_id: str | None = None,
        hours: int = 24,
    ) -> list[VolumeTrend]:
        """
        Aggregate hourly volume trends.

        Args:
            tenant_id: Tenant UUID
            dataset_id: Optional dataset UUID filter
            asset_id: Optional asset UUID filter
            hours: Number of hours to aggregate (default: 24)

        Returns:
            List of VolumeTrend instances
        """
        queryset = DataObservabilityMetric.objects.filter(tenant_id=tenant_id)

        if dataset_id:
            queryset = queryset.filter(dataset_id=dataset_id)
        if asset_id:
            queryset = queryset.filter(asset_id=asset_id)

        # Get metrics from last N hours
        cutoff_time = timezone.now() - timedelta(hours=hours)
        queryset = queryset.filter(recorded_at__gte=cutoff_time)

        # Group by hour
        hourly_data = (
            queryset.annotate(hour=TruncHour("recorded_at"))
            .values("hour", "dataset_id", "asset_id")
            .annotate(
                avg_row_count=Avg("row_count"),
                min_row_count=Min("row_count"),
                max_row_count=Max("row_count"),
                avg_size_bytes=Avg("size_bytes"),
                min_size_bytes=Min("size_bytes"),
                max_size_bytes=Max("size_bytes"),
                sample_count=Count("id"),
            )
            .order_by("hour")
        )

        trends = []
        for item in hourly_data:
            period_start = item["hour"]
            period_end = period_start + timedelta(hours=1)

            # Lookup kwargs for update_or_create (defaults= first, rest are lookup)
            lookup = {
                "tenant_id": tenant_id,
                "period_type": "HOURLY",
                "period_start": period_start,
            }
            if item.get("dataset_id"):
                lookup["dataset_id"] = item["dataset_id"]
            if item.get("asset_id"):
                lookup["asset_id"] = item["asset_id"]

            trend, _created = VolumeTrend.objects.update_or_create(
                defaults={
                    "period_end": period_end,
                    "avg_row_count": int(item["avg_row_count"]) if item["avg_row_count"] else None,
                    "min_row_count": int(item["min_row_count"]) if item["min_row_count"] else None,
                    "max_row_count": int(item["max_row_count"]) if item["max_row_count"] else None,
                    "avg_size_bytes": int(item["avg_size_bytes"])
                    if item["avg_size_bytes"]
                    else None,
                    "min_size_bytes": int(item["min_size_bytes"])
                    if item["min_size_bytes"]
                    else None,
                    "max_size_bytes": int(item["max_size_bytes"])
                    if item["max_size_bytes"]
                    else None,
                    "sample_count": item["sample_count"],
                },
                **lookup,
            )

            # Detect anomalies
            cls._detect_anomalies(trend, tenant_id, dataset_id, asset_id)

            trends.append(trend)

        logger.info(
            "Hourly volume trends aggregated",
            tenant_id=tenant_id,
            trends_count=len(trends),
            hours=hours,
        )

        return trends

    @classmethod
    @transaction.atomic
    def aggregate_daily_trends(
        cls,
        tenant_id: str,
        dataset_id: str | None = None,
        asset_id: str | None = None,
        days: int = 30,
    ) -> list[VolumeTrend]:
        """
        Aggregate daily volume trends.

        Args:
            tenant_id: Tenant UUID
            dataset_id: Optional dataset UUID filter
            asset_id: Optional asset UUID filter
            days: Number of days to aggregate (default: 30)

        Returns:
            List of VolumeTrend instances
        """
        queryset = DataObservabilityMetric.objects.filter(tenant_id=tenant_id)

        if dataset_id:
            queryset = queryset.filter(dataset_id=dataset_id)
        if asset_id:
            queryset = queryset.filter(asset_id=asset_id)

        # Get metrics from last N days
        cutoff_time = timezone.now() - timedelta(days=days)
        queryset = queryset.filter(recorded_at__gte=cutoff_time)

        # Group by day
        daily_data = (
            queryset.annotate(day=TruncDay("recorded_at"))
            .values("day", "dataset_id", "asset_id")
            .annotate(
                avg_row_count=Avg("row_count"),
                min_row_count=Min("row_count"),
                max_row_count=Max("row_count"),
                avg_size_bytes=Avg("size_bytes"),
                min_size_bytes=Min("size_bytes"),
                max_size_bytes=Max("size_bytes"),
                sample_count=Count("id"),
            )
            .order_by("day")
        )

        trends = []
        for item in daily_data:
            period_start = item["day"]
            period_end = period_start + timedelta(days=1)

            # Lookup kwargs for update_or_create (first arg is defaults, rest are lookup)
            lookup = {
                "tenant_id": tenant_id,
                "period_type": "DAILY",
                "period_start": period_start,
            }
            if item.get("dataset_id"):
                lookup["dataset_id"] = item["dataset_id"]
            if item.get("asset_id"):
                lookup["asset_id"] = item["asset_id"]

            trend, _created = VolumeTrend.objects.update_or_create(
                defaults={
                    "period_end": period_end,
                    "avg_row_count": int(item["avg_row_count"]) if item["avg_row_count"] else None,
                    "min_row_count": int(item["min_row_count"]) if item["min_row_count"] else None,
                    "max_row_count": int(item["max_row_count"]) if item["max_row_count"] else None,
                    "avg_size_bytes": int(item["avg_size_bytes"])
                    if item["avg_size_bytes"]
                    else None,
                    "min_size_bytes": int(item["min_size_bytes"])
                    if item["min_size_bytes"]
                    else None,
                    "max_size_bytes": int(item["max_size_bytes"])
                    if item["max_size_bytes"]
                    else None,
                    "sample_count": item["sample_count"],
                },
                **lookup,
            )

            # Detect anomalies
            cls._detect_anomalies(trend, tenant_id, dataset_id, asset_id)

            trends.append(trend)

        logger.info(
            "Daily volume trends aggregated",
            tenant_id=tenant_id,
            trends_count=len(trends),
            days=days,
        )

        return trends

    @staticmethod
    def _detect_anomalies(
        trend: VolumeTrend,
        tenant_id: str,
        dataset_id: str | None = None,
        asset_id: str | None = None,
    ):
        """
        Detect anomalies in volume trends using statistical methods.

        Uses z-score method: values more than 3 standard deviations from mean are anomalies.
        """
        # Get historical trends for comparison
        historical_filter = Q(tenant_id=tenant_id, period_type=trend.period_type)

        if dataset_id:
            historical_filter &= Q(dataset_id=dataset_id)
        if asset_id:
            historical_filter &= Q(asset_id=asset_id)

        # Get last 30 periods for baseline
        historical = VolumeTrend.objects.filter(
            historical_filter, period_start__lt=trend.period_start
        ).order_by("-period_start")[:30]

        if len(historical) < 5:
            # Not enough data for anomaly detection
            trend.is_anomaly = False
            trend.anomaly_type = None
            trend.anomaly_score = None
            trend.save()
            return

        # Calculate baseline statistics for row_count
        if trend.avg_row_count is not None:
            baseline_row_counts = [
                h.avg_row_count for h in historical if h.avg_row_count is not None
            ]
            if len(baseline_row_counts) >= 3:
                mean_row = statistics.mean(baseline_row_counts)
                stdev_row = (
                    statistics.stdev(baseline_row_counts) if len(baseline_row_counts) > 1 else 0
                )

                if stdev_row > 0:
                    z_score_row = abs((trend.avg_row_count - mean_row) / stdev_row)

                    if z_score_row > 3.0:
                        trend.is_anomaly = True
                        trend.anomaly_type = "SPIKE" if trend.avg_row_count > mean_row else "DROP"
                        trend.anomaly_score = min(z_score_row / 3.0, 1.0)  # Normalize to 0-1
                        trend.save()
                        return

        # Calculate baseline statistics for size_bytes
        if trend.avg_size_bytes is not None:
            baseline_size_bytes = [
                h.avg_size_bytes for h in historical if h.avg_size_bytes is not None
            ]
            if len(baseline_size_bytes) >= 3:
                mean_size = statistics.mean(baseline_size_bytes)
                stdev_size = (
                    statistics.stdev(baseline_size_bytes) if len(baseline_size_bytes) > 1 else 0
                )

                if stdev_size > 0:
                    z_score_size = abs((trend.avg_size_bytes - mean_size) / stdev_size)

                    if z_score_size > 3.0:
                        trend.is_anomaly = True
                        trend.anomaly_type = "SPIKE" if trend.avg_size_bytes > mean_size else "DROP"
                        trend.anomaly_score = min(z_score_size / 3.0, 1.0)  # Normalize to 0-1
                        trend.save()
                        return

        # No anomaly detected
        trend.is_anomaly = False
        trend.anomaly_type = None
        trend.anomaly_score = None
        trend.save()

    @classmethod
    def get_volume_dashboard(
        cls,
        tenant_id: str,
        dataset_id: str | None = None,
        asset_id: str | None = None,
        period_type: str = "DAILY",
        limit: int = 30,
    ) -> dict[str, Any]:
        """
        Get volume dashboard data.

        Args:
            tenant_id: Tenant UUID
            dataset_id: Optional dataset UUID filter
            asset_id: Optional asset UUID filter
            period_type: Period type (HOURLY or DAILY)
            limit: Maximum number of trends to return

        Returns:
            Dashboard data dictionary
        """
        queryset = VolumeTrend.objects.filter(tenant_id=tenant_id, period_type=period_type)

        if dataset_id:
            queryset = queryset.filter(dataset_id=dataset_id)
        if asset_id:
            queryset = queryset.filter(asset_id=asset_id)

        # Get latest trends
        trends = queryset.order_by("-period_start")[:limit]

        # Calculate statistics
        total_trends = queryset.count()
        anomaly_count = queryset.filter(is_anomaly=True).count()

        # Get volume statistics
        volume_stats = queryset.aggregate(
            avg_row_count=Avg("avg_row_count"),
            max_row_count=Max("max_row_count"),
            min_row_count=Min("min_row_count"),
            avg_size_bytes=Avg("avg_size_bytes"),
            max_size_bytes=Max("max_size_bytes"),
            min_size_bytes=Min("min_size_bytes"),
        )

        # Format results
        results = []
        for trend in trends:
            results.append(
                {
                    "id": str(trend.id),
                    "dataset_id": str(trend.dataset_id) if trend.dataset else None,
                    "asset_id": str(trend.asset_id) if trend.asset else None,
                    "period_start": trend.period_start.isoformat(),
                    "period_end": trend.period_end.isoformat(),
                    "period_type": trend.period_type,
                    "avg_row_count": trend.avg_row_count,
                    "min_row_count": trend.min_row_count,
                    "max_row_count": trend.max_row_count,
                    "avg_size_bytes": trend.avg_size_bytes,
                    "min_size_bytes": trend.min_size_bytes,
                    "max_size_bytes": trend.max_size_bytes,
                    "sample_count": trend.sample_count,
                    "is_anomaly": trend.is_anomaly,
                    "anomaly_type": trend.anomaly_type,
                    "anomaly_score": trend.anomaly_score,
                }
            )

        return {
            "results": results,
            "summary": {
                "total_trends": total_trends,
                "anomaly_count": anomaly_count,
                "anomaly_percentage": round(
                    (anomaly_count / total_trends * 100) if total_trends > 0 else 0, 2
                ),
                "volume_stats": {
                    "avg_row_count": int(volume_stats["avg_row_count"])
                    if volume_stats["avg_row_count"]
                    else None,
                    "max_row_count": int(volume_stats["max_row_count"])
                    if volume_stats["max_row_count"]
                    else None,
                    "min_row_count": int(volume_stats["min_row_count"])
                    if volume_stats["min_row_count"]
                    else None,
                    "avg_size_bytes": int(volume_stats["avg_size_bytes"])
                    if volume_stats["avg_size_bytes"]
                    else None,
                    "max_size_bytes": int(volume_stats["max_size_bytes"])
                    if volume_stats["max_size_bytes"]
                    else None,
                    "min_size_bytes": int(volume_stats["min_size_bytes"])
                    if volume_stats["min_size_bytes"]
                    else None,
                },
            },
        }
