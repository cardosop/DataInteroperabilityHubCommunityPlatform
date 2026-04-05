"""
Cache Warming Utilities

Utilities for warming cache with frequently accessed resources.
"""
from typing import List, Optional, Dict, Any
from django.core.cache import cache
from django.conf import settings
import structlog

logger = structlog.get_logger(__name__)

# Import caching modules
try:
    from hub.apps.assets.caching import (
        hash_filters,
        cache_asset_list,
        CACHE_TTL_ASSET_LIST,
    )
    ASSETS_AVAILABLE = True
except ImportError:
    ASSETS_AVAILABLE = False
    logger.warning("Asset caching module not available")

try:
    from hub.apps.contracts.caching import (
        get_query_result_cache_key,
        cache_query_result,
        CACHE_TTL_QUERY_RESULT,
    )
    from hub.apps.contracts.models import Contract
    CONTRACTS_AVAILABLE = True
except ImportError:
    CONTRACTS_AVAILABLE = False
    logger.warning("Contract caching module not available")

try:
    from hub.apps.marketplace.caching import (
        hash_filters as marketplace_hash_filters,
        cache_marketplace_list,
        CACHE_TTL_MARKETPLACE_LIST,
    )
    from hub.apps.marketplace.models import Listing
    MARKETPLACE_AVAILABLE = True
except ImportError:
    MARKETPLACE_AVAILABLE = False
    logger.warning("Marketplace caching module not available")


def warm_asset_list_cache(tenant_id: str, common_filters: Optional[List[Dict[str, Any]]] = None) -> int:
    """
    Warm asset list cache for a tenant.

    Args:
        tenant_id: Tenant UUID string
        common_filters: List of common filter combinations to warm (default: empty filters)

    Returns:
        Number of cache entries warmed
    """
    if not ASSETS_AVAILABLE:
        logger.warning("Asset caching not available, skipping asset list cache warming")
        return 0

    warmed_count = 0

    # Default filters to warm (most common queries)
    if common_filters is None:
        common_filters = [
            {},  # No filters (all assets)
            {'status': 'ACTIVE'},  # Active assets
            {'status': 'DRAFT'},  # Draft assets
        ]

    try:
        from hub.apps.assets.models import Asset
        from hub.apps.assets.serializers import AssetSerializer
        from rest_framework.request import Request
        from django.test import RequestFactory

        # Create a mock request for serialization
        factory = RequestFactory()
        mock_request = factory.get('/api/v1/assets/')

        for filters in common_filters:
            try:
                # Build queryset with filters
                queryset = Asset.objects.filter(tenant_id=tenant_id)

                # Apply filters
                if 'status' in filters:
                    queryset = queryset.filter(status=filters['status'])
                if 'domain' in filters:
                    queryset = queryset.filter(domain=filters['domain'])

                # Get results (limit to first page for warming)
                assets = queryset[:50]  # Warm first page

                # Serialize results
                serializer = AssetSerializer(assets, many=True, context={'request': mock_request})
                results = serializer.data
                total_count = queryset.count()

                # Generate filters hash
                filters_hash = hash_filters(filters)

                # Cache the results
                cache_asset_list(tenant_id, filters_hash, results, total_count)
                warmed_count += 1

                logger.debug(
                    "asset_list_cache_warmed",
                    tenant_id=tenant_id,
                    filters=filters,
                    filters_hash=filters_hash,
                    result_count=len(results),
                    total_count=total_count
                )
            except Exception as e:
                logger.warning(
                    "asset_list_cache_warming_error",
                    tenant_id=tenant_id,
                    filters=filters,
                    error=str(e),
                    message="Failed to warm asset list cache for filters"
                )

    except Exception as e:
        logger.error(
            "asset_list_cache_warming_failed",
            tenant_id=tenant_id,
            error=str(e),
            message="Failed to warm asset list cache"
        )

    return warmed_count


def warm_contract_list_cache(tenant_id: str, common_filters: Optional[List[Dict[str, Any]]] = None) -> int:
    """
    Warm contract list cache for a tenant.

    Args:
        tenant_id: Tenant UUID string
        common_filters: List of common filter combinations to warm (default: empty filters)

    Returns:
        Number of cache entries warmed
    """
    if not CONTRACTS_AVAILABLE:
        logger.warning("Contract caching not available, skipping contract list cache warming")
        return 0

    warmed_count = 0

    # Default filters to warm (most common queries)
    if common_filters is None:
        common_filters = [
            {},  # No filters (all contracts)
            {'status': 'ACTIVE'},  # Active contracts
            {'status': 'VALID'},  # Valid contracts
        ]

    try:
        from hub.apps.contracts.serializers import ContractSerializer
        from rest_framework.request import Request
        from django.test import RequestFactory

        # Create a mock request for serialization
        factory = RequestFactory()
        mock_request = factory.get('/api/v1/contracts/')

        for filters in common_filters:
            try:
                # Build queryset with filters
                queryset = Contract.objects.filter(tenant_id=tenant_id)

                # Apply filters
                if 'status' in filters:
                    queryset = queryset.filter(status=filters['status'])
                if 'validation_status' in filters:
                    queryset = queryset.filter(validation_status=filters['validation_status'])

                # Get results (limit to first page for warming)
                contracts = queryset[:50]  # Warm first page

                # Serialize results
                serializer = ContractSerializer(contracts, many=True, context={'request': mock_request})
                results = serializer.data
                total_count = queryset.count()

                # Cache the results
                cache_query_result(filters, tenant_id, results, total_count)
                warmed_count += 1

                logger.debug(
                    "contract_list_cache_warmed",
                    tenant_id=tenant_id,
                    filters=filters,
                    result_count=len(results),
                    total_count=total_count
                )
            except Exception as e:
                logger.warning(
                    "contract_list_cache_warming_error",
                    tenant_id=tenant_id,
                    filters=filters,
                    error=str(e),
                    message="Failed to warm contract list cache for filters"
                )

    except Exception as e:
        logger.error(
            "contract_list_cache_warming_failed",
            tenant_id=tenant_id,
            error=str(e),
            message="Failed to warm contract list cache"
        )

    return warmed_count


