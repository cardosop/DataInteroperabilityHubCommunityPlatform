"""
Workflow operations for DataHub SDK.
"""
from typing import Any, Dict, Optional

from .client import DataHubClient


class WorkflowsAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def list_workflows(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        return await self.client.get("workflows/", params=params)

    async def get_workflow(self, workflow_id: str) -> Dict[str, Any]:
        return await self.client.get(f"workflows/{workflow_id}/")

    async def trigger_workflow(self, workflow_id: str) -> Dict[str, Any]:
        return await self.client.post(f"workflows/{workflow_id}/trigger/")

    async def retry_workflow(self, workflow_id: str) -> Dict[str, Any]:
        return await self.client.post(f"workflows/{workflow_id}/retry/")
