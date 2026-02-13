"""
GDPR operations for DataHub SDK (Phase 25).

Provides methods for data export and erasure requests.
Uses real hub API - no mocks/stubs.
"""

from typing import Any, Dict, Optional

from .client import DataHubClient


class GDPRAPI:
    """
    GDPR API.

    Provides methods for data portability and erasure requests.
    """

    def __init__(self, client: DataHubClient):
        """
        Initialize GDPR API.

        Args:
            client: DataHub client instance
        """
        self.client = client

    async def request_export(self) -> Dict[str, Any]:
        """
        Request data export (GDPR Article 20 - Data Portability).

        Returns:
            Export job data with download URL
        """
        return await self.client.post("users/me/export-jobs/export-data/")

    async def list_export_jobs(
        self,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        List data export jobs.

        Args:
            page: Page number (default: 1)
            page_size: Items per page (default: 50)

        Returns:
            Paginated response with export jobs
        """
        params = {
            "page": page,
            "page_size": page_size,
        }
        return await self.client.get("users/me/export-jobs/", params=params)

    async def get_export_job(self, job_id: str) -> Dict[str, Any]:
        """
        Get export job by ID.

        Args:
            job_id: Export job UUID

        Returns:
            Export job data
        """
        return await self.client.get(f"users/me/export-jobs/{job_id}/")

    async def request_erasure(self) -> Dict[str, Any]:
        """
        Request data erasure (GDPR Article 17 - Right to be Forgotten).

        Returns:
            Erasure request data
        """
        return await self.client.post("users/me/erasure-requests/request-erasure/")

    async def list_erasure_requests(
        self,
        page: int = 1,
        page_size: int = 50,
    ) -> Dict[str, Any]:
        """
        List erasure requests.

        Args:
            page: Page number (default: 1)
            page_size: Items per page (default: 50)

        Returns:
            Paginated response with erasure requests
        """
        params = {
            "page": page,
            "page_size": page_size,
        }
        return await self.client.get("users/me/erasure-requests/", params=params)

    async def get_erasure_request(self, request_id: str) -> Dict[str, Any]:
        """
        Get erasure request by ID.

        Args:
            request_id: Erasure request UUID

        Returns:
            Erasure request data
        """
        return await self.client.get(f"users/me/erasure-requests/{request_id}/")
