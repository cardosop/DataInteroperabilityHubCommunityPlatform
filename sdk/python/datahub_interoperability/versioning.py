"""
Versioning operations for DataHub SDK.

Provides methods for querying version history, schema evolution, time-travel queries, and version comparison.
"""
from typing import Dict, Any, Optional
from .client import DataHubClient


class VersioningAPI:
    """
    Versioning API.

    Provides methods for dataset version management and queries.
    """

    def __init__(self, client: DataHubClient):
        """
        Initialize Versioning API.

        Args:
            client: DataHub client instance
        """
        self.client = client

    async def get_version_history(
        self,
        dataset_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Get version history for dataset.

        Args:
            dataset_id: Dataset UUID
            page: Page number (default: 1)
            page_size: Items per page (default: 50)

        Returns:
            Paginated response with version history
        """
        params = {
            "page": page,
            "page_size": page_size,
        }
        return await self.client.get(f"datasets/{dataset_id}/versions/", params=params)

    async def get_version(
        self,
        dataset_id: str,
        version_id: str,
    ) -> Dict[str, Any]:
        """
        Get specific version details.

        Args:
            dataset_id: Dataset UUID
            version_id: Version UUID

        Returns:
            Version data
        """
        return await self.client.get(f"datasets/{dataset_id}/versions/{version_id}/")

    async def get_schema_evolution(
        self,
        dataset_id: str,
        from_version_id: Optional[str] = None,
        to_version_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Get schema evolution between versions.

        Args:
            dataset_id: Dataset UUID
            from_version_id: Source version ID (optional, defaults to previous version)
            to_version_id: Target version ID (optional, defaults to current version)

        Returns:
            Schema evolution data with changes
        """
        params: Dict[str, Any] = {}
        if from_version_id:
            params["from_version_id"] = from_version_id
        if to_version_id:
            params["to_version_id"] = to_version_id

        return await self.client.get(f"datasets/{dataset_id}/schema-evolution/", params=params)

    async def time_travel_query(
        self,
        dataset_id: str,
        timestamp: Optional[str] = None,
        version_number: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Time-travel query to get dataset state at specific time or version.

        Args:
            dataset_id: Dataset UUID
            timestamp: ISO 8601 timestamp (optional)
            version_number: Version number (optional)

        Returns:
            Dataset state at specified time/version

        Note:
            Either timestamp or version_number must be provided.
        """
        params: Dict[str, Any] = {}
        if timestamp:
            params["timestamp"] = timestamp
        if version_number is not None:
            params["version_number"] = version_number

        return await self.client.get(f"datasets/{dataset_id}/time-travel/", params=params)

    async def compare_versions(
        self,
        dataset_id: str,
        version1_id: str,
        version2_id: str,
    ) -> Dict[str, Any]:
        """
        Compare two versions of a dataset.

        Args:
            dataset_id: Dataset UUID
            version1_id: First version UUID
            version2_id: Second version UUID

        Returns:
            Comparison data with schema and data differences
        """
        params = {
            "version1_id": version1_id,
            "version2_id": version2_id,
        }
        return await self.client.get(f"datasets/{dataset_id}/compare/", params=params)

