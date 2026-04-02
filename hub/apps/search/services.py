"""
Search Service

Service layer for search operations.
Extracts search logic from search_engine.py module.
"""
import time
from typing import Dict, List, Any, Optional, Tuple

from hub.apps.core.services.base import BaseService
from hub.apps.core.services.base import ValidationError as ServiceValidationError
from hub.apps.core.events.service_publishers import SearchEventPublisher
from hub.apps.search.business_rules import SearchBusinessRules
from hub.apps.search.search_engine import SearchEngine
from hub.apps.search.indexing import SearchIndexer
from hub.apps.search.models import SearchIndex

logger = None


def get_logger():
    """Get logger instance"""
    global logger
    if logger is None:
        import structlog
        logger = structlog.get_logger(__name__)
    return logger


class SearchService(BaseService, SearchEventPublisher):
    """
    Service for search operations.

    Provides business logic for:
    - Full-text search with relevance ranking
    - Search filtering
    - Search analytics
    - Index management with event publishing
    """

    service_name = "search_service"

    def __init__(self, tenant_id: Optional[str] = None, user_id: Optional[str] = None):
        """
        Initialize SearchService.

        Args:
            tenant_id: Optional tenant ID
            user_id: Optional user ID
        """
        # Set attributes directly (BaseService doesn't have __init__)
        self.tenant_id = tenant_id
        self.user_id = user_id
        # Initialize event publisher
        SearchEventPublisher.__init__(self, tenant_id=tenant_id, user_id=user_id)

    def search(
        self,
        tenant_id: str,
        query: str,
        resource_type: Optional[str] = None,
        classification: Optional[str] = None,
        owner_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
        domain: Optional[str] = None,
        quality_status: Optional[str] = None,
        compliance_status: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
        sort_by: str = "relevance",
        sort_order: str = "desc",
        weights: Optional[Dict[str, float]] = None,
        user_id: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Perform full-text search with filters and ranking.

        Args:
            tenant_id: Tenant UUID
            query: Search query string
            resource_type: Filter by resource type (CONTRACT, ASSET, DATASET)
            classification: Filter by classification
            owner_id: Filter by owner ID
            tags: Filter by tags (list)
            domain: Filter by domain
            quality_status: Filter by quality status
            compliance_status: Filter by compliance status
            limit: Results per page (default: 20, max: 100)
            offset: Pagination offset
            sort_by: Sort field (relevance, created_at, indexed_at)
            sort_order: Sort order (asc, desc)
            weights: Custom ranking weights
            user_id: Optional user ID for event publishing

        Returns:
            Tuple of (results list, total count)
        """
        start_time = time.time()

        # Validate query and filters via SearchBusinessRules (Phase 75.2)
        # Strip None values so the validator only sees filters that
        # were actually provided by the caller.
        raw_filters = {
            "resource_type": resource_type,
            "classification": classification,
            "owner_id": owner_id,
            "tags": tags,
            "domain": domain,
            "quality_status": quality_status,
            "compliance_status": compliance_status,
        }
        active_filters = {
            k: v for k, v in raw_filters.items() if v is not None
        }
        rules = SearchBusinessRules(
            tenant_id=tenant_id,
            user_id=user_id or self.user_id,
        )
        validation_result = rules.validate(
            query=query,
            filters=active_filters or None,
        )
        if not validation_result.is_valid:
            raise ServiceValidationError(
                "; ".join(validation_result.errors),
                code="SEARCH_VALIDATION_FAILED",
                details=validation_result.details,
            )

        # Build filters dict for event publishing
        filters = {}
        if resource_type:
            filters["resource_type"] = resource_type
        if classification:
            filters["classification"] = classification
        if owner_id:
            filters["owner_id"] = owner_id
        if tags:
            filters["tags"] = tags
        if domain:
            filters["domain"] = domain
        if quality_status:
            filters["quality_status"] = quality_status
        if compliance_status:
            filters["compliance_status"] = compliance_status

        # Determine query type
        query_type = "full_text" if query else "filter_only"

        # Perform search
        results, total = self.execute_with_metrics(
            operation="search",
            func=lambda: SearchEngine.search(
                tenant_id=tenant_id,
                query=query,
                resource_type=resource_type,
                classification=classification,
                owner_id=owner_id,
                tags=tags,
                domain=domain,
                quality_status=quality_status,
                compliance_status=compliance_status,
                limit=limit,
                offset=offset,
                sort_by=sort_by,
                sort_order=sort_order,
                weights=weights
            ),
            tenant_id=tenant_id
        )

        # Calculate execution time
        execution_time_ms = int((time.time() - start_time) * 1000)

        # Publish search.query event
        try:
            self.publish_search_query(
                query=query,
                query_type=query_type,
                filters=filters,
                result_count=total,
                no_results=(total == 0),
                execution_time_ms=execution_time_ms,
                tenant_id=tenant_id,
                user_id=user_id or self.user_id
            )
        except Exception as e:
            # Log error but don't fail search if event publishing fails
            get_logger().warning(
                "Failed to publish search.query event",
                query=query,
                tenant_id=tenant_id,
                error=str(e),
                exc_info=True
            )

        return results, total

    def update_index(
        self,
        resource_type: str,
        resource_id: str,
        tenant_id: Optional[str] = None,
        index_id: Optional[str] = None,
        title: Optional[str] = None,
        update_type: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Optional[SearchIndex]:
        """
        Update search index for a resource and publish event.

        Args:
            resource_type: Resource type (CONTRACT, ASSET, DATASET, VIRTUAL_DATASET)
            resource_id: Resource ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            index_id: Optional index ID
            title: Optional resource title
            update_type: Update type ('created', 'updated', 'deleted')
            user_id: Optional user ID for event publishing

        Returns:
            SearchIndex instance or None if indexing failed
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValueError("tenant_id is required")

        # Get the resource and index it
        search_index = None
        try:
            if resource_type == "CONTRACT":
                from hub.apps.contracts.models import Contract
                try:
                    contract = Contract.objects.get(id=resource_id, tenant_id=effective_tenant_id)
                    search_index = SearchIndexer.index_contract(contract)
                    if not title:
                        # Get title from hub_contract_json
                        if contract.hub_contract_json and isinstance(contract.hub_contract_json, dict):
                            info = contract.hub_contract_json.get("info", {})
                            if isinstance(info, dict):
                                title = info.get("title") or info.get("name")
                        if not title:
                            title = f"Contract {contract.id}"
                    if not update_type:
                        update_type = "updated"
                except Contract.DoesNotExist:
                    get_logger().warning(
                        "Contract not found for indexing",
                        resource_id=resource_id,
                        tenant_id=effective_tenant_id
                    )
                    return None

            elif resource_type == "ASSET":
                from hub.apps.assets.models import Asset
                try:
                    asset = Asset.objects.get(id=resource_id, tenant_id=effective_tenant_id)
                    search_index = SearchIndexer.index_asset(asset)
                    if not title:
                        title = asset.name or str(asset.id)
                    if not update_type:
                        update_type = "updated"
                except Asset.DoesNotExist:
                    get_logger().warning(
                        "Asset not found for indexing",
                        resource_id=resource_id,
                        tenant_id=effective_tenant_id
                    )
                    return None

            elif resource_type == "DATASET":
                from hub.apps.datasets.models import Dataset
                try:
                    dataset = Dataset.objects.get(id=resource_id, tenant_id=effective_tenant_id)
                    search_index = SearchIndexer.index_dataset(dataset)
                    if not title:
                        # Dataset doesn't have a name field, use asset name or dataset ID
                        if dataset.asset:
                            title = dataset.asset.name or str(dataset.id)
                        else:
                            title = f"Dataset {dataset.id}"
                    if not update_type:
                        update_type = "updated"
                except Dataset.DoesNotExist:
                    get_logger().warning(
                        "Dataset not found for indexing",
                        resource_id=resource_id,
                        tenant_id=effective_tenant_id
                    )
                    return None

            elif resource_type == "VIRTUAL_DATASET":
                from hub.apps.virtualization.models import VirtualDataset
                try:
                    virtual_dataset = VirtualDataset.objects.get(id=resource_id, tenant_id=effective_tenant_id)
                    search_index = SearchIndexer.index_virtual_dataset(virtual_dataset)
                    if not title:
                        title = virtual_dataset.name or str(virtual_dataset.id)
                    if not update_type:
                        update_type = "updated"
                except Exception as e:
                    get_logger().warning(
                        "VirtualDataset not found for indexing",
                        resource_id=resource_id,
                        tenant_id=effective_tenant_id,
                        error=str(e)
                    )
                    return None

            else:
                get_logger().warning(
                    "Unknown resource type for indexing",
                    resource_type=resource_type,
                    resource_id=resource_id
                )
                return None

            # Publish search.index.updated event
            if search_index:
                try:
                    self.publish_index_updated(
                        resource_type=resource_type,
                        resource_id=resource_id,
                        index_id=str(search_index.id) if search_index.id else index_id,
                        title=title or search_index.title if search_index else None,
                        update_type=update_type or "updated",
                        tenant_id=effective_tenant_id,
                        user_id=user_id or self.user_id
                    )
                except Exception as e:
                    # Log error but don't fail indexing if event publishing fails
                    get_logger().warning(
                        "Failed to publish search.index.updated event",
                        resource_type=resource_type,
                        resource_id=resource_id,
                        tenant_id=effective_tenant_id,
                        error=str(e),
                        exc_info=True
                    )

            return search_index

        except Exception as e:
            get_logger().error(
                "Failed to update search index",
                resource_type=resource_type,
                resource_id=resource_id,
                tenant_id=effective_tenant_id,
                error=str(e),
                exc_info=True
            )
            return None

    def delete_index(
        self,
        resource_type: str,
        resource_id: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> None:
        """
        Delete search index for a resource and publish event.

        Args:
            resource_type: Resource type (CONTRACT, ASSET, DATASET, VIRTUAL_DATASET)
            resource_id: Resource ID
            tenant_id: Tenant ID (uses service tenant_id if not provided)
            user_id: Optional user ID for event publishing
        """
        effective_tenant_id = tenant_id or self.tenant_id
        if not effective_tenant_id:
            raise ValueError("tenant_id is required")

        # Get index title before deletion
        try:
            index = SearchIndex.objects.get(
                tenant_id=effective_tenant_id,
                resource_type=resource_type,
                resource_id=resource_id
            )
            title = index.title
            index_id = str(index.id)
        except SearchIndex.DoesNotExist:
            title = None
            index_id = None

        # Delete index
        SearchIndexer.delete_index(
            tenant_id=effective_tenant_id,
            resource_type=resource_type,
            resource_id=resource_id
        )

        # Publish search.index.updated event with update_type='deleted'
        try:
            self.publish_index_updated(
                resource_type=resource_type,
                resource_id=resource_id,
                index_id=index_id,
                title=title,
                update_type="deleted",
                tenant_id=effective_tenant_id,
                user_id=user_id or self.user_id
            )
        except Exception as e:
            # Log error but don't fail deletion if event publishing fails
            get_logger().warning(
                "Failed to publish search.index.updated event for deletion",
                resource_type=resource_type,
                resource_id=resource_id,
                tenant_id=effective_tenant_id,
                error=str(e),
                exc_info=True
            )

    def rebuild_index(
        self,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Rebuild search index and publish event.

        Args:
            tenant_id: Optional tenant ID (rebuilds for all tenants if not provided)
            user_id: Optional user ID for event publishing

        Returns:
            Dict with rebuild results (resource_count, duration_ms, success, errors)
        """
        effective_tenant_id = tenant_id or self.tenant_id
        start_time = time.time()
        errors = []
        resource_count = 0

        try:
            # Count resources before rebuild
            from django.db.models import Q
            queryset = Q()
            if effective_tenant_id:
                queryset = Q(tenant_id=effective_tenant_id)

            from hub.apps.contracts.models import Contract
            from hub.apps.assets.models import Asset
            from hub.apps.datasets.models import Dataset

            resource_count = (
                Contract.objects.filter(queryset).count() +
                Asset.objects.filter(queryset).count() +
                Dataset.objects.filter(queryset).count()
            )

            # Try to count virtual datasets if available
            try:
                from hub.apps.virtualization.models import VirtualDataset
                resource_count += VirtualDataset.objects.filter(queryset).count()
            except ImportError:
                pass

            # Rebuild index
            SearchIndexer.rebuild_index(tenant_id=effective_tenant_id)

            # Calculate duration
            duration_ms = int((time.time() - start_time) * 1000)

            # Get resource types that were indexed
            resource_types = []
            if effective_tenant_id:
                indexed_types = SearchIndex.objects.filter(tenant_id=effective_tenant_id).values_list('resource_type', flat=True).distinct()
                resource_types = list(indexed_types)
            else:
                indexed_types = SearchIndex.objects.values_list('resource_type', flat=True).distinct()
                resource_types = list(indexed_types)

            # Publish search.index.rebuilt event
            try:
                self.publish_index_rebuilt(
                    tenant_id=effective_tenant_id,
                    resource_count=resource_count,
                    duration_ms=duration_ms,
                    resource_types=resource_types,
                    success=True,
                    errors=errors,
                    user_id=user_id or self.user_id
                )
            except Exception as e:
                # Log error but don't fail rebuild if event publishing fails
                get_logger().warning(
                    "Failed to publish search.index.rebuilt event",
                    tenant_id=effective_tenant_id,
                    error=str(e),
                    exc_info=True
                )

            return {
                "resource_count": resource_count,
                "duration_ms": duration_ms,
                "success": True,
                "errors": errors,
                "resource_types": resource_types
            }

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            error_msg = str(e)
            errors.append(error_msg)

            get_logger().error(
                "Failed to rebuild search index",
                tenant_id=effective_tenant_id,
                error=error_msg,
                exc_info=True
            )

            # Publish search.index.rebuilt event with failure
            try:
                self.publish_index_rebuilt(
                    tenant_id=effective_tenant_id,
                    resource_count=resource_count,
                    duration_ms=duration_ms,
                    resource_types=[],
                    success=False,
                    errors=errors,
                    user_id=user_id or self.user_id
                )
            except Exception as event_error:
                get_logger().warning(
                    "Failed to publish search.index.rebuilt event for failure",
                    tenant_id=effective_tenant_id,
                    error=str(event_error),
                    exc_info=True
                )

            return {
                "resource_count": resource_count,
                "duration_ms": duration_ms,
                "success": False,
                "errors": errors,
                "resource_types": []
            }

