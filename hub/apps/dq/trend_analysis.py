"""
DQ Trend Analysis

Tracks quality trends over time with visualization and forecasting.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from django.db.models import Q, Avg, Count
from django.utils import timezone
from datetime import timedelta
import statistics
import structlog

from .models import DQRun, DQTrend, DQTrendDirection, DQRunStatus
from hub.apps.assets.models import Asset
from hub.apps.datasets.models import Dataset

logger = structlog.get_logger(__name__)


class TrendAnalyzer:
    """
    Analyzes data quality trends over time.
    """
    
    @staticmethod
    def calculate_trend(
        asset_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        tenant_id: str = None,
        metric_type: str = "quality_score",
        period_type: str = "DAILY",
        periods: int = 30
    ) -> List[DQTrend]:
        """
        Calculate trends for a metric over time.
        
        Args:
            asset_id: Optional asset UUID
            dataset_id: Optional dataset UUID
            tenant_id: Tenant UUID
            metric_type: Type of metric (e.g., quality_score, completeness)
            period_type: Period type (HOURLY, DAILY, WEEKLY, MONTHLY)
            periods: Number of periods to analyze
        
        Returns:
            List of trend records
        """
        # Get DQ runs
        dq_runs = TrendAnalyzer._get_dq_runs(
            asset_id=asset_id,
            dataset_id=dataset_id,
            tenant_id=tenant_id,
            periods=periods
        )
        
        if not dq_runs:
            return []
        
        # Group by period
        period_groups = TrendAnalyzer._group_by_period(
            dq_runs,
            period_type=period_type,
            metric_type=metric_type
        )
        
        # Calculate trends
        trends = []
        previous_value = None
        
        for period_start, period_data in sorted(period_groups.items()):
            current_value = period_data["value"]
            period_end = period_start + TrendAnalyzer._get_period_delta(period_type)
            
            # Calculate change
            change_amount = None
            change_percent = None
            direction = DQTrendDirection.STABLE
            
            if previous_value is not None:
                change_amount = current_value - previous_value
                change_percent = (change_amount / previous_value * 100) if previous_value > 0 else 0
                
                if change_percent > 1.0:
                    direction = DQTrendDirection.IMPROVING
                elif change_percent < -1.0:
                    direction = DQTrendDirection.DEGRADING
                else:
                    direction = DQTrendDirection.STABLE
            
            # Calculate trend strength (based on consistency)
            trend_strength = TrendAnalyzer._calculate_trend_strength(
                period_groups,
                period_start,
                direction
            )
            
            # Forecast next period (simple linear forecast)
            forecast_value = TrendAnalyzer._forecast_value(
                period_groups,
                period_start,
                current_value
            )
            
            # Create trend record
            trend = DQTrend(
                tenant_id=tenant_id,
                asset_id=asset_id,
                dataset_id=dataset_id,
                metric_type=metric_type,
                period_start=period_start,
                period_end=period_end,
                period_type=period_type,
                current_value=current_value,
                previous_value=previous_value,
                change_amount=change_amount,
                change_percent=change_percent,
                direction=direction,
                trend_strength=trend_strength,
                forecast_value=forecast_value,
                metadata={
                    "run_count": period_data["count"],
                    "period_index": len(trends)
                }
            )
            trends.append(trend)
            previous_value = current_value
        
        return trends
    
    @staticmethod
    def _get_dq_runs(
        asset_id: Optional[str],
        dataset_id: Optional[str],
        tenant_id: str,
        periods: int
    ) -> List[DQRun]:
        """Get DQ runs for trend analysis"""
        filter_q = Q(
            tenant_id=tenant_id,
            status=DQRunStatus.SUCCEEDED
        )
        
        if asset_id:
            filter_q &= Q(asset_id=asset_id)
        elif dataset_id:
            filter_q &= Q(dataset_id=dataset_id)
        else:
            return []
        
        # Get runs from last N periods
        cutoff_date = timezone.now() - timedelta(days=periods)
        
        return list(
            DQRun.objects.filter(
                filter_q,
                completed_at__gte=cutoff_date
            ).order_by('completed_at')
        )
    
    @staticmethod
    def _group_by_period(
        dq_runs: List[DQRun],
        period_type: str,
        metric_type: str
    ) -> Dict[timezone.datetime, Dict[str, Any]]:
        """Group DQ runs by time period"""
        period_groups = {}
        
        for run in dq_runs:
            if not run.completed_at:
                continue
            
            # Get period start
            period_start = TrendAnalyzer._get_period_start(
                run.completed_at,
                period_type
            )
            
            # Get metric value
            metric_value = TrendAnalyzer._get_metric_value(run, metric_type)
            if metric_value is None:
                continue
            
            # Group by period
            if period_start not in period_groups:
                period_groups[period_start] = {
                    "values": [],
                    "count": 0
                }
            
            period_groups[period_start]["values"].append(metric_value)
            period_groups[period_start]["count"] += 1
        
        # Calculate average for each period
        for period_start, period_data in period_groups.items():
            if period_data["values"]:
                period_data["value"] = statistics.mean(period_data["values"])
            else:
                period_data["value"] = 0.0
        
        return period_groups
    
    @staticmethod
    def _get_period_start(dt: timezone.datetime, period_type: str) -> timezone.datetime:
        """Get period start timestamp"""
        if period_type == "HOURLY":
            return dt.replace(minute=0, second=0, microsecond=0)
        elif period_type == "DAILY":
            return dt.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period_type == "WEEKLY":
            # Start of week (Monday)
            days_since_monday = dt.weekday()
            return (dt - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif period_type == "MONTHLY":
            return dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            return dt.replace(hour=0, minute=0, second=0, microsecond=0)
    
    @staticmethod
    def _get_period_delta(period_type: str) -> timedelta:
        """Get time delta for period type"""
        if period_type == "HOURLY":
            return timedelta(hours=1)
        elif period_type == "DAILY":
            return timedelta(days=1)
        elif period_type == "WEEKLY":
            return timedelta(weeks=1)
        elif period_type == "MONTHLY":
            return timedelta(days=30)  # Approximate
        else:
            return timedelta(days=1)
    
    @staticmethod
    def _get_metric_value(dq_run: DQRun, metric_type: str) -> Optional[float]:
        """Get metric value from DQ run"""
        if metric_type == "quality_score":
            return dq_run.quality_score
        
        # Extract from details_json
        if dq_run.details_json and isinstance(dq_run.details_json, dict):
            return dq_run.details_json.get(metric_type)
        
        return None
    
    @staticmethod
    def _calculate_trend_strength(
        period_groups: Dict[timezone.datetime, Dict[str, Any]],
        current_period: timezone.datetime,
        direction: str
    ) -> float:
        """Calculate trend strength (0-1)"""
        # Get recent periods
        sorted_periods = sorted(period_groups.keys())
        current_index = sorted_periods.index(current_period) if current_period in sorted_periods else -1
        
        if current_index < 2:
            return 0.5  # Not enough data
        
        # Check consistency of direction in recent periods
        recent_periods = sorted_periods[max(0, current_index - 4):current_index + 1]
        consistent_count = 0
        
        for i in range(1, len(recent_periods)):
            prev_period = recent_periods[i - 1]
            curr_period = recent_periods[i]
            
            if prev_period in period_groups and curr_period in period_groups:
                prev_value = period_groups[prev_period]["value"]
                curr_value = period_groups[curr_period]["value"]
                
                if direction == DQTrendDirection.IMPROVING and curr_value > prev_value:
                    consistent_count += 1
                elif direction == DQTrendDirection.DEGRADING and curr_value < prev_value:
                    consistent_count += 1
                elif direction == DQTrendDirection.STABLE and abs(curr_value - prev_value) < 1.0:
                    consistent_count += 1
        
        # Trend strength is proportion of consistent periods
        return consistent_count / max(1, len(recent_periods) - 1)
    
    @staticmethod
    def _forecast_value(
        period_groups: Dict[timezone.datetime, Dict[str, Any]],
        current_period: timezone.datetime,
        current_value: float
    ) -> Optional[float]:
        """Forecast value for next period using simple linear regression"""
        sorted_periods = sorted(period_groups.keys())
        current_index = sorted_periods.index(current_period) if current_period in sorted_periods else -1
        
        if current_index < 2:
            return None
        
        # Get recent values for linear regression
        recent_periods = sorted_periods[max(0, current_index - 4):current_index + 1]
        values = [period_groups[p]["value"] for p in recent_periods if p in period_groups]
        
        if len(values) < 2:
            return None
        
        # Simple linear forecast: average change rate
        changes = [values[i] - values[i - 1] for i in range(1, len(values))]
        avg_change = statistics.mean(changes) if changes else 0.0
        
        return current_value + avg_change
    
    @staticmethod
    def get_trend_visualization(
        trends: List[DQTrend],
        format: str = "json"
    ) -> Any:
        """
        Generate trend visualization.
        
        Args:
            trends: List of trend records
            format: Output format (json, csv, chart_data)
        
        Returns:
            Visualization in requested format
        """
        if format == "json":
            return [
                {
                    "period_start": trend.period_start.isoformat(),
                    "period_end": trend.period_end.isoformat(),
                    "current_value": trend.current_value,
                    "previous_value": trend.previous_value,
                    "change_amount": trend.change_amount,
                    "change_percent": trend.change_percent,
                    "direction": trend.direction,
                    "trend_strength": trend.trend_strength,
                    "forecast_value": trend.forecast_value
                }
                for trend in trends
            ]
        elif format == "csv":
            lines = ["period_start,period_end,current_value,previous_value,change_amount,change_percent,direction,trend_strength,forecast_value"]
            for trend in trends:
                lines.append(
                    f"{trend.period_start.isoformat()},{trend.period_end.isoformat()},"
                    f"{trend.current_value},{trend.previous_value or ''},"
                    f"{trend.change_amount or ''},{trend.change_percent or ''},"
                    f"{trend.direction},{trend.trend_strength or ''},{trend.forecast_value or ''}"
                )
            return "\n".join(lines)
        elif format == "chart_data":
            # Format for charting libraries (e.g., Chart.js, D3.js)
            return {
                "labels": [trend.period_start.isoformat() for trend in trends],
                "datasets": [
                    {
                        "label": "Current Value",
                        "data": [trend.current_value for trend in trends],
                        "borderColor": "rgb(75, 192, 192)",
                        "backgroundColor": "rgba(75, 192, 192, 0.2)"
                    },
                    {
                        "label": "Forecast",
                        "data": [trend.forecast_value for trend in trends if trend.forecast_value],
                        "borderColor": "rgb(255, 99, 132)",
                        "borderDash": [5, 5],
                        "backgroundColor": "rgba(255, 99, 132, 0.2)"
                    }
                ]
            }
        
        return trends

