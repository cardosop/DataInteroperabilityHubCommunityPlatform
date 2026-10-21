"""
Observability operations for DataHub SDK.

Provides methods for monitoring data freshness, volume, schema drift, pipelines, SLAs, and incidents.
"""

from typing import Any

from .client import DataHubClient


class ObservabilityAPI:
    """
    Observability API.

    Provides methods for data observability and monitoring.
    """

    def __init__(self, client: DataHubClient):
        """
        Initialize Observability API.

        Args:
            client: DataHub client instance
        """
        self.client = client

    async def get_freshness(
        self,
        dataset_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """
        Get data freshness monitoring metrics.

        Args:
            dataset_id: Filter by dataset ID (optional)
            start_date: Start date for metrics (ISO 8601, optional)
            end_date: End date for metrics (ISO 8601, optional)

        Returns:
            Freshness metrics
        """
        params: dict[str, Any] = {}
        if dataset_id:
            params["dataset_id"] = dataset_id
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        return await self.client.get("observability/freshness/", params=params)

    async def get_volume(
        self,
        dataset_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """
        Get data volume monitoring metrics.

        Args:
            dataset_id: Filter by dataset ID (optional)
            start_date: Start date for metrics (ISO 8601, optional)
            end_date: End date for metrics (ISO 8601, optional)

        Returns:
            Volume metrics
        """
        params: dict[str, Any] = {}
        if dataset_id:
            params["dataset_id"] = dataset_id
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        return await self.client.get("observability/volume/", params=params)

    async def get_schema_drift(
        self,
        dataset_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get schema drift detection results.

        Args:
            dataset_id: Filter by dataset ID (optional)

        Returns:
            Schema drift data
        """
        params: dict[str, Any] = {}
        if dataset_id:
            params["dataset_id"] = dataset_id

        return await self.client.get("observability/schema-drift/", params=params)

    async def get_pipelines(
        self,
        pipeline_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """
        Get pipeline monitoring metrics.

        Args:
            pipeline_id: Filter by pipeline ID (optional)
            start_date: Start date for metrics (ISO 8601, optional)
            end_date: End date for metrics (ISO 8601, optional)

        Returns:
            Pipeline metrics
        """
        params: dict[str, Any] = {}
        if pipeline_id:
            params["pipeline_id"] = pipeline_id
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date

        return await self.client.get("observability/pipelines/", params=params)

    async def get_slas(
        self,
        dataset_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Get data SLA monitoring.

        Args:
            dataset_id: Filter by dataset ID (optional)

        Returns:
            SLA monitoring data
        """
        params: dict[str, Any] = {}
        if dataset_id:
            params["dataset_id"] = dataset_id

        return await self.client.get("observability/slas/", params=params)

    async def list_incidents(
        self,
        status: str | None = None,
        severity: str | None = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """
        List data incidents.

        Args:
            status: Filter by status (optional)
            severity: Filter by severity (optional)
            page: Page number (default: 1)
            page_size: Items per page (default: 50)

        Returns:
            Paginated response with incidents
        """
        params: dict[str, Any] = {
            "page": page,
            "page_size": page_size,
        }
        if status:
            params["status"] = status
        if severity:
            params["severity"] = severity

        return await self.client.get("observability/incidents/", params=params)

    async def create_incident(
        self,
        dataset_id: str,
        severity: str,
        description: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Create data incident.

        Args:
            dataset_id: Dataset UUID
            severity: Incident severity (LOW, MEDIUM, HIGH, CRITICAL)
            description: Incident description
            **kwargs: Additional incident parameters

        Returns:
            Created incident
        """
        data: dict[str, Any] = {
            "dataset_id": dataset_id,
            "severity": severity,
            "description": description,
        }
        data.update(kwargs)

        return await self.client.post("observability/incidents/", data=data)

    async def update_incident(
        self,
        incident_id: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """
        Update data incident.

        Args:
            incident_id: Incident UUID
            **kwargs: Fields to update (status, severity, description, etc.)

        Returns:
            Updated incident
        """
        data = {"incident_id": incident_id}
        data.update(kwargs)
        return await self.client.patch("observability/incidents/update/", data=data)
