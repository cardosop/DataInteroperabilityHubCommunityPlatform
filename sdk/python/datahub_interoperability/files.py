"""
File operations for DataHub SDK.
"""

from typing import Any

from .client import DataHubClient


class FilesAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def init_upload(
        self,
        name: str,
        content_type: str,
        size: int,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {
            "name": name,
            "content_type": content_type,
            "size": size,
        }
        return await self.client.post("files/init/", data=data)

    async def complete_upload(
        self,
        file_id: str,
        content_sha256: str | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if content_sha256:
            data["content_sha256"] = content_sha256
        return await self.client.post(f"files/{file_id}/complete/", data=data or None)

    async def list_files(
        self,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"limit": limit, "offset": offset}
        if status:
            params["status"] = status
        return await self.client.get("files/", params=params)

    async def get_file(self, file_id: str) -> dict[str, Any]:
        return await self.client.get(f"files/{file_id}/")

    async def delete_file(self, file_id: str) -> None:
        await self.client.delete(f"files/{file_id}/")

    async def get_download_url(self, file_id: str) -> dict[str, Any]:
        return await self.client.get(f"files/{file_id}/download/")
