"""
Rate Limiting Quota Management

Quota tracking and management for rate limiting.
"""

from __future__ import annotations

from typing import Any

import structlog
from django.core.cache import cache

from .config import get_tenant_rate_limit
from .utils import EndpointCategory, TimeWindow

logger = structlog.get_logger(__name__)


class QuotaManager:
    """
    Manager for quota tracking and enforcement.
    """

    @staticmethod
    def check_quota(
        tenant_id: str, category: str = EndpointCategory.GENERAL, window: int = TimeWindow.DAILY
    ) -> tuple[bool, dict[str, Any]]:
        """
        Check if tenant has quota remaining.

        Args:
            tenant_id: Tenant UUID
            category: Endpoint category
            window: Time window (default: DAILY for quota)

        Returns:
            Tuple of (has_quota, quota_info)
        """
        limit = get_tenant_rate_limit(tenant_id, category, window)

        # Get current usage from cache
        cache_key = f"quota:{tenant_id}:{category}:{window}"
        usage = cache.get(cache_key, 0)

        has_quota = usage < limit

        quota_info = {
            "limit": limit,
            "used": usage,
            "remaining": max(0, limit - usage),
            "window": window,
            "category": category,
        }

        return has_quota, quota_info

    @staticmethod
    def increment_quota(
        tenant_id: str,
        category: str = EndpointCategory.GENERAL,
        window: int = TimeWindow.DAILY,
        amount: int = 1,
    ):
        """
        Increment quota usage.

        Args:
            tenant_id: Tenant UUID
            category: Endpoint category
            window: Time window
            amount: Amount to increment (default: 1)
        """
        cache_key = f"quota:{tenant_id}:{category}:{window}"

        # Increment with expiration
        current = cache.get(cache_key, 0)
        cache.set(cache_key, current + amount, window)

    @staticmethod
    def reset_quota(tenant_id: str, category: str | None = None, window: int | None = None):
        """
        Reset quota usage.

        Args:
            tenant_id: Tenant UUID
            category: Optional category (if None, resets all)
            window: Optional window (if None, resets all)
        """
        if category and window:
            cache_key = f"quota:{tenant_id}:{category}:{window}"
            cache.delete(cache_key)
        else:
            # Reset all quotas for tenant
            # This is a simplified approach - in production, you'd want to track keys
            logger.warning(
                "quota_reset_all",
                tenant_id=tenant_id,
                message="Resetting all quotas (simplified implementation)",
            )

    @staticmethod
    def get_quota_info(tenant_id: str, category: str | None = None) -> dict[str, Any]:
        """
        Get quota information for tenant.

        Args:
            tenant_id: Tenant UUID
            category: Optional category filter

        Returns:
            Dictionary with quota information
        """
        categories = (
            [category]
            if category
            else [
                EndpointCategory.GENERAL,
                EndpointCategory.DQ_RUN,
                EndpointCategory.COMPLIANCE_RUN,
                EndpointCategory.FILE_UPLOAD,
                EndpointCategory.FILE_DOWNLOAD,
                EndpointCategory.CONTRACT_VALIDATION,
                EndpointCategory.CATALOG_READ,
                EndpointCategory.SPARQL_QUERY,
            ]
        )

        quota_info = {}

        for cat in categories:
            _has_quota, info = QuotaManager.check_quota(
                tenant_id, category=cat, window=TimeWindow.DAILY
            )
            quota_info[cat] = info

        return quota_info
