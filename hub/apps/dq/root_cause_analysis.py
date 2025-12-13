"""
DQ Root Cause Analysis

Identify root causes of data quality issues through correlation analysis.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from django.db.models import Q, Count, Avg
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict
import statistics
import structlog

from .models import DQRun, DQRunStatus, DQAnomaly
from hub.apps.assets.models import Asset
from hub.apps.datasets.models import Dataset

logger = structlog.get_logger(__name__)


class RootCauseAnalyzer:
    """
    Analyzes root causes of data quality issues.
    """
    
    @staticmethod
    def analyze_root_cause(
        dq_run: DQRun,
        lookback_days: int = 30
    ) -> Dict[str, Any]:
        """
        Analyze root cause for a specific DQ run.
        
        Args:
            dq_run: DQ run to analyze
            lookback_days: Number of days to look back for correlation
        
        Returns:
            Root cause analysis result
        """
        start_date = timezone.now() - timedelta(days=lookback_days)
        
        # Get historical context
        historical_runs = DQRun.objects.filter(
            tenant=dq_run.tenant,
            status=DQRunStatus.SUCCEEDED,
            completed_at__gte=start_date,
            completed_at__lt=dq_run.completed_at or timezone.now()
        )
        
        if dq_run.asset:
            historical_runs = historical_runs.filter(asset=dq_run.asset)
        elif dq_run.dataset:
            historical_runs = historical_runs.filter(dataset=dq_run.dataset)
        
        # Identify potential root causes
        root_causes = []
        
        # Check for schema changes
        schema_change = RootCauseAnalyzer._check_schema_changes(dq_run, historical_runs)
        if schema_change:
            root_causes.append(schema_change)
        
        # Check for data volume changes
        volume_change = RootCauseAnalyzer._check_volume_changes(dq_run, historical_runs)
        if volume_change:
            root_causes.append(volume_change)
        
        # Check for check-level failures
        check_failures = RootCauseAnalyzer._analyze_check_failures(dq_run)
        if check_failures:
            root_causes.extend(check_failures)
        
        # Check for correlation with anomalies
        anomaly_correlation = RootCauseAnalyzer._check_anomaly_correlation(dq_run, historical_runs)
        if anomaly_correlation:
            root_causes.append(anomaly_correlation)
        
        # Calculate confidence scores
        for cause in root_causes:
            cause["confidence"] = RootCauseAnalyzer._calculate_confidence(cause, historical_runs)
        
        # Sort by confidence
        root_causes.sort(key=lambda x: x.get("confidence", 0.0), reverse=True)
        
        return {
            "dq_run_id": str(dq_run.id),
            "analysis_date": timezone.now().isoformat(),
            "root_causes": root_causes,
            "primary_cause": root_causes[0] if root_causes else None,
            "recommendations": RootCauseAnalyzer._generate_recommendations(root_causes)
        }
    
    @staticmethod
    def _check_schema_changes(
        dq_run: DQRun,
        historical_runs: Any
    ) -> Optional[Dict[str, Any]]:
        """Check for schema changes as root cause"""
        if not dq_run.dataset:
            return None
        
        # Get dataset schema
        current_schema = dq_run.dataset.schema_json
        
        # Get previous dataset version
        if dq_run.dataset.parent_version:
            previous_schema = dq_run.dataset.parent_version.schema_json
            
            if current_schema != previous_schema:
                # Compare schemas
                schema_diff = RootCauseAnalyzer._compare_schemas(
                    previous_schema,
                    current_schema
                )
                
                if schema_diff["has_changes"]:
                    return {
                        "type": "SCHEMA_CHANGE",
                        "description": "Schema changes detected",
                        "details": schema_diff,
                        "confidence": 0.7
                    }
        
        return None
    
    @staticmethod
    def _check_volume_changes(
        dq_run: DQRun,
        historical_runs: Any
    ) -> Optional[Dict[str, Any]]:
        """Check for data volume changes as root cause"""
        if not dq_run.dataset:
            return None
        
        current_row_count = dq_run.dataset.row_count
        
        # Get historical row counts
        historical_counts = []
        for run in historical_runs:
            if run.dataset and run.dataset.row_count:
                historical_counts.append(run.dataset.row_count)
        
        if len(historical_counts) < 3:
            return None
        
        avg_count = statistics.mean(historical_counts)
        std_dev = statistics.stdev(historical_counts) if len(historical_counts) > 1 else 0.0
        
        if current_row_count and std_dev > 0:
            z_score = abs((current_row_count - avg_count) / std_dev)
            
            if z_score > 2.0:  # Significant change
                change_percent = ((current_row_count - avg_count) / avg_count * 100) if avg_count > 0 else 0
                
                return {
                    "type": "VOLUME_CHANGE",
                    "description": f"Data volume changed by {change_percent:.1f}%",
                    "details": {
                        "current_count": current_row_count,
                        "average_count": avg_count,
                        "change_percent": change_percent,
                        "z_score": z_score
                    },
                    "confidence": min(0.8, 0.5 + (z_score / 10))
                }
        
        return None
    
    @staticmethod
    def _analyze_check_failures(dq_run: DQRun) -> List[Dict[str, Any]]:
        """Analyze check-level failures"""
        root_causes = []
        
        if not dq_run.checks_json or not isinstance(dq_run.checks_json, list):
            return root_causes
        
        for check in dq_run.checks_json:
            if not isinstance(check, dict):
                continue
            
            check_status = check.get("status", "").upper()
            if check_status == "FAIL":
                check_name = check.get("name", "Unknown")
                check_type = check.get("type", "Unknown")
                
                root_causes.append({
                    "type": "CHECK_FAILURE",
                    "description": f"Check '{check_name}' failed",
                    "details": {
                        "check_name": check_name,
                        "check_type": check_type,
                        "check_result": check.get("result"),
                        "check_message": check.get("message")
                    },
                    "confidence": 0.9  # High confidence for explicit failures
                })
        
        return root_causes
    
    @staticmethod
    def _check_anomaly_correlation(
        dq_run: DQRun,
        historical_runs: Any
    ) -> Optional[Dict[str, Any]]:
        """Check for correlation with anomalies"""
        # Get recent anomalies
        start_date = timezone.now() - timedelta(days=7)
        
        anomalies = DQAnomaly.objects.filter(
            tenant=dq_run.tenant,
            detected_at__gte=start_date
        )
        
        if dq_run.asset:
            anomalies = anomalies.filter(asset=dq_run.asset)
        elif dq_run.dataset:
            anomalies = anomalies.filter(dataset=dq_run.dataset)
        
        anomaly_count = anomalies.count()
        
        if anomaly_count > 0:
            # Check if anomalies correlate with quality degradation
            high_severity_anomalies = anomalies.filter(
                severity__in=["CRITICAL", "HIGH"]
            ).count()
            
            return {
                "type": "ANOMALY_CORRELATION",
                "description": f"{anomaly_count} anomalies detected recently",
                "details": {
                    "anomaly_count": anomaly_count,
                    "high_severity_count": high_severity_anomalies,
                    "time_window_days": 7
                },
                "confidence": min(0.7, 0.4 + (high_severity_anomalies * 0.1))
            }
        
        return None
    
    @staticmethod
    def _compare_schemas(
        old_schema: Dict[str, Any],
        new_schema: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Compare two schemas and identify changes"""
        old_fields = {f.get("name"): f for f in old_schema.get("fields", [])}
        new_fields = {f.get("name"): f for f in new_schema.get("fields", [])}
        
        added_fields = set(new_fields.keys()) - set(old_fields.keys())
        removed_fields = set(old_fields.keys()) - set(new_fields.keys())
        changed_fields = []
        
        for field_name in set(old_fields.keys()) & set(new_fields.keys()):
            old_field = old_fields[field_name]
            new_field = new_fields[field_name]
            
            if old_field.get("data_type") != new_field.get("data_type"):
                changed_fields.append({
                    "field": field_name,
                    "change": "type",
                    "old": old_field.get("data_type"),
                    "new": new_field.get("data_type")
                })
            
            if old_field.get("nullable") != new_field.get("nullable"):
                changed_fields.append({
                    "field": field_name,
                    "change": "nullable",
                    "old": old_field.get("nullable"),
                    "new": new_field.get("nullable")
                })
        
        return {
            "has_changes": len(added_fields) > 0 or len(removed_fields) > 0 or len(changed_fields) > 0,
            "added_fields": list(added_fields),
            "removed_fields": list(removed_fields),
            "changed_fields": changed_fields
        }
    
    @staticmethod
    def _calculate_confidence(
        cause: Dict[str, Any],
        historical_runs: Any
    ) -> float:
        """Calculate confidence score for a root cause"""
        base_confidence = cause.get("confidence", 0.5)
        
        # Adjust based on historical patterns
        if cause["type"] == "CHECK_FAILURE":
            # High confidence for explicit failures
            return min(0.95, base_confidence)
        elif cause["type"] == "SCHEMA_CHANGE":
            # Medium-high confidence
            return min(0.85, base_confidence)
        elif cause["type"] == "VOLUME_CHANGE":
            # Adjust based on magnitude
            change_percent = abs(cause.get("details", {}).get("change_percent", 0))
            if change_percent > 50:
                return min(0.9, base_confidence + 0.1)
            return base_confidence
        elif cause["type"] == "ANOMALY_CORRELATION":
            # Medium confidence
            return min(0.75, base_confidence)
        
        return base_confidence
    
    @staticmethod
    def _generate_recommendations(
        root_causes: List[Dict[str, Any]]
    ) -> List[str]:
        """Generate recommendations based on root causes"""
        recommendations = []
        
        for cause in root_causes:
            cause_type = cause.get("type")
            
            if cause_type == "SCHEMA_CHANGE":
                recommendations.append(
                    "Review schema changes and ensure data quality checks are updated accordingly"
                )
            elif cause_type == "VOLUME_CHANGE":
                recommendations.append(
                    "Investigate data volume changes - may indicate data pipeline issues"
                )
            elif cause_type == "CHECK_FAILURE":
                check_name = cause.get("details", {}).get("check_name", "check")
                recommendations.append(
                    f"Review and fix the failing check: {check_name}"
                )
            elif cause_type == "ANOMALY_CORRELATION":
                recommendations.append(
                    "Review recent anomalies and investigate underlying data issues"
                )
        
        # Add general recommendations
        if not recommendations:
            recommendations.append(
                "Review DQ run results and check-level failures for details"
            )
        
        return recommendations
    
    @staticmethod
    def generate_root_cause_report(
        tenant_id: str,
        asset_id: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """
        Generate comprehensive root cause analysis report.
        
        Args:
            tenant_id: Tenant UUID
            asset_id: Optional asset UUID
            days: Number of days to analyze
        
        Returns:
            Root cause analysis report
        """
        start_date = timezone.now() - timedelta(days=days)
        
        query = Q(
            tenant_id=tenant_id,
            status=DQRunStatus.SUCCEEDED,
            completed_at__gte=start_date,
            overall_status="FAIL"
        )
        
        if asset_id:
            query &= Q(asset_id=asset_id)
        
        failed_runs = DQRun.objects.filter(query)
        
        # Analyze each failed run
        analyses = []
        for run in failed_runs[:50]:  # Limit to 50 for performance
            analysis = RootCauseAnalyzer.analyze_root_cause(run, days)
            analyses.append(analysis)
        
        # Aggregate root causes
        cause_counts = defaultdict(int)
        for analysis in analyses:
            primary = analysis.get("primary_cause")
            if primary:
                cause_counts[primary["type"]] += 1
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": timezone.now().isoformat(),
                "days": days
            },
            "summary": {
                "total_failed_runs": failed_runs.count(),
                "analyzed_runs": len(analyses),
                "root_cause_distribution": dict(cause_counts)
            },
            "analyses": analyses[:20],  # Return top 20
            "common_recommendations": RootCauseAnalyzer._get_common_recommendations(analyses)
        }
    
    @staticmethod
    def _get_common_recommendations(
        analyses: List[Dict[str, Any]]
    ) -> List[str]:
        """Get common recommendations across analyses"""
        all_recommendations = []
        
        for analysis in analyses:
            all_recommendations.extend(analysis.get("recommendations", []))
        
        # Count recommendation frequency
        rec_counts = defaultdict(int)
        for rec in all_recommendations:
            rec_counts[rec] += 1
        
        # Return most common recommendations
        sorted_recs = sorted(
            rec_counts.items(),
            key=lambda x: x[1],
            reverse=True
        )[:5]
        
        return [rec for rec, count in sorted_recs]

