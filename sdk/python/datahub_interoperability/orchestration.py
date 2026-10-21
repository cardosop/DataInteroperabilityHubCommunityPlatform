"""
285.11.4.7 — Pipeline dependency operations for DataHub SDK.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .client import DataHubClient


class OrchestrationAPI:
    """SDK surface for the ``/workflows/dependencies/`` endpoint family."""

    def __init__(self, client: DataHubClient):
        self.client = client

    async def list_dependencies(
        self,
        pipeline_type: str | None = None,
        pipeline_id: str | None = None,
        direction: str = "both",
    ) -> dict[str, Any]:
        """GET /api/v1/workflows/dependencies/

        Returns {nodes, links} graph.  Filterable by pipeline.
        """
        params: dict[str, Any] = {"direction": direction}
        if pipeline_type:
            params["pipeline_type"] = pipeline_type
        if pipeline_id:
            params["pipeline_id"] = pipeline_id
        return await self.client.get("workflows/dependencies/", params=params)

    async def add_manual_dependency(
        self,
        upstream_type: str,
        upstream_id: str,
        downstream_type: str,
        downstream_id: str,
        dependency_type: str = "DATA",
        priority: int = 0,
    ) -> dict[str, Any]:
        """POST /api/v1/workflows/dependencies/

        Create a manual PipelineDependency.
        """
        data: dict[str, Any] = {
            "pipeline_type": upstream_type,
            "pipeline_id": upstream_id,
            "dependency_type": dependency_type,
            "downstream_pipeline_type": downstream_type,
            "downstream_pipeline_id": downstream_id,
            "priority": priority,
            "created_by": "MANUAL",
        }
        return await self.client.post("workflows/dependencies/", data=data)

    async def preview_trigger_chain(
        self,
        pipeline_type: str,
        pipeline_id: str,
        max_depth: int = 5,
    ) -> dict[str, Any]:
        """GET /api/v1/workflows/dependencies/preview/

        Dry-run preview of the trigger chain.
        """
        return await self.client.get(
            "workflows/dependencies/preview/",
            params={
                "pipeline_type": pipeline_type,
                "pipeline_id": pipeline_id,
                "max_depth": max_depth,
            },
        )

    async def get_run_lineage(
        self,
        run_type: str,
        run_id: str,
    ) -> dict[str, Any]:
        """GET /api/v1/workflows/runs/{run_type}/{run_id}/lineage/

        Run-to-run traceability.
        """
        return await self.client.get(f"workflows/runs/{run_type}/{run_id}/lineage/")
