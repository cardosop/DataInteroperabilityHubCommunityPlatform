"""
Search Service

Service layer for search operations.
Extracts search logic from search_engine.py module.
"""
from typing import Dict, List, Any, Optional, Tuple

from hub.apps.core.services.base import BaseService
from hub.apps.search.search_engine import SearchEngine


class SearchService(BaseService):
    """
    Service for search operations.
    
    Provides business logic for:
    - Full-text search with relevance ranking
    - Search filtering
    - Search analytics
    """
    
    service_name = "search_service"
    
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
        weights: Optional[Dict[str, float]] = None
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
            
        Returns:
            Tuple of (results list, total count)
        """
        return self.execute_with_metrics(
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

