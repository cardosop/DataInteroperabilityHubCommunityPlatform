"""
Job operations for DataHub SDK.
"""
from typing import Any, Dict, Optional

from .client import DataHubClient


class JobsAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def list_jobs(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        return await self.client.get("jobs/", params=params)

    async def get_job(self, job_id: str) -> Dict[str, Any]:
        return await self.client.get(f"jobs/{job_id}/")

    async def cancel_job(self, job_id: str) -> Dict[str, Any]:
        return await self.client.post(f"jobs/{job_id}/cancel/")
