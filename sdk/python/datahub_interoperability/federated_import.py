"""
284.A.3 — Federated Import operations for DataHub SDK.

Provides methods for listing providers, creating import jobs,
polling status, and cancelling federated marketplace imports.
"""
from typing import Dict, Any

from .client import DataHubClient


class FederatedImportAPI:
    """Federated Import API.

    Provides methods for federated marketplace import management.
    All methods are tenant-scoped via the client's authentication.
    """

    def __init__(self, client: DataHubClient):
        """Initialize Federated Import API.

        Args:
            client: DataHub client instance
        """
        self.client = client

    async def list_providers(self) -> Dict[str, Any]:
        """List supported federated import providers.

        Returns:
            Dict with ``providers`` list and ``count``.
        """
        return await self.client.get("integrations/federated-import/providers/")

    async def create_import_job(
        self,
        provider_id: str,
        credential_ref: str,
        external_listing_id: str = "",
        data_strategy: str = "METADATA_ONLY",
    ) -> Dict[str, Any]:
        """Create a federated import job.

        Args:
            provider_id: Provider id from list_providers()
            credential_ref: AWS Secrets Manager ARN (never raw creds)
            external_listing_id: Optional external listing id to import
            data_strategy: One of METADATA_ONLY, DOWNLOAD_SELECTIVE, DOWNLOAD_ALL

        Returns:
            Created job dict with id, status, provider_id.
        """
        payload: Dict[str, Any] = {
            "provider_id": provider_id,
            "credential_ref": credential_ref,
            "data_strategy": data_strategy,
        }
        if external_listing_id:
            payload["external_listing_id"] = external_listing_id
        return await self.client.post(
            "integrations/federated-import/imports/", data=payload
        )

    async def get_import_status(self, job_id: str) -> Dict[str, Any]:
        """Get the status of a federated import job.

        Args:
            job_id: Job UUID returned by create_import_job()

        Returns:
            Job status dict with id, type, status, details, timestamps.
        """
        return await self.client.get(
            f"integrations/federated-import/imports/{job_id}/"
        )

    async def cancel_import(self, job_id: str) -> Dict[str, Any]:
        """Cancel a pending or running federated import job.

        Args:
            job_id: Job UUID to cancel

        Returns:
            Dict with id and new status (cancelled).
        """
        return await self.client.post(
            f"integrations/federated-import/imports/{job_id}/cancel/"
        )
