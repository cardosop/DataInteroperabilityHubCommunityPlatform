"""
Scheduled ingestion operations for DataHub SDK.

Provides methods for managing scheduled data ingestion workflows.
"""

from typing import Any, Dict, Optional

from .client import DataHubClient


class ScheduledIngestionAPI:
    """
    Scheduled Ingestion API.

    Provides methods for creating, updating, and managing scheduled ingestion workflows.
    """

    def __init__(self, client: DataHubClient):
        """
        Initialize Scheduled Ingestion API.

        Args:
            client: DataHub client instance
        """
        self.client = client

    async def create(
        self,
        name: str,
        source_type: str,
        source_config: Dict[str, Any],
        schedule: str,
        asset_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create scheduled ingestion.

        Args:
            name: Ingestion name
            source_type: Source type (s3, gcs, azure_blob, http, ftp, database)
            source_config: Source configuration
            schedule: Cron schedule expression
            asset_id: Target asset ID
            filters: File filters (optional)
            **kwargs: Additional ingestion parameters

        Returns:
            Created scheduled ingestion data
        """
        data: Dict[str, Any] = {
            "name": name,
            "source_type": source_type,
            "source_config": source_config,
            "schedule": schedule,
        }
        if asset_id:
            data["asset_id"] = asset_id
        if filters:
            data["filters"] = filters
        data.update(kwargs)

        return await self.client.post("scheduled-ingestions/", data=data)

    async def list(
        self,
        page: int = 1,
        page_size: int = 50,
        status: Optional[str] = None,
        asset_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List scheduled ingestions.

        Args:
            page: Page number (default: 1)
            page_size: Items per page (default: 50)
            status: Filter by status
            asset_id: Filter by asset ID

        Returns:
            Paginated response with scheduled ingestions
        """
        params: Dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }
        if status:
            params["status"] = status
        if asset_id:
            params["asset_id"] = asset_id

        return await self.client.get("scheduled-ingestions/", params=params)

    async def get(self, ingestion_id: str) -> Dict[str, Any]:
        """
        Get scheduled ingestion by ID.

        Args:
            ingestion_id: Scheduled ingestion UUID

        Returns:
            Scheduled ingestion data
        """
        return await self.client.get(f"scheduled-ingestions/{ingestion_id}/")

    async def update(
        self,
        ingestion_id: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Update scheduled ingestion (partial update supported).

        Args:
            ingestion_id: Scheduled ingestion UUID
            **kwargs: Fields to update

        Returns:
            Updated scheduled ingestion data
        """
        return await self.client.patch(f"scheduled-ingestions/{ingestion_id}/", data=kwargs)

    async def delete(self, ingestion_id: str) -> None:
        """
        Delete scheduled ingestion.

        Args:
            ingestion_id: Scheduled ingestion UUID
        """
        await self.client.delete(f"scheduled-ingestions/{ingestion_id}/")

    async def trigger(self, ingestion_id: str) -> Dict[str, Any]:
        """
        Manually trigger scheduled ingestion.

        Args:
            ingestion_id: Scheduled ingestion UUID

        Returns:
            Trigger result with run ID
        """
        return await self.client.post(f"scheduled-ingestions/{ingestion_id}/trigger/")

    async def get_run_history(
        self,
        ingestion_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Get run history for scheduled ingestion.

        Args:
            ingestion_id: Scheduled ingestion UUID
            page: Page number (default: 1)
            page_size: Items per page (default: 50)

        Returns:
            Paginated response with run history
        """
        params = {
            "page": page,
            "page_size": page_size,
        }
        return await self.client.get(f"scheduled-ingestions/{ingestion_id}/runs/", params=params)

    async def get_run(self, ingestion_id: str, run_id: str) -> Dict[str, Any]:
        """
        Get specific run details.

        Args:
            ingestion_id: Scheduled ingestion UUID
            run_id: Run UUID

        Returns:
            Run data
        """
        return await self.client.get(f"scheduled-ingestions/{ingestion_id}/runs/{run_id}/")
