"""
Search operations for DataHub SDK.

Provides methods for full-text search, search suggestions, and search analytics.
"""

from typing import Any, Dict, Optional

from .client import DataHubClient


class SearchAPI:
    """
    Search API.

    Provides methods for searching contracts, assets, and datasets.
    """

    def __init__(self, client: DataHubClient):
        """
        Initialize Search API.

        Args:
            client: DataHub client instance
        """
        self.client = client

    async def search(
        self,
        query: str,
        type: Optional[str] = None,
        classification: Optional[str] = None,
        owner: Optional[str] = None,
        tags: Optional[str] = None,
        domain: Optional[str] = None,
        quality_status: Optional[str] = None,
        compliance_status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        sort_by: str = "relevance",
        sort_order: str = "desc",
    ) -> Dict[str, Any]:
        """
        Full-text search across contracts and assets.

        Args:
            query: Search query string
            type: Filter by type (contract, asset, dataset)
            classification: Filter by data classification
            owner: Filter by owner
            tags: Filter by tags
            domain: Filter by domain
            quality_status: Filter by quality status
            compliance_status: Filter by compliance status
            limit: Maximum results (default: 50)
            offset: Result offset (default: 0)
            sort_by: Sort field (default: relevance)
            sort_order: Sort order - "asc" or "desc" (default: desc)

        Returns:
            Search results
        """
        params: Dict[str, Any] = {
            "q": query,
            "limit": limit,
            "offset": offset,
            "sort_by": sort_by,
            "sort_order": sort_order,
        }
        if type:
            params["type"] = type.upper()
        if classification:
            params["classification"] = classification
        if owner:
            params["owner"] = owner
        if tags:
            params["tags"] = tags
        if domain:
            params["domain"] = domain
        if quality_status:
            params["quality_status"] = quality_status
        if compliance_status:
            params["compliance_status"] = compliance_status

        return await self.client.get("search/search/", params=params)

    async def get_suggestions(
        self,
        query: str,
        limit: int = 10,
    ) -> Dict[str, Any]:
        """
        Get search suggestions/autocomplete.

        Args:
            query: Search query string
            limit: Maximum suggestions (default: 10)

        Returns:
            Search suggestions
        """
        params = {
            "q": query,
            "limit": limit,
        }
        result = await self.client.get("search/suggestions/", params=params)
        # API returns a bare list; wrap it in a dict for a stable interface.
        if isinstance(result, list):
            return {"suggestions": result}
        return result

    async def get_analytics(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get search analytics.

        Args:
            start_date: Start date (ISO 8601, optional)
            end_date: End date (ISO 8601, optional)

        Returns:
            Search analytics data
        """
        params: Dict[str, Any] = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        return await self.client.get("search/analytics/", params=params)
