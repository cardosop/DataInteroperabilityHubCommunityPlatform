"""
User management operations for DataHub SDK.
"""

from typing import Any, Dict

from .client import DataHubClient


class UsersAPI:
    def __init__(self, client: DataHubClient):
        self.client = client

    async def list_users(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        return await self.client.get("users/", params=params)

    async def get_user(self, user_id: str) -> Dict[str, Any]:
        return await self.client.get(f"users/{user_id}/")

    async def create_user(
        self,
        email: str,
        display_name: str,
        role: str = "viewer",
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "email": email,
            "display_name": display_name,
            "role": role,
        }
        return await self.client.post("users/", data=data)

    async def update_user(self, user_id: str, **kwargs: Any) -> Dict[str, Any]:
        return await self.client.patch(f"users/{user_id}/", data=kwargs)

    async def list_invitations(self) -> Dict[str, Any]:
        return await self.client.get("auth/invitations/")

    async def create_invitation(
        self,
        email: str,
        role: str = "viewer",
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {"email": email, "role": role}
        return await self.client.post("auth/invitations/", data=data)
