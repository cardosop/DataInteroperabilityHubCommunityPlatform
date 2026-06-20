"""
Transformation operations for DataHub SDK.
"""

from typing import Any, Dict, Optional

from .client import DataHubClient


class TransformationAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def list_pipelines(
        self,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        return await self.client.get("transformation/pipelines/", params=params)

    async def get_pipeline(self, pipeline_id: str) -> Dict[str, Any]:
        return await self.client.get(f"transformation/pipelines/{pipeline_id}/")

    async def create_pipeline(
        self,
        name: str,
        description: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {"name": name}
        if description:
            data["description"] = description
        if config:
            data["config"] = config
        return await self.client.post("transformation/pipelines/", data=data)

    async def update_pipeline(self, pipeline_id: str, **kwargs: Any) -> Dict[str, Any]:
        return await self.client.patch(f"transformation/pipelines/{pipeline_id}/", data=kwargs)

    async def delete_pipeline(self, pipeline_id: str) -> None:
        await self.client.delete(f"transformation/pipelines/{pipeline_id}/")

    async def execute_pipeline(
        self,
        pipeline_id: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {}
        if params:
            data["params"] = params
        return await self.client.post(f"transformation/pipelines/{pipeline_id}/execute/", data=data)

    async def list_executions(
        self,
        pipeline_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        if pipeline_id:
            params["pipeline_id"] = pipeline_id
        if status:
            params["status"] = status
        return await self.client.get("transformation/executions/", params=params)

    async def get_execution(self, execution_id: str) -> Dict[str, Any]:
        return await self.client.get(f"transformation/executions/{execution_id}/")

    async def cancel_execution(self, execution_id: str) -> Dict[str, Any]:
        return await self.client.post(f"transformation/executions/{execution_id}/cancel/")
