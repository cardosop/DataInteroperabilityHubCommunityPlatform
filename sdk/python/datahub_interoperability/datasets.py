"""
Dataset operations for DataHub SDK.
"""

from typing import Any

from .client import DataHubClient


class DatasetsAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def list_datasets(
        self,
        asset_id: str | None = None,
        dataset_format: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if asset_id:
            params["asset_id"] = asset_id
        if dataset_format:
            params["format"] = dataset_format
        return await self.client.get("datasets/", params=params)

    async def get_dataset(self, dataset_id: str) -> dict[str, Any]:
        return await self.client.get(f"datasets/{dataset_id}/")

    async def create_dataset(
        self,
        file_id: str,
        asset_id: str | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {"file_id": file_id}
        if asset_id:
            data["asset_id"] = asset_id
        return await self.client.post("datasets/", data=data)

    async def delete_dataset(self, dataset_id: str) -> None:
        await self.client.delete(f"datasets/{dataset_id}/")

    async def list_versions(self, dataset_id: str) -> list[dict[str, Any]]:
        result = await self.client.get(f"datasets/{dataset_id}/versions/")
        if isinstance(result, dict) and "results" in result:
            return result["results"]
        return result

    async def upload_and_create(
        self,
        file_path: str,
        asset_id: str | None = None,
    ) -> dict[str, Any]:
        # Placeholder: full implementation requires multipart upload via files API
        raise NotImplementedError(
            "upload_and_create requires multipart file upload. "
            "Use FilesAPI.init_upload() + complete_upload() then DatasetsAPI.create_dataset()."
        )
