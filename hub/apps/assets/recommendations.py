"""
Asset Recommendations

Recommendation algorithms based on usage patterns, lineage relationships, and user behavior.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import structlog
from django.db.models import F

from hub.apps.contracts.models import Contract
from hub.apps.search.models import SearchAnalytics

from .models import Asset, AssetStatus

logger = structlog.get_logger(__name__)


class AssetRecommendationService:
    """
    Service for generating asset recommendations.
    """

    @staticmethod
    def get_recommendations(
        tenant_id: str,
        user_id: str | None = None,
        asset_id: str | None = None,
        limit: int = 10,
        include_usage_patterns: bool = True,
        include_lineage: bool = True,
        include_user_behavior: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Get asset recommendations.

        Args:
            tenant_id: Tenant UUID
            user_id: Optional user UUID for personalized recommendations
            asset_id: Optional asset UUID for "similar to" recommendations
            limit: Maximum number of recommendations
            include_usage_patterns: Include usage-based recommendations
            include_lineage: Include lineage-based recommendations
            include_user_behavior: Include user behavior-based recommendations

        Returns:
            List of recommended assets with scores
        """
        recommendations = []

        # Validate tenant_id is a valid UUID
        try:
            import uuid

            uuid.UUID(tenant_id)
        except (ValueError, TypeError):
            # Return empty list for invalid UUID
            return []

        # Get base assets (exclude RETIRED).
        # tenant_id was validated as a real UUID above; the queryset
        # filter construction is lazy and cannot fail at this point.
        # Any DB error during actual evaluation will surface naturally
        # from the caller's iteration of the returned recommendations.

        # Usage pattern-based recommendations
        if include_usage_patterns:
            usage_recs = AssetRecommendationService._get_usage_pattern_recommendations(
                tenant_id, limit=limit
            )
            recommendations.extend(usage_recs)

        # Lineage-based recommendations
        if include_lineage and asset_id:
            lineage_recs = AssetRecommendationService._get_lineage_recommendations(
                tenant_id, asset_id, limit=limit
            )
            recommendations.extend(lineage_recs)

        # User behavior-based recommendations
        if include_user_behavior and user_id:
            behavior_recs = AssetRecommendationService._get_user_behavior_recommendations(
                tenant_id, user_id, limit=limit
            )
            recommendations.extend(behavior_recs)

        # Aggregate and deduplicate recommendations
        aggregated = AssetRecommendationService._aggregate_recommendations(
            recommendations, limit=limit
        )

        return aggregated

    @staticmethod
    def _get_usage_pattern_recommendations(tenant_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """Get recommendations based on usage patterns"""
        recommendations = []

        # Get assets with high popularity scores
        popular_assets = Asset.objects.filter(
            tenant_id=tenant_id,
            status__in=[AssetStatus.ACTIVE, AssetStatus.PUBLIC],
            popularity_score__isnull=False,
        ).order_by("-popularity_score")[: limit * 2]

        for asset in popular_assets:
            # Calculate score based on popularity
            score = (asset.popularity_score or 0.0) / 100.0

            recommendations.append(
                {
                    "asset_id": str(asset.id),
                    "asset_name": asset.name,
                    "asset_key": asset.key,
                    "score": score,
                    "reason": "Popular asset",
                    "reason_type": "USAGE_PATTERN",
                }
            )

        # Get assets with high view/download counts
        viewed_assets = (
            Asset.objects.filter(
                tenant_id=tenant_id, status__in=[AssetStatus.ACTIVE, AssetStatus.PUBLIC]
            )
            .annotate(total_interactions=F("view_count") + F("download_count"))
            .order_by("-total_interactions")[: limit * 2]
        )

        for asset in viewed_assets:
            if asset.view_count > 0 or asset.download_count > 0:
                # Normalize score (max interactions = 1000)
                score = min(1.0, (asset.view_count + asset.download_count) / 1000.0)

                recommendations.append(
                    {
                        "asset_id": str(asset.id),
                        "asset_name": asset.name,
                        "asset_key": asset.key,
                        "score": score * 0.8,  # Slightly lower weight
                        "reason": "Frequently accessed",
                        "reason_type": "USAGE_PATTERN",
                    }
                )

        return recommendations

    @staticmethod
    def _get_lineage_recommendations(
        tenant_id: str, asset_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get recommendations based on lineage relationships"""
        recommendations = []

        try:
            source_asset = Asset.objects.get(id=asset_id, tenant_id=tenant_id)
        except Asset.DoesNotExist:
            return recommendations

        # Get contracts for source asset
        source_contracts = Contract.objects.filter(tenant_id=tenant_id, asset=source_asset)

        # Find assets with lineage relationships
        related_assets = set()

        for contract in source_contracts:
            if not contract.hub_contract_json:
                continue

            hub_contract = contract.hub_contract_json

            # Check contract-level lineage
            lineage = hub_contract.get("lineage", {})
            contracts = lineage.get("contracts", [])

            for lineage_contract in contracts:
                # Find contracts with matching namespace/name
                related_contracts = Contract.objects.filter(
                    tenant_id=tenant_id,
                    hub_contract_json__contains={"id": lineage_contract.get("name")},
                )

                for related_contract in related_contracts:
                    if related_contract.asset and related_contract.asset.id != source_asset.id:
                        related_assets.add(related_contract.asset)

            # Check model-level lineage
            models_list = hub_contract.get("models", [])
            for model in models_list:
                model_lineage = model.get("lineage", {})
                model_contracts = model_lineage.get("models", [])

                for model_contract in model_contracts:
                    related_contracts = Contract.objects.filter(
                        tenant_id=tenant_id,
                        hub_contract_json__contains={"id": model_contract.get("name")},
                    )

                    for related_contract in related_contracts:
                        if related_contract.asset and related_contract.asset.id != source_asset.id:
                            related_assets.add(related_contract.asset)

        # Create recommendations
        for asset in list(related_assets)[:limit]:
            recommendations.append(
                {
                    "asset_id": str(asset.id),
                    "asset_name": asset.name,
                    "asset_key": asset.key,
                    "score": 0.7,  # Lineage-based recommendations have medium score
                    "reason": "Related via lineage",
                    "reason_type": "LINEAGE",
                }
            )

        return recommendations

    @staticmethod
    def _get_user_behavior_recommendations(
        tenant_id: str, user_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        """Get recommendations based on user behavior"""
        recommendations = []

        # Get user's search history.
        # The queryset construction is lazy — errors surface during
        # iteration below, not here.  But Django's ORM may raise
        # ValidationError during filter kwarg type-checking for
        # malformed UUID strings.
        from django.core.exceptions import ValidationError as _DjangoValidationError

        try:
            recent_searches = SearchAnalytics.objects.filter(
                tenant_id=tenant_id, user_id=user_id
            ).order_by("-created_at")[:50]
        except (ValueError, TypeError, _DjangoValidationError) as e:
            logger.warning(
                "recommendations_user_behavior_invalid_params",
                tenant_id=str(tenant_id),
                user_id=str(user_id),
                error=str(e),
                exc_info=True,
            )
            return []

        # Extract clicked assets
        clicked_assets = {}
        for search in recent_searches:
            if search.clicked_result_id and search.clicked_result_type == "ASSET":
                asset_id = str(search.clicked_result_id)
                clicked_assets[asset_id] = clicked_assets.get(asset_id, 0) + 1

        # Get assets similar to clicked assets
        for asset_id, click_count in sorted(
            clicked_assets.items(), key=lambda x: x[1], reverse=True
        )[:5]:  # Top 5 clicked assets
            try:
                clicked_asset = Asset.objects.get(id=asset_id, tenant_id=tenant_id)

                # Find similar assets (same domain, similar name)
                # If clicked asset has a domain, find assets with same domain
                # Otherwise, find assets with similar names or any active assets
                if clicked_asset.domain:
                    similar_assets = Asset.objects.filter(
                        tenant_id=tenant_id,
                        status__in=[AssetStatus.ACTIVE, AssetStatus.PUBLIC],
                        domain=clicked_asset.domain,
                    ).exclude(id=clicked_asset.id)[:limit]
                else:
                    # If no domain, find any active assets
                    similar_assets = Asset.objects.filter(
                        tenant_id=tenant_id, status__in=[AssetStatus.ACTIVE, AssetStatus.PUBLIC]
                    ).exclude(id=clicked_asset.id)[:limit]

                for asset in similar_assets:
                    score = 0.6 * (click_count / 10.0)  # Weight by click frequency
                    recommendations.append(
                        {
                            "asset_id": str(asset.id),
                            "asset_name": asset.name,
                            "asset_key": asset.key,
                            "score": min(1.0, score),
                            "reason": f"Similar to {clicked_asset.name}",
                            "reason_type": "USER_BEHAVIOR",
                        }
                    )
            except Asset.DoesNotExist:
                continue

        # Get assets from same domain as user's searches
        search_domains = defaultdict(int)
        for search in recent_searches:
            # Extract domain from search query or filters
            filters = search.filters or {}
            domain = filters.get("domain")
            if domain:
                search_domains[domain] += 1

        for domain, search_count in sorted(
            search_domains.items(), key=lambda x: x[1], reverse=True
        )[:3]:  # Top 3 domains
            domain_assets = Asset.objects.filter(
                tenant_id=tenant_id,
                status__in=[AssetStatus.ACTIVE, AssetStatus.PUBLIC],
                domain=domain,
            )[:limit]

            for asset in domain_assets:
                score = 0.5 * (search_count / 20.0)  # Weight by search frequency
                recommendations.append(
                    {
                        "asset_id": str(asset.id),
                        "asset_name": asset.name,
                        "asset_key": asset.key,
                        "score": min(1.0, score),
                        "reason": f"Popular in {domain} domain",
                        "reason_type": "USER_BEHAVIOR",
                    }
                )

        return recommendations

    @staticmethod
    def _aggregate_recommendations(
        recommendations: list[dict[str, Any]], limit: int = 10
    ) -> list[dict[str, Any]]:
        """Aggregate and deduplicate recommendations"""
        aggregated = defaultdict(lambda: {"scores": [], "reasons": []})

        for rec in recommendations:
            asset_id = rec["asset_id"]
            aggregated[asset_id]["asset_id"] = asset_id
            aggregated[asset_id]["asset_name"] = rec["asset_name"]
            aggregated[asset_id]["asset_key"] = rec["asset_key"]
            aggregated[asset_id]["scores"].append(rec["score"])
            aggregated[asset_id]["reasons"].append(
                {"reason": rec["reason"], "type": rec["reason_type"]}
            )

        # Calculate final scores (average with slight boost for multiple reasons)
        final_recommendations = []
        for asset_id, data in aggregated.items():
            scores = data["scores"]
            avg_score = sum(scores) / len(scores) if scores else 0.0
            # Boost score if multiple recommendation types
            boost = min(0.2, len(set(r["type"] for r in data["reasons"])) * 0.05)
            final_score = min(1.0, avg_score + boost)

            final_recommendations.append(
                {
                    "asset_id": data["asset_id"],
                    "asset_name": data["asset_name"],
                    "asset_key": data["asset_key"],
                    "score": round(final_score, 3),
                    "reasons": data["reasons"],
                }
            )

        # Sort by score and return top N
        final_recommendations.sort(key=lambda x: x["score"], reverse=True)
        return final_recommendations[:limit]