def warm_marketplace_listings_cache(common_filters: Optional[List[Dict[str, Any]]] = None) -> int:
    """
    Warm marketplace listings cache.

    Args:
        common_filters: List of common filter combinations to warm (default: empty filters)

    Returns:
        Number of cache entries warmed
    """
    if not MARKETPLACE_AVAILABLE:
        logger.warning("Marketplace caching not available, skipping marketplace cache warming")
        return 0

    warmed_count = 0

    # Default filters to warm (most common queries)
    if common_filters is None:
        common_filters = [
            {},  # No filters (all published listings)
            {'category': 'data'},  # Data listings
            {'pricing_model': 'FREE'},  # Free listings
        ]

    try:
        from hub.apps.marketplace.models import ListingStatus
        from hub.apps.marketplace.serializers import ListingSerializer
        from rest_framework.request import Request
        from django.test import RequestFactory

        # Create a mock request for serialization
        factory = RequestFactory()
        mock_request = factory.get('/api/v1/marketplace/listings/')

        for filters in common_filters:
            try:
                # Build queryset with filters (only published listings)
                queryset = Listing.objects.filter(status=ListingStatus.PUBLISHED)

                # Apply filters
                if 'category' in filters:
                    queryset = queryset.filter(asset__domain=filters['category'])
                if 'pricing_model' in filters:
                    queryset = queryset.filter(pricing_model=filters['pricing_model'])

                # Get results (limit to first page for warming)
                listings = queryset[:50]  # Warm first page

                # Serialize results
                serializer = ListingSerializer(listings, many=True, context={'request': mock_request})
                results = serializer.data
                total_count = queryset.count()

                # Generate filters hash
                filters_hash = marketplace_hash_filters(filters)

                # Cache the results
                cache_marketplace_list(filters_hash, results, total_count)
                warmed_count += 1

                logger.debug(
                    "marketplace_listings_cache_warmed",
                    filters=filters,
                    filters_hash=filters_hash,
                    result_count=len(results),
                    total_count=total_count
                )
            except Exception as e:
                logger.warning(
                    "marketplace_listings_cache_warming_error",
                    filters=filters,
                    error=str(e),
                    message="Failed to warm marketplace listings cache for filters"
                )

    except Exception as e:
        logger.error(
            "marketplace_listings_cache_warming_failed",
            error=str(e),
            message="Failed to warm marketplace listings cache"
        )

    return warmed_count


def warm_tenant_cache(tenant_id: str) -> Dict[str, int]:
    """
    Warm all caches for a tenant.

    Args:
        tenant_id: Tenant UUID string

    Returns:
        Dictionary with counts of warmed cache entries per resource type
    """
    results = {
        'assets': 0,
        'contracts': 0,
        'marketplace': 0,
    }

    logger.info(
        "cache_warming_started",
        tenant_id=tenant_id,
        message="Starting cache warming for tenant"
    )

    # Warm asset list cache
    try:
        results['assets'] = warm_asset_list_cache(tenant_id)
    except Exception as e:
        logger.error(
            "cache_warming_asset_error",
            tenant_id=tenant_id,
            error=str(e),
            message="Failed to warm asset cache"
        )

    # Warm contract list cache
    try:
        results['contracts'] = warm_contract_list_cache(tenant_id)
    except Exception as e:
        logger.error(
            "cache_warming_contract_error",
            tenant_id=tenant_id,
            error=str(e),
            message="Failed to warm contract cache"
        )

    # Warm marketplace listings (not tenant-specific)
    try:
        results['marketplace'] = warm_marketplace_listings_cache()
    except Exception as e:
        logger.error(
            "cache_warming_marketplace_error",
            tenant_id=tenant_id,
            error=str(e),
            message="Failed to warm marketplace cache"
        )

    logger.info(
        "cache_warming_completed",
        tenant_id=tenant_id,
        assets_warmed=results['assets'],
        contracts_warmed=results['contracts'],
        marketplace_warmed=results['marketplace'],
        message="Cache warming completed for tenant"
    )

    return results


def warm_all_tenants_cache() -> Dict[str, Any]:
    """
    Warm caches for all tenants.

    Returns:
        Dictionary with summary of cache warming results
    """
    from hub.apps.tenants.models import Tenant

    logger.info("cache_warming_all_tenants_started", message="Starting cache warming for all tenants")

    tenants = Tenant.objects.all()
    total_tenants = tenants.count()
    successful = 0
    failed = 0
    results_by_tenant = {}

    for tenant in tenants:
        tenant_id = str(tenant.id)
        try:
            results = warm_tenant_cache(tenant_id)
            results_by_tenant[tenant_id] = results
            successful += 1
        except Exception as e:
            logger.error(
                "cache_warming_tenant_failed",
                tenant_id=tenant_id,
                error=str(e),
                message="Failed to warm cache for tenant"
            )
            failed += 1

    summary = {
        'total_tenants': total_tenants,
        'successful': successful,
        'failed': failed,
        'results_by_tenant': results_by_tenant
    }

    logger.info(
        "cache_warming_all_tenants_completed",
        total_tenants=total_tenants,
        successful=successful,
        failed=failed,
        message="Cache warming completed for all tenants"
    )

    return summary

