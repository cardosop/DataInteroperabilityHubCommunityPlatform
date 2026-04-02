"""
Compliance operations for DataHub SDK.
"""
import asyncio
from typing import Any, Dict, List, Optional

from .client import DataHubClient


class ComplianceAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def create_run(
        self,
        asset_id: str,
        scan_mode: str = "full",
        regulations: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "asset_id": asset_id,
            "scan_mode": scan_mode,
        }
        if regulations:
            data["regulations"] = regulations
        return await self.client.post("compliance/runs/", data=data)

    async def list_runs(
        self,
        page: int = 1,
        page_size: int = 50,
        asset_id: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"page": page, "page_size": page_size}
        if asset_id:
            params["asset_id"] = asset_id
        if status:
            params["status"] = status
        return await self.client.get("compliance/runs/", params=params)

    async def get_run(self, run_id: str) -> Dict[str, Any]:
        return await self.client.get(f"compliance/runs/{run_id}/")

    async def get_results(self, run_id: str) -> Dict[str, Any]:
        return await self.client.get(f"compliance/runs/{run_id}/results/")

    async def poll_async(
        self,
        run_id: str,
        interval: float = 2.0,
        timeout: float = 300.0,
    ) -> Dict[str, Any]:
        elapsed = 0.0
        while elapsed < timeout:
            run = await self.get_run(run_id)
            if run.get("status") in ("completed", "failed", "cancelled"):
                return run
            await asyncio.sleep(interval)
            elapsed += interval
        raise TimeoutError(f"Compliance run {run_id} did not complete within {timeout}s")
