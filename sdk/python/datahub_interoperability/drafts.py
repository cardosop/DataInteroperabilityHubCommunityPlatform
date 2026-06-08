"""Form draft operations for DataHub SDK."""
from typing import Any, Dict, Optional
from .client import DataHubClient

class DraftsAPI:
    def __init__(self, client: DataHubClient): self.client = client
    async def get_draft(self, resource_type: str, draft_key: str = "default") -> Dict[str, Any]:
        return await self.client.get("drafts/", params={"resource_type": resource_type, "draft_key": draft_key})
    async def save_draft(self, resource_type: str, data: Dict[str, Any], draft_key: str = "default") -> Dict[str, Any]:
        return await self.client.put("drafts/save/", data={"resource_type": resource_type, "draft_key": draft_key, "data": data})
    async def delete_draft(self, resource_type: str, draft_key: str = "default") -> None:
        await self.client.delete("drafts/delete/", params={"resource_type": resource_type, "draft_key": draft_key})
