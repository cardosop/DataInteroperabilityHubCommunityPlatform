"""
Transformation operations for DataHub SDK.
"""

from typing import Any

from .client import DataHubClient


class TransformationAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def list_pipelines(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        return await self.client.get("transformation/pipelines/", params=params)

    async def get_pipeline(self, pipeline_id: str) -> dict[str, Any]:
        return await self.client.get(f"transformation/pipelines/{pipeline_id}/")

    async def create_pipeline(
        self,
        name: str,
        pipeline_definition: dict[str, Any],
        description: str | None = None,
        version: str | None = None,
    ) -> dict[str, Any]:
        """Create a transformation pipeline.

        ``TransformationPipelineCreateSerializer`` requires
        ``pipeline_definition`` and has no ``config`` field, so the previous
        signature could only ever 400: it omitted the required key and sent
        one the backend ignores.
        """
        data: dict[str, Any] = {"name": name, "pipeline_definition": pipeline_definition}
        if description:
            data["description"] = description
        if version:
            data["version"] = version
        return await self.client.post("transformation/pipelines/", data=data)

    async def update_pipeline(self, pipeline_id: str, **kwargs: Any) -> dict[str, Any]:
        return await self.client.patch(f"transformation/pipelines/{pipeline_id}/", data=kwargs)

    async def delete_pipeline(self, pipeline_id: str) -> None:
        await self.client.delete(f"transformation/pipelines/{pipeline_id}/")

    async def execute_pipeline(
        self,
        pipeline_id: str,
        asset_id: str,
        execution_mode: str = "ASYNC",
    ) -> dict[str, Any]:
        """Execute a pipeline against a source asset.

        The ``execute`` action requires ``asset_id`` and reads
        ``execution_mode`` (default ``ASYNC``); it never reads ``params``.
        The previous signature therefore always 400'd on the missing
        required field.  Mirrors ``datahub transformation runs submit``.
        """
        data: dict[str, Any] = {"asset_id": asset_id, "execution_mode": execution_mode}
        return await self.client.post(f"transformation/pipelines/{pipeline_id}/execute/", data=data)

    async def list_executions(
        self,
        pipeline_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if pipeline_id:
            params["pipeline_id"] = pipeline_id
        if status:
            params["status"] = status
        return await self.client.get("transformation/executions/", params=params)

    async def get_execution(self, execution_id: str) -> dict[str, Any]:
        return await self.client.get(f"transformation/executions/{execution_id}/")

    async def cancel_execution(self, execution_id: str) -> dict[str, Any]:
        return await self.client.post(f"transformation/executions/{execution_id}/cancel/")
