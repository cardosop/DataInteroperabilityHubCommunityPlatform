"""
Scheduled export operations for DataHub SDK.

Provides methods for managing scheduled data export workflows.
Uses real hub API - no mocks/stubs.
"""

from typing import Any, Dict, Optional

from .client import DataHubClient


class ScheduledExportAPI:
    """
    Scheduled Export API.

    Provides methods for creating, updating, and managing scheduled export workflows.
    """

    def __init__(self, client: DataHubClient):
        """
        Initialize Scheduled Export API.

        Args:
            client: DataHub client instance
        """
        self.client = client

    async def create(
        self,
        name: str,
        destination_type: str,
        destination_config: Dict[str, Any],
        schedule_config: Dict[str, Any],
        source_scope: Dict[str, Any],
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Create scheduled export.

        Args:
            name: Export name
            destination_type: Destination type (S3, GCS, AZURE_BLOB, HTTP)
            destination_config: Destination configuration
            schedule_config: Schedule configuration (must include 'cron')
            source_scope: Source scope (asset_ids, dataset_ids, file_ids, or contract_id)
            **kwargs: Additional export parameters

        Returns:
            Created scheduled export data
        """
        data: Dict[str, Any] = {
            "name": name,
            "destination_type": destination_type,
            "destination_config": destination_config,
            "schedule_config": schedule_config,
            "source_scope": source_scope,
        }
        data.update(kwargs)

        return await self.client.post("scheduled-exports/", data=data)

    async def list(
        self,
        page: int = 1,
        page_size: int = 50,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        List scheduled exports.

        Args:
            page: Page number (default: 1)
            page_size: Items per page (default: 50)
            status: Filter by status

        Returns:
            Paginated response with scheduled exports
        """
        params: Dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }
        if status:
            params["status"] = status

        return await self.client.get("scheduled-exports/", params=params)

    async def get(self, export_id: str) -> Dict[str, Any]:
        """
        Get scheduled export by ID.

        Args:
            export_id: Scheduled export UUID

        Returns:
            Scheduled export data
        """
        return await self.client.get(f"scheduled-exports/{export_id}/")

    async def update(
        self,
        export_id: str,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Update scheduled export (partial update supported).

        Args:
            export_id: Scheduled export UUID
            **kwargs: Fields to update

        Returns:
            Updated scheduled export data
        """
        return await self.client.patch(f"scheduled-exports/{export_id}/", data=kwargs)

    async def delete(self, export_id: str) -> None:
        """
        Delete scheduled export.

        Args:
            export_id: Scheduled export UUID
        """
        await self.client.delete(f"scheduled-exports/{export_id}/")

    async def trigger(self, export_id: str) -> Dict[str, Any]:
        """
        Manually trigger scheduled export.

        Args:
            export_id: Scheduled export UUID

        Returns:
            Trigger result with run ID
        """
        return await self.client.post(f"scheduled-exports/{export_id}/trigger/")

    async def get_run_history(
        self,
        export_id: str,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        Get run history for scheduled export.

        Args:
            export_id: Scheduled export UUID
            page: Page number (default: 1)
            page_size: Items per page (default: 50)

        Returns:
            Paginated response with run history
        """
        params = {
            "page": page,
            "page_size": page_size,
        }
        return await self.client.get(f"scheduled-exports/{export_id}/runs/", params=params)

    async def get_run(self, export_id: str, run_id: str) -> Dict[str, Any]:
        """
        Get specific run details.

        Args:
            export_id: Scheduled export UUID
            run_id: Run UUID

        Returns:
            Run data
        """
        return await self.client.get(f"scheduled-exports/{export_id}/runs/{run_id}/")
