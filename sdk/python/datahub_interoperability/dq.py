"""
Data Quality operations for DataHub SDK.
"""
from typing import Any, Dict, Optional

from .client import DataHubClient


class DQAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def create_run(
        self,
        asset_id: str,
        dataset_id: Optional[str] = None,
        file_id: Optional[str] = None,
        profile_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {"asset_id": asset_id}
        if dataset_id:
            data["dataset_id"] = dataset_id
        if file_id:
            data["file_id"] = file_id
        if profile_key:
            data["profile_key"] = profile_key
        return await self.client.post("dq/runs/", data=data)

    async def list_runs(
        self,
        asset_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if asset_id:
            params["asset_id"] = asset_id
        if dataset_id:
            params["dataset_id"] = dataset_id
        if status:
            params["status"] = status
        return await self.client.get("dq/runs/", params=params)

    async def get_run(self, run_id: str) -> Dict[str, Any]:
        return await self.client.get(f"dq/runs/{run_id}/")

    async def get_scorecard(self, asset_id: str) -> Dict[str, Any]:
        return await self.client.get(f"dq/scorecards/{asset_id}/")

    async def list_alerts(self, asset_id: str) -> Dict[str, Any]:
        return await self.client.get("dq/alerts/", params={"asset_id": asset_id})

    async def create_alert(
        self,
        asset_id: str,
        threshold: float,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "asset_id": asset_id,
            "threshold": threshold,
        }
        return await self.client.post("dq/alerts/", data=data)

    async def get_anomalies(self, asset_id: str) -> Dict[str, Any]:
        return await self.client.get(f"dq/anomalies/{asset_id}/")

    async def get_trends(self, asset_id: str) -> Dict[str, Any]:
        return await self.client.get(f"dq/trends/{asset_id}/")
