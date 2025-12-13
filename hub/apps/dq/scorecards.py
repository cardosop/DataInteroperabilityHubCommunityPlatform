"""
DQ Scorecards

Executive dashboards for quality metrics with drill-down capabilities.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional
from django.db.models import Q, Count, Avg, Max, Min, Sum
from django.utils import timezone
from datetime import timedelta
import structlog

from .models import DQRun, DQRunStatus, DQTrend, DQTrendDirection
from hub.apps.assets.models import Asset
from hub.apps.datasets.models import Dataset

logger = structlog.get_logger(__name__)


class DQScorecardService:
    """
    Service for generating DQ scorecards and executive dashboards.
    """
    
    @staticmethod
    def get_executive_dashboard(
        tenant_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get executive dashboard with aggregate quality metrics.
        
        Args:
            tenant_id: Tenant UUID
            days: Number of days to analyze
        
        Returns:
            Dashboard data dictionary
        """
        start_date = timezone.now() - timedelta(days=days)
        
        # Get all DQ runs in period
        dq_runs = DQRun.objects.filter(
            tenant_id=tenant_id,
            status=DQRunStatus.SUCCEEDED,
            completed_at__gte=start_date
        )
        
        # Aggregate metrics
        total_runs = dq_runs.count()
        avg_quality_score = dq_runs.aggregate(
            avg_score=Avg('quality_score')
        )['avg_score'] or 0.0
        
        # Pass/fail rates
        pass_count = dq_runs.filter(overall_status="PASS").count()
        fail_count = dq_runs.filter(overall_status="FAIL").count()
        warn_count = dq_runs.filter(overall_status="WARN").count()
        
        pass_rate = (pass_count / total_runs * 100) if total_runs > 0 else 0.0
        fail_rate = (fail_count / total_runs * 100) if total_runs > 0 else 0.0
        
        # Quality score distribution
        score_distribution = DQScorecardService._calculate_score_distribution(dq_runs)
        
        # Top quality issues
        top_issues = DQScorecardService._get_top_quality_issues(dq_runs)
        
        # Trend summary
        trend_summary = DQScorecardService._get_trend_summary(tenant_id, days)
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": timezone.now().isoformat(),
                "days": days
            },
            "summary": {
                "total_runs": total_runs,
                "avg_quality_score": round(avg_quality_score, 2),
                "pass_rate": round(pass_rate, 2),
                "fail_rate": round(fail_rate, 2),
                "warn_count": warn_count
            },
            "score_distribution": score_distribution,
            "top_issues": top_issues,
            "trend_summary": trend_summary
        }
    
    @staticmethod
    def get_asset_scorecard(
        asset_id: str,
        tenant_id: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Get scorecard for a specific asset with drill-down capabilities.
        
        Args:
            asset_id: Asset UUID
            tenant_id: Tenant UUID
            days: Number of days to analyze
        
        Returns:
            Asset scorecard data
        """
        start_date = timezone.now() - timedelta(days=days)
        
        # Get DQ runs for asset
        dq_runs = DQRun.objects.filter(
            tenant_id=tenant_id,
            asset_id=asset_id,
            status=DQRunStatus.SUCCEEDED,
            completed_at__gte=start_date
        )
        
        # Asset-level metrics
        total_runs = dq_runs.count()
        avg_quality_score = dq_runs.aggregate(
            avg_score=Avg('quality_score')
        )['avg_score'] or 0.0
        
        # Pass/fail rates
        pass_count = dq_runs.filter(overall_status="PASS").count()
        fail_count = dq_runs.filter(overall_status="FAIL").count()
        
        # Recent runs
        recent_runs = list(
            dq_runs.order_by('-completed_at')[:10].values(
                'id', 'quality_score', 'overall_status', 'completed_at'
            )
        )
        
        # Quality trends
        trends = DQTrend.objects.filter(
            tenant_id=tenant_id,
            asset_id=asset_id,
            period_start__gte=start_date
        ).order_by('-period_start')[:30]
        
        trend_data = [
            {
                "period_start": t.period_start.isoformat(),
                "current_value": t.current_value,
                "direction": t.direction,
                "change_percent": t.change_percent
            }
            for t in trends
        ]
        
        return {
            "asset_id": asset_id,
            "period": {
                "start": start_date.isoformat(),
                "end": timezone.now().isoformat(),
                "days": days
            },
            "metrics": {
                "total_runs": total_runs,
                "avg_quality_score": round(avg_quality_score, 2),
                "pass_rate": round((pass_count / total_runs * 100) if total_runs > 0 else 0.0, 2),
                "fail_rate": round((fail_count / total_runs * 100) if total_runs > 0 else 0.0, 2)
            },
            "recent_runs": recent_runs,
            "trends": trend_data
        }
    
    @staticmethod
    def _calculate_score_distribution(dq_runs) -> Dict[str, int]:
        """Calculate quality score distribution"""
        distribution = {
            "excellent": 0,  # 90-100
            "good": 0,      # 80-89
            "fair": 0,      # 70-79
            "poor": 0,      # 60-69
            "critical": 0   # <60
        }
        
        for run in dq_runs:
            if run.quality_score is None:
                continue
            
            score = run.quality_score
            if score >= 90:
                distribution["excellent"] += 1
            elif score >= 80:
                distribution["good"] += 1
            elif score >= 70:
                distribution["fair"] += 1
            elif score >= 60:
                distribution["poor"] += 1
            else:
                distribution["critical"] += 1
        
        return distribution
    
    @staticmethod
    def _get_top_quality_issues(dq_runs, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top quality issues"""
        # Analyze check-level failures from checks_json
        issue_counts = {}
        
        for run in dq_runs:
            if not run.checks_json or not isinstance(run.checks_json, list):
                continue
            
            for check in run.checks_json:
                if isinstance(check, dict):
                    check_status = check.get("status", "").upper()
                    check_name = check.get("name", "Unknown")
                    
                    if check_status in ["FAIL", "WARN"]:
                        key = f"{check_name}:{check_status}"
                        issue_counts[key] = issue_counts.get(key, 0) + 1
        
        # Sort by count and return top issues
        sorted_issues = sorted(
            issue_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:limit]
        
        return [
            {
                "issue": issue_name,
                "count": count,
                "percentage": round((count / len(dq_runs) * 100) if len(dq_runs) > 0 else 0.0, 2)
            }
            for issue_name, count in sorted_issues
        ]
    
    @staticmethod
    def _get_trend_summary(tenant_id: str, days: int) -> Dict[str, Any]:
        """Get trend summary"""
        start_date = timezone.now() - timedelta(days=days)
        
        trends = DQTrend.objects.filter(
            tenant_id=tenant_id,
            period_start__gte=start_date,
            metric_type="quality_score"
        )
        
        improving_count = trends.filter(direction=DQTrendDirection.IMPROVING).count()
        degrading_count = trends.filter(direction=DQTrendDirection.DEGRADING).count()
        stable_count = trends.filter(direction=DQTrendDirection.STABLE).count()
        
        total_trends = trends.count()
        
        return {
            "improving": improving_count,
            "degrading": degrading_count,
            "stable": stable_count,
            "improving_percent": round((improving_count / total_trends * 100) if total_trends > 0 else 0.0, 2),
            "degrading_percent": round((degrading_count / total_trends * 100) if total_trends > 0 else 0.0, 2)
        }
    
    @staticmethod
    def drill_down(
        tenant_id: str,
        asset_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        metric_type: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Drill down into specific asset, dataset, or metric.
        
        Args:
            tenant_id: Tenant UUID
            asset_id: Optional asset UUID
            dataset_id: Optional dataset UUID
            metric_type: Optional metric type
            days: Number of days to analyze
        
        Returns:
            Drill-down data
        """
        start_date = timezone.now() - timedelta(days=days)
        
        query = Q(
            tenant_id=tenant_id,
            status=DQRunStatus.SUCCEEDED,
            completed_at__gte=start_date
        )
        
        if asset_id:
            query &= Q(asset_id=asset_id)
        if dataset_id:
            query &= Q(dataset_id=dataset_id)
        
        dq_runs = DQRun.objects.filter(query)
        
        # Detailed metrics
        metrics = {
            "total_runs": dq_runs.count(),
            "avg_quality_score": dq_runs.aggregate(avg=Avg('quality_score'))['avg'] or 0.0,
            "min_quality_score": dq_runs.aggregate(min=Min('quality_score'))['min'] or 0.0,
            "max_quality_score": dq_runs.aggregate(max=Max('quality_score'))['max'] or 0.0,
        }
        
        # Run history
        run_history = list(
            dq_runs.order_by('-completed_at')[:50].values(
                'id', 'quality_score', 'overall_status', 'completed_at', 'asset_id', 'dataset_id'
            )
        )
        
        return {
            "filters": {
                "asset_id": asset_id,
                "dataset_id": dataset_id,
                "metric_type": metric_type,
                "days": days
            },
            "metrics": metrics,
            "run_history": run_history
        }

