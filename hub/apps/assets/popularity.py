"""
Asset Popularity Metrics

Tracking and calculation of asset popularity based on views, downloads, and usage frequency.
"""

from __future__ import annotations

from datetime import timedelta

import structlog
from django.db.models import F
from django.utils import timezone

from hub.apps.search.models import SearchAnalytics

from .models import Asset, AssetStatus

logger = structlog.get_logger(__name__)


class AssetPopularityService:
    """
    Service for tracking and calculating asset popularity.
    """

    @staticmethod
    def track_view(asset_id: str, tenant_id: str) -> None:
        """
        Track an asset view.

        Args:
            asset_id: Asset UUID
            tenant_id: Tenant UUID
        """
        try:
            # Use update to atomically increment
            Asset.objects.filter(id=asset_id, tenant_id=tenant_id).update(
                view_count=F("view_count") + 1
            )

            # Get updated asset and recalculate popularity score
            asset = Asset.objects.get(id=asset_id, tenant_id=tenant_id)
            AssetPopularityService.calculate_popularity_score(asset)
        except Asset.DoesNotExist:
            logger.warning(
                "Asset not found for view tracking", asset_id=asset_id, tenant_id=tenant_id
            )

    @staticmethod
    def track_download(asset_id: str, tenant_id: str) -> None:
        """
        Track an asset download.

        Args:
            asset_id: Asset UUID
            tenant_id: Tenant UUID
        """
        try:
            # Use update to atomically increment
            Asset.objects.filter(id=asset_id, tenant_id=tenant_id).update(
                download_count=F("download_count") + 1
            )

            # Get updated asset and recalculate popularity score
            asset = Asset.objects.get(id=asset_id, tenant_id=tenant_id)
            AssetPopularityService.calculate_popularity_score(asset)
        except Asset.DoesNotExist:
            logger.warning(
                "Asset not found for download tracking", asset_id=asset_id, tenant_id=tenant_id
            )

    @staticmethod
    def track_usage_frequency(asset_id: str, tenant_id: str) -> None:
        """
        Track asset usage frequency (e.g., from search clicks, API access).

        Args:
            asset_id: Asset UUID
            tenant_id: Tenant UUID
        """
        # Usage frequency is tracked through views and downloads
        # This method can be extended for additional usage tracking
        AssetPopularityService.track_view(asset_id, tenant_id)

    @staticmethod
    def track_user_engagement(asset_id: str, tenant_id: str, user_id: str | None = None) -> None:
        """
        Track user engagement with an asset.

        Args:
            asset_id: Asset UUID
            tenant_id: Tenant UUID
            user_id: Optional user UUID
        """
        # Track as view
        AssetPopularityService.track_view(asset_id, tenant_id)

        # Additional engagement tracking can be added here
        # (e.g., time spent, interactions, etc.)

    @staticmethod
    def calculate_popularity_score(asset: Asset) -> float:
        """
        Calculate popularity score for an asset.

        Args:
            asset: Asset instance

        Returns:
            Popularity score (0-100)
        """
        # Refresh from database to get latest counts
        asset.refresh_from_db()

        # Base score from view and download counts
        view_score = min(50.0, asset.view_count * 0.1)  # Max 50 points from views
        download_score = min(40.0, asset.download_count * 2.0)  # Max 40 points from downloads

        # Recency bonus (recent views/downloads weighted more)
        recency_bonus = AssetPopularityService._calculate_recency_bonus(asset)

        # Status bonus
        status_bonus = 0.0
        if asset.status == AssetStatus.PUBLIC:
            status_bonus = 5.0
        elif asset.status == AssetStatus.ACTIVE:
            status_bonus = 2.0

        # Calculate total score
        total_score = view_score + download_score + recency_bonus + status_bonus

        # Normalize to 0-100
        popularity_score = min(100.0, total_score)

        # Update asset
        asset.popularity_score = popularity_score
        asset.save(update_fields=["popularity_score", "updated_at"])

        return popularity_score

    @staticmethod
    def _calculate_recency_bonus(asset: Asset) -> float:
        """Calculate bonus for recent activity"""
        # Get recent search clicks for this asset
        recent_clicks = SearchAnalytics.objects.filter(
            tenant=asset.tenant,
            clicked_result_id=asset.id,
            clicked_result_type="ASSET",
            clicked_at__gte=timezone.now() - timedelta(days=7),
        ).count()

        # Bonus: 1 point per recent click (max 5 points)
        return min(5.0, recent_clicks * 0.5)

    @staticmethod
    def recalculate_all_popularity_scores(tenant_id: str) -> int:
        """
        Recalculate popularity scores for all assets in a tenant.

        Args:
            tenant_id: Tenant UUID

        Returns:
            Number of assets updated
        """
        assets = Asset.objects.filter(tenant_id=tenant_id)
        count = 0

        for asset in assets:
            AssetPopularityService.calculate_popularity_score(asset)
            count += 1

        logger.info("Recalculated popularity scores", tenant_id=tenant_id, count=count)

        return count
