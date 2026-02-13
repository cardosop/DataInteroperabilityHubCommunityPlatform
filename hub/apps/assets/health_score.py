"""
Asset Health Score

Calculation of asset health score combining DQ, compliance, freshness, and usage metrics.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, Optional

import structlog
from django.db.models import Q
from django.utils import timezone

from hub.apps.datasets.models import Dataset
from hub.apps.dq.models import DQRun, DQRunStatus

from .models import Asset, AssetStatus, ComplianceStatus, DQStatus

# Import observability model if available
try:
    from hub.apps.observability.models import DataObservabilityMetric
except ImportError:
    DataObservabilityMetric = None

logger = structlog.get_logger(__name__)


class AssetHealthScoreService:
    """
    Service for calculating asset health scores.
    """

    # Weight configuration
    DQ_WEIGHT = 0.35
    COMPLIANCE_WEIGHT = 0.25
    FRESHNESS_WEIGHT = 0.20
    USAGE_WEIGHT = 0.20

    @staticmethod
    def calculate_health_score(asset: Asset) -> float:
        """
        Calculate health score for an asset.

        Combines:
        - DQ status (35%)
        - Compliance status (25%)
        - Freshness (20%)
        - Usage metrics (20%)

        Args:
            asset: Asset instance

        Returns:
            Health score (0-100)
        """
        # Calculate component scores
        dq_score = AssetHealthScoreService._calculate_dq_score(asset)
        compliance_score = AssetHealthScoreService._calculate_compliance_score(asset)
        freshness_score = AssetHealthScoreService._calculate_freshness_score(asset)
        usage_score = AssetHealthScoreService._calculate_usage_score(asset)

        # Weighted combination
        health_score = (
            dq_score * AssetHealthScoreService.DQ_WEIGHT
            + compliance_score * AssetHealthScoreService.COMPLIANCE_WEIGHT
            + freshness_score * AssetHealthScoreService.FRESHNESS_WEIGHT
            + usage_score * AssetHealthScoreService.USAGE_WEIGHT
        )

        # Normalize to 0-100
        health_score = max(0.0, min(100.0, health_score))

        # Update asset (use update() to avoid triggering signals/validation that might hang)
        # This is a performance optimization and prevents potential deadlocks
        Asset.objects.filter(id=asset.id).update(
            health_score=health_score,
            updated_at=timezone.now()
        )
        # Refresh the instance to reflect the update
        asset.refresh_from_db()
        asset.health_score = health_score

        return health_score

    @staticmethod
    def _calculate_dq_score(asset: Asset) -> float:
        """Calculate DQ component score"""
        # DQ status scoring
        if asset.dq_status == DQStatus.PASS:
            base_score = 100.0
        elif asset.dq_status == DQStatus.WARN:
            base_score = 70.0
        elif asset.dq_status == DQStatus.FAIL:
            base_score = 30.0
        else:  # UNKNOWN
            base_score = 50.0

        # Get latest DQ run quality score if available
        # Only query if asset has a tenant (required for filtering)
        latest_dq_run = None
        if asset.tenant:
            latest_dq_run = (
                DQRun.objects.filter(tenant=asset.tenant, asset=asset, status=DQRunStatus.SUCCEEDED)
                .order_by("-completed_at")
                .first()
            )

        if latest_dq_run and latest_dq_run.quality_score is not None:
            # Blend status-based score with actual quality score
            quality_score = latest_dq_run.quality_score
            # Weight: 60% status, 40% quality score
            dq_score = (base_score * 0.6) + (quality_score * 0.4)
        else:
            dq_score = base_score

        return dq_score

    @staticmethod
    def _calculate_compliance_score(asset: Asset) -> float:
        """Calculate compliance component score"""
        if asset.compliance_status == ComplianceStatus.PASS:
            return 100.0
        elif asset.compliance_status == ComplianceStatus.WARN:
            return 70.0
        elif asset.compliance_status == ComplianceStatus.FAIL:
            return 30.0
        else:  # UNKNOWN
            return 50.0

    @staticmethod
    def _calculate_freshness_score(asset: Asset) -> float:
        """Calculate freshness component score"""
        # Get latest dataset
        dataset = asset.datasets.order_by("-created_at").first()

        if not dataset:
            # No dataset = no freshness data
            return 50.0

        # Get freshness metrics (if observability model is available)
        freshness_metric = None
        if DataObservabilityMetric and asset.tenant:
            # DataObservabilityMetric doesn't have metric_type field
            # Filter by tenant and asset, and check for freshness data
            freshness_metric = (
                DataObservabilityMetric.objects.filter(
                    tenant=asset.tenant,
                    asset=asset,
                    freshness_age_seconds__isnull=False  # Has freshness data
                )
                .order_by("-recorded_at")
                .first()
            )

        if freshness_metric and freshness_metric.freshness_age_seconds is not None:
            # Extract freshness age from metric (convert seconds to hours)
            freshness_age_hours = freshness_metric.freshness_age_seconds / 3600.0

            # Score based on freshness age
            # 0-24 hours: 100
            # 24-48 hours: 80
            # 48-72 hours: 60
            # 72-96 hours: 40
            # >96 hours: 20
            if freshness_age_hours <= 24:
                return 100.0
            elif freshness_age_hours <= 48:
                return 80.0
            elif freshness_age_hours <= 72:
                return 60.0
            elif freshness_age_hours <= 96:
                return 40.0
            else:
                return 20.0

        # Fallback: use dataset creation time
        dataset_age_hours = (timezone.now() - dataset.created_at).total_seconds() / 3600

        if dataset_age_hours <= 24:
            return 100.0
        elif dataset_age_hours <= 48:
            return 80.0
        elif dataset_age_hours <= 72:
            return 60.0
        elif dataset_age_hours <= 96:
            return 40.0
        else:
            return 20.0

    @staticmethod
    def _calculate_usage_score(asset: Asset) -> float:
        """Calculate usage component score"""
        # Base score from popularity
        if asset.popularity_score is not None:
            return asset.popularity_score

        # Fallback: calculate from view/download counts
        total_interactions = asset.view_count + asset.download_count

        if total_interactions == 0:
            return 50.0  # Neutral score for no usage

        # Normalize: 100 interactions = 100 score
        usage_score = min(100.0, (total_interactions / 100.0) * 100.0)

        return usage_score

    @staticmethod
    def recalculate_all_health_scores(tenant_id: str) -> int:
        """
        Recalculate health scores for all assets in a tenant.

        Args:
            tenant_id: Tenant UUID

        Returns:
            Number of assets updated
        """
        assets = Asset.objects.filter(tenant_id=tenant_id)
        count = 0

        for asset in assets:
            AssetHealthScoreService.calculate_health_score(asset)
            count += 1

        logger.info("Recalculated health scores", tenant_id=tenant_id, count=count)

        return count

    @staticmethod
    def get_health_score_breakdown(asset: Asset) -> Dict[str, Any]:
        """
        Get detailed breakdown of health score components.

        Args:
            asset: Asset instance

        Returns:
            Dictionary with component scores and breakdown
        """
        dq_score = AssetHealthScoreService._calculate_dq_score(asset)
        compliance_score = AssetHealthScoreService._calculate_compliance_score(asset)
        freshness_score = AssetHealthScoreService._calculate_freshness_score(asset)
        usage_score = AssetHealthScoreService._calculate_usage_score(asset)

        total_score = AssetHealthScoreService.calculate_health_score(asset)

        return {
            "total_score": round(total_score, 2),
            "components": {
                "dq": {
                    "score": round(dq_score, 2),
                    "weight": AssetHealthScoreService.DQ_WEIGHT,
                    "weighted_score": round(dq_score * AssetHealthScoreService.DQ_WEIGHT, 2),
                    "status": asset.dq_status,
                },
                "compliance": {
                    "score": round(compliance_score, 2),
                    "weight": AssetHealthScoreService.COMPLIANCE_WEIGHT,
                    "weighted_score": round(
                        compliance_score * AssetHealthScoreService.COMPLIANCE_WEIGHT, 2
                    ),
                    "status": asset.compliance_status,
                },
                "freshness": {
                    "score": round(freshness_score, 2),
                    "weight": AssetHealthScoreService.FRESHNESS_WEIGHT,
                    "weighted_score": round(
                        freshness_score * AssetHealthScoreService.FRESHNESS_WEIGHT, 2
                    ),
                },
                "usage": {
                    "score": round(usage_score, 2),
                    "weight": AssetHealthScoreService.USAGE_WEIGHT,
                    "weighted_score": round(usage_score * AssetHealthScoreService.USAGE_WEIGHT, 2),
                    "view_count": asset.view_count,
                    "download_count": asset.download_count,
                },
            },
        }
